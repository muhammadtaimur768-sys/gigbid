"""Shared fixtures/helpers for the API TestClient tests (no tests here)."""
from __future__ import annotations

import importlib
import os
import time
from typing import Any, TypedDict

JOBS = [
    {"id": "job-low", "title": "Excel cleanup", "description": "Format a spreadsheet", "category": "data",
     "skills_required": ["excel"], "budget_type": "fixed", "budget_min": 50, "budget_max": 80,
     "client_id": "c1", "connects_cost": 4, "proposals_count": 3, "posted_at": "2026-11-15T10:00:00Z"},
    {"id": "job-high", "title": "Build a RAG chatbot with LangGraph",
     "description": "Python LangGraph RAG pipeline with evaluation", "category": "ai_ml",
     "skills_required": ["python", "langgraph", "rag"], "budget_type": "fixed", "budget_min": 1500,
     "budget_max": 3000, "client_id": "c2", "connects_cost": 8, "proposals_count": 5,
     "posted_at": "2026-11-15T09:00:00Z"},
    {"id": "job-mid", "title": "Python data scraper", "description": "Scrape and clean data with python",
     "category": "ai_ml", "skills_required": ["python", "scrapy"], "budget_type": "fixed", "budget_min": 300,
     "budget_max": 500, "client_id": "c3", "connects_cost": 6, "proposals_count": 12,
     "posted_at": "2026-11-15T08:00:00Z"},
]
PROFILE = {"persona": "aiml", "skills": ["python", "langgraph", "rag", "llm"], "hourly_floor": 40,
           "hourly_target": 70}


def fake_bid_graph(checkpointer, store):
    """Minimal graph honouring the agent contract: parallel-ish analysis, interrupt at approval,
    resume with an ApprovalDecision dict, submit on approve/edit."""
    from langgraph.config import get_stream_writer
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import interrupt

    class S(TypedDict, total=False):
        job_id: str
        job: dict
        user_id: str
        persona: str
        thread_id: str
        trace_id: str
        options: dict
        fit: dict
        risk: dict
        decision: dict
        price: dict
        draft: dict
        approval: dict
        submission: dict
        status: str
        status_reason: str

    def analyst(s):
        get_stream_writer()({"node": "analyst", "message": "parsing job"})
        return {"fit": {"job_id": s["job_id"], "fit_score": 0.82, "matches": [], "reasons": ["python"], "gaps": []},
                "risk": {"job_id": s["job_id"], "client_score": 0.9, "is_scam": False, "injection_detected": False,
                         "flags": [], "summary": "ok"}}

    def decide(s):
        return {"decision": {"job_id": s["job_id"], "action": "bid", "confidence": 0.8, "reasons": ["fit"]},
                "price": {"job_id": s["job_id"], "amount": 2000.0, "budget_type": "fixed", "connects_cost": 8,
                          "worth_connects": True, "rationale": "p50"}}

    def writer(s):
        return {"draft": {"job_id": s["job_id"], "version": 1,
                          "cover_letter": "I built a LangGraph RAG system.\n\nI can start Monday.",
                          "claims": [{"id": "c1", "text": "I built a LangGraph RAG system.",
                                      "status": "supported", "evidence_ids": ["aiml-case-01#c0"]}]}}

    def approval(s):
        decision = interrupt({"draft": s["draft"], "price": s["price"], "risk": s["risk"],
                              "dry_run": {"connects_cost": 8, "balance_after": 92}})
        return {"approval": decision}

    def route(s):
        return "reject" if s["approval"].get("action") == "reject" else "submit"

    def reject(s):
        return {"status": "rejected", "status_reason": s["approval"].get("reason", "")}

    def submit(s):
        text = s["approval"].get("edited_text") or s["draft"]["cover_letter"]
        return {"submission": {"proposal_id": f"p-{s['job_id']}", "status": "submitted", "connects_spent": 8,
                               "cover_letter": text}, "status": "submitted"}

    g = StateGraph(S)
    for name, fn in [("analyst", analyst), ("decide", decide), ("writer", writer), ("approval", approval),
                     ("reject", reject), ("submit", submit)]:
        g.add_node(name, fn)
    g.add_edge(START, "analyst")
    g.add_edge("analyst", "decide")
    g.add_edge("decide", "writer")
    g.add_edge("writer", "approval")
    g.add_conditional_edges("approval", route, {"reject": "reject", "submit": "submit"})
    g.add_edge("reject", END)
    g.add_edge("submit", END)
    return g.compile(checkpointer=checkpointer, store=store)


def make_client(tmp_path, monkeypatch, use_fake_graph: bool = True, fake_marketplace: bool = True):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("TRACE_DATABASE_URL", f"sqlite:///{tmp_path / 'trace.db'}")
    monkeypatch.setenv("LLM_PROVIDER", "heuristic")
    monkeypatch.setenv("RUN_MODE", "inline")
    monkeypatch.setenv("MOUNT_GIGSIM", "0")
    monkeypatch.setenv("MOUNT_MCP", "0")
    monkeypatch.setenv("GIGSIM_ERROR_RATE", "0")
    from apps.api import config, db
    config.get_settings.cache_clear()
    db.reset_engine()
    from apps.api import graphs
    graphs.close_runtime()
    graphs.runtime.errors.clear()
    from apps.api.services import fit, marketplace
    if fake_marketplace:
        marketplace.force_status(True)
        monkeypatch.setattr(fit, "persona_profile", lambda persona: PROFILE)

        async def list_jobs(token, **kw):
            return {"jobs": [dict(j) for j in JOBS], "total": len(JOBS)}

        async def get_job(token, job_id):
            return next(dict(j) for j in JOBS if j["id"] == job_id)

        async def empty(*a, **k):
            return []

        async def client_history(token, cid):
            return {"client_id": cid, "name": "Client", "hires": 3}

        monkeypatch.setattr(marketplace, "list_jobs", list_jobs)
        monkeypatch.setattr(marketplace, "get_job", get_job)
        monkeypatch.setattr(marketplace, "list_proposals", empty)
        monkeypatch.setattr(marketplace, "get_client_history", client_history)
    else:
        marketplace.force_status(None)
    if use_fake_graph:
        monkeypatch.setattr(graphs, "build_graphs", lambda: None)
    monkeypatch.delenv("VERCEL", raising=False)
    main = importlib.import_module("apps.api.main")
    main.reset_ready()
    client = TestClient(main.app)
    client.__enter__()
    if use_fake_graph:
        graphs.runtime.bid_graph = fake_bid_graph(graphs.runtime.checkpointer, graphs.runtime.store)
    return client


def close_client(client):
    from apps.api.services import marketplace
    marketplace.force_status(None)
    client.__exit__(None, None, None)


def login(client, email="reviewer@gigbid.app", password=None) -> dict:
    password = password or os.getenv("REVIEWER_PASSWORD", "review-gigbid-2026")
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def wait_status(client, headers, thread_id, statuses=("interrupted", "done", "error"), timeout=20.0) -> dict:
    deadline = time.time() + timeout
    last: Any = None
    while time.time() < deadline:
        last = client.get(f"/api/runs/{thread_id}", headers=headers).json()
        if last.get("status") in statuses:
            return last
        time.sleep(0.1)
    raise AssertionError(f"run {thread_id} did not reach {statuses}: {last}")


def client_fixture(tmp_path, monkeypatch):
    """Generator body for an `api` fixture: TestClient with fake graph + fake marketplace."""
    c = make_client(tmp_path, monkeypatch)
    try:
        yield c
    finally:
        close_client(c)
