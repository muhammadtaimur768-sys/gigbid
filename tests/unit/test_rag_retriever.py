"""Retriever tests on a tiny temporary persona corpus (real fastembed models, no network once cached)."""
from __future__ import annotations

import json

import pytest

from rag import retriever as R
from rag.config import load_config, variant_flags
from rag.ingest.chunkers import code_digest, fixed_chunks, structured_chunks
from rag.ingest.loaders import load_persona
from rag.variants.v1_decompose import extract_requirements
from rag.variants.v2_hybrid import rrf

CASE = """---
id: t-case-01
title: Support chatbot with retrieval
project: helpdesk-bot
skills: [langchain, pinecone, fastapi]
date: 2025-03-01
client_industry: ecommerce
outcome: delivered
---
# Support chatbot
Built a retrieval-augmented support assistant over 4,000 help-centre articles for an online retailer.
Answers are grounded in the retrieved articles and deflected 38% of tickets in the first month.
"""

CASE2 = """---
id: t-case-02
title: Sales dashboard
project: sales-dash
skills: [sql, tableau]
date: 2024-06-01
client_industry: retail
outcome: delivered
---
# Weekly sales dashboard
Designed a Tableau dashboard on top of a Postgres warehouse with weekly revenue by region.
"""

README = "# churn-model\nA small project predicting which subscribers will cancel.\n"
CODE = "import xgboost\nfrom sklearn.model_selection import train_test_split\n\ndef train(df):\n    return xgboost.XGBClassifier().fit(df, df)\n"


@pytest.fixture()
def corpus(tmp_path, monkeypatch):
    p = tmp_path / "personas" / "t"
    (p / "case_studies").mkdir(parents=True)
    (p / "case_studies" / "t-case-01.md").write_text(CASE)
    (p / "case_studies" / "t-case-02.md").write_text(CASE2)
    (p / "repos" / "t-repo-01").mkdir(parents=True)
    (p / "repos" / "t-repo-01" / "README.md").write_text(README)
    (p / "repos" / "t-repo-01" / "train.py").write_text(CODE)
    (p / "cv.md").write_text("# T Person\nMachine learning engineer. Python, LangChain, XGBoost.\n")
    (p / "profile.json").write_text(json.dumps({"persona": "t", "title": "ML engineer", "skills": ["python"]}))
    (p / "reviews.json").write_text(json.dumps([{"id": "t-review-01", "client": "Acme", "rating": 5,
                                                 "text": "Great chatbot work, fast delivery.", "project": "helpdesk-bot",
                                                 "date": "2025-04-01"}]))
    (p / "proposals.jsonl").write_text("\n".join(json.dumps(x) for x in [
        {"id": "t-prop-001", "job_title": "RAG chatbot", "category": "ai", "skills": ["langchain"],
         "text": "I built a help-centre chatbot with LangChain and Pinecone.", "outcome": "won", "date": "2025-05-01",
         "project": "helpdesk-bot"},
        {"id": "t-prop-002", "job_title": "Dashboard", "category": "data", "skills": ["tableau"],
         "text": "I can build your Tableau dashboard.", "outcome": "ignored", "date": "2025-05-02"},
    ]) + "\n")
    cfg = load_config()
    monkeypatch.setitem(cfg, "paths", {**cfg["paths"], "personas_dir": str(tmp_path / "personas"),
                                       "index_dir": str(tmp_path / "index")})
    R._STORES.clear(), R._ITEMS.clear(), R._RETRIEVERS.clear()
    yield p
    R._STORES.clear(), R._ITEMS.clear(), R._RETRIEVERS.clear()


def test_loader_metadata(corpus):
    items = {i.item_id: i for i in load_persona(corpus, "t")}
    assert {"t-cv", "t-case-01", "t-case-02", "t-repo-01", "t-review-01", "t-prop-001", "t-prop-002"} <= set(items)
    assert items["t-case-01"].client_industry == "ecommerce"
    assert items["t-prop-001"].outcome == "won"
    assert items["t-repo-01"].files and items["t-repo-01"].files[0]["path"] == "train.py"


def test_chunks_carry_metadata(corpus):
    item = next(i for i in load_persona(corpus, "t") if i.item_id == "t-repo-01")
    for chunks in (fixed_chunks(item, 80, 10), structured_chunks(item)):
        assert all(c.chunk_id.startswith("t-repo-01#c") for c in chunks)
        assert {c.type for c in chunks} == {"repo", "code"}
        assert all(c.persona == "t" for c in chunks)
    assert "xgboost" in code_digest(item) and "sklearn" in code_digest(item)


def test_variant_flags_compose():
    f = variant_flags("v1+v2+v3")
    assert f["query"] == "decompose" and f["retrieval"] == "hybrid" and f["rerank"] is True
    assert variant_flags("v0")["chunking"] == "fixed" and variant_flags("v0")["dedupe_items"] is False
    with pytest.raises(ValueError):
        variant_flags("v42")


def test_rrf_prefers_items_ranked_high_in_both():
    fused = rrf([["a", "b", "c"], ["b", "a", "d"]], k=60)
    assert [k for k, _ in fused][:2] in (["a", "b"], ["b", "a"])
    assert dict(fused)["d"] < dict(fused)["a"]


def test_extract_requirements_from_structured_fields():
    job = {"title": "x", "skills_required": ["Celery", "dbt"],
           "description": "We need help.\n- Build an ETL pipeline\n- Write tests"}
    assert extract_requirements(job) == ["Celery", "dbt", "Build an ETL pipeline", "Write tests"]


@pytest.mark.parametrize("variant", ["v0", "v1+v2+v3+v4", "v5", "v8"])
def test_search_finds_relevant_item(corpus, variant):
    r = R.get_retriever("t", variant)
    ev = r.search("customer support chatbot grounded in help articles", k=5,
                  requirements=["LangChain", "Pinecone"])
    if variant == "v8" and not ev:
        pytest.fail("corrective variant refused on an on-profile query")
    assert ev[0].item_id in {"t-case-01", "t-prop-001", "t-review-01"}
    assert all(e.chunk_id.startswith(e.item_id) for e in ev)


def test_filters_and_get_item_and_skills(corpus):
    r = R.get_retriever("t", "v2")
    ev = r.search("dashboard", k=5, filters={"type": "case_study"})
    assert ev and all(e.type == "case_study" for e in ev)
    item = r.get_item("t-repo-01")
    assert "xgboost" in item["full_text"] and item["chunk_ids"]
    skills = {s["skill"]: s for s in r.list_skills()}
    assert "langchain" in skills and "t-case-01" in skills["langchain"]["items"]
    with pytest.raises(KeyError):
        r.get_item("nope")


def test_corrective_refuses_off_profile(corpus):
    r = R.get_retriever("t", "v8")
    assert r.search("Need a licensed plumber to fix a leaking kitchen sink pipe in Boston", k=5) == []
    assert r.last_info.get("refused") is True


def test_add_document_incremental(corpus):
    r = R.get_retriever("t", "v2")
    before = len(r.store.chunks)
    out = r.add_document("t-case-03", "case_study", "# Kubernetes migration\nMoved 12 services to Kubernetes with Helm.",
                         project="k8s", skills=["kubernetes", "helm"])
    assert out["chunks"] >= 1 and len(r.store.chunks) == before + out["chunks"]
    assert r.search("Helm charts Kubernetes migration", k=3)[0].item_id == "t-case-03"
    # persisted: a fresh process (cleared caches) sees the uploaded item
    R._STORES.clear(), R._ITEMS.clear(), R._RETRIEVERS.clear()
    r2 = R.get_retriever("t", "v2")
    assert "t-case-03" in r2.store.item_rows
