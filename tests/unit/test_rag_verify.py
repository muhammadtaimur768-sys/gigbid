"""Claim verification tests (heuristic mode, no LLM)."""
from __future__ import annotations

import pytest

from rag import retriever as R
from rag.config import load_config
from rag.verify import is_claim, split_sentences, verify_proposal

from test_rag_retriever import corpus  # noqa: F401  (fixture)


def test_split_sentences_keeps_paragraphs():
    s = split_sentences("Hi there. I built a bot.\n\nThanks! Talk soon.")
    assert [p for p, _ in s] == [0, 0, 1, 1]


def test_claim_detection():
    v = load_config()["verify"]
    skills = {"langchain", "pinecone"}
    assert is_claim("I built a support chatbot with LangChain for a retailer.", skills, v)
    assert is_claim("My last project cut ticket volume by 38%.", skills, v)
    assert not is_claim("I can start on Monday and deliver in two weeks.", skills, v)
    assert not is_claim("Do you already have an index of the articles?", skills, v)
    assert not is_claim("Thanks for reading.", skills, v)


def test_verify_removes_unsupported_and_keeps_supported(corpus):  # noqa: F811
    r = R.get_retriever("t", "v2")
    text = ("Hi, thanks for posting this.\n\n"
            "I built a retrieval-augmented support assistant over 4,000 help-centre articles for an online retailer. "
            "I led a team of 40 engineers building self-driving car firmware for Tesla.\n\n"
            "I can start on Monday.")
    out = verify_proposal(text, r, "t")
    by_text = {c.text: c for c in out["claims"]}
    good = by_text["I built a retrieval-augmented support assistant over 4,000 help-centre articles for an online retailer."]
    bad = by_text["I led a team of 40 engineers building self-driving car firmware for Tesla."]
    assert good.status in ("supported", "partly_supported") and good.action == "kept" and good.evidence_ids
    assert bad.status == "unsupported" and bad.action == "removed"
    assert out["unsupported_before"] >= 1 and out["unsupported_after"] == 0
    assert "Tesla" not in out["cleaned_text"] and "I can start on Monday." in out["cleaned_text"]
    assert out["n_claims"] == len(out["claims"]) == 2


def test_verify_no_claims(corpus):  # noqa: F811
    out = verify_proposal("Hello! Could you share more about the timeline?", R.get_retriever("t", "v2"), "t")
    assert out["claims"] == [] and out["unsupported_before"] == 0 and out["unsupported_after"] == 0


@pytest.mark.parametrize("mode", ["llm"])
def test_llm_mode_falls_back_without_model(corpus, mode, monkeypatch):  # noqa: F811
    monkeypatch.setenv("LLM_PROVIDER", "heuristic")
    out = verify_proposal("I built a support chatbot with LangChain and Pinecone for a retailer.",
                          R.get_retriever("t", "v2"), "t", mode=mode)
    assert out["claims"] and out["claims"][0].status in ("supported", "partly_supported", "unsupported")
