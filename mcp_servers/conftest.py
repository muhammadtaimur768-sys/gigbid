"""Shared fixtures for MCP server tests: isolated audit/idempotency files and a tiny portfolio."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_servers.common.audit import AuditLog
from mcp_servers.common.idempotency import IdempotencyStore
from mcp_servers.common.ratelimit import TokenBucketLimiter


@pytest.fixture
def isolated_runtime(tmp_path, monkeypatch):
    """Point every server runtime at tmp files; return the audit path."""
    from mcp_servers.marketplace import server as mk
    from mcp_servers.workspace import server as ws

    audit = tmp_path / "audit.log"
    for srv in (mk, ws):
        monkeypatch.setattr(srv.runtime, "audit", AuditLog(audit))
        monkeypatch.setattr(srv.runtime, "idem", IdempotencyStore(tmp_path / f"idem-{srv.SERVER_NAME}.json"))
        monkeypatch.setattr(srv.runtime, "limiter", TokenBucketLimiter(capacity=50, refill_per_minute=50))
    ws.set_store(ws.WorkspaceStore(tmp_path / "workspace.json"))
    return audit


def write_mini_portfolio(root: Path, persona: str = "aiml") -> Path:
    p = root / persona
    (p / "case_studies").mkdir(parents=True)
    (p / "repos" / f"{persona}-repo-01").mkdir(parents=True)
    (p / "profile.json").write_text(json.dumps({"persona": persona, "name": "Test", "title": "ML engineer",
                                                "skills": ["python", "rag"]}))
    (p / "cv.md").write_text("# CV\nPython engineer building retrieval systems.")
    (p / "case_studies" / f"{persona}-case-01.md").write_text(
        "---\nid: %s-case-01\ntitle: Legal RAG assistant\nproject: lexsearch\nskills: [rag, python, reranking]\n"
        "date: 2025-03-01\nclient_industry: legal\noutcome: shipped\n---\n"
        "Built a retrieval augmented generation pipeline with hybrid BM25 and dense search and a cross-encoder "
        "reranker for a law firm. Cut lookup time by half.\n\nSecond paragraph about deployment on AWS." % persona)
    (p / "case_studies" / f"{persona}-case-02.md").write_text(
        "---\nid: %s-case-02\ntitle: Churn dashboard\nproject: churnviz\nskills: [sql, dashboards]\n"
        "date: 2024-06-01\nclient_industry: saas\noutcome: shipped\n---\nBuilt SQL models and a churn dashboard."
        % persona)
    (p / "repos" / f"{persona}-repo-01" / "README.md").write_text("# lexsearch\nSearch service for documents.")
    (p / "repos" / f"{persona}-repo-01" / "rank.py").write_text("from rank_bm25 import BM25Okapi\n# reranker\n")
    (p / "reviews.json").write_text(json.dumps([{"id": f"{persona}-review-01", "client": "Acme", "rating": 5,
                                                 "text": "Great RAG work, fast.", "project": "lexsearch",
                                                 "date": "2025-04-01"}]))
    (p / "proposals.jsonl").write_text(json.dumps({"id": f"{persona}-prop-001", "job_title": "RAG chatbot",
                                                   "category": "AI", "skills": ["rag"], "outcome": "won",
                                                   "text": "I built a legal RAG assistant with reranking.",
                                                   "date": "2025-05-01", "client_industry": "legal"}) + "\n")
    return root


@pytest.fixture
def mini_portfolio(tmp_path, monkeypatch):
    from mcp_servers.portfolio.gigbid_portfolio_mcp import store

    root = write_mini_portfolio(tmp_path / "personas")
    monkeypatch.setenv("PORTFOLIO_DATA_DIR", str(root))
    monkeypatch.setenv("PORTFOLIO_BACKEND", "keyword")
    monkeypatch.setenv("PORTFOLIO_PERSONA", "aiml")
    store.reset_backends()
    yield root
    store.reset_backends()
