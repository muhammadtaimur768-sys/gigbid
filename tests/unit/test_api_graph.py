"""API against the real agent bid graph (LLM_PROVIDER=heuristic, in-memory marketplace port)."""
from __future__ import annotations

import pytest
from test_api_support import JOBS, close_client, login, make_client, wait_status


@pytest.fixture
def real_api(tmp_path, monkeypatch):
    build = pytest.importorskip("agent.graphs.bid_graph").build_bid_graph
    from agent.marketplace_port import InMemoryMarketplace

    from apps.api import graphs
    port = InMemoryMarketplace(jobs=[dict(j) for j in JOBS], balance=200)

    def build_graphs():
        graphs.runtime.bid_graph = build(checkpointer=graphs.runtime.checkpointer, store=graphs.runtime.store,
                                         marketplace=port)
    monkeypatch.setattr(graphs, "build_graphs", build_graphs)
    c = make_client(tmp_path, monkeypatch, use_fake_graph=False)
    c.port = port
    try:
        yield c
    finally:
        close_client(c)


def test_heuristic_run_to_approval_and_submit(real_api):
    api = real_api
    h = login(api)
    assert api.get("/api/health").json()["graphs"]["bid"] == "available"
    api.get("/api/jobs", headers=h)
    r = api.post("/api/jobs/job-high/analyse", headers=h)
    assert r.status_code == 202, r.text
    tid = r.json()["thread_id"]
    run = wait_status(api, h, tid, timeout=120)
    assert run["status"] in ("interrupted", "done"), run
    events = {e["event"] for e in api.get(f"/api/runs/{tid}/events", headers=h).json()}
    assert {"node_start", "node_end", "done"} <= events
    detail = api.get("/api/jobs/job-high", headers=h).json()
    assert detail["analysis"]["fit"] is not None
    if run["status"] == "interrupted":
        p = api.get(f"/api/proposals/{tid}", headers=h).json()
        assert p["pending_approval"]["payload"]["draft"]["cover_letter"]
        api.post(f"/api/proposals/{tid}/approve", headers=h, json={})
        done = wait_status(api, h, tid, statuses=("done", "error"), timeout=60)
        assert done["status"] == "done", done
        assert len(api.port.submissions) == 1
