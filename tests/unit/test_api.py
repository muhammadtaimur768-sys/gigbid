"""TestClient tests for the GigBid API: auth, inbox ranking, run start, approve/edit/reject,
pending approval surviving refresh (read from checkpoint), SSE, degraded mode, memory viewer."""
from __future__ import annotations

import pytest
from test_api_support import client_fixture, login, wait_status


@pytest.fixture
def api(tmp_path, monkeypatch):
    yield from client_fixture(tmp_path, monkeypatch)


def test_login_cookie_and_bearer(api):
    bad = api.post("/api/auth/login", json={"email": "reviewer@gigbid.app", "password": "wrong-password"})
    assert bad.status_code == 401
    r = api.post("/api/auth/login", json={"email": "reviewer@gigbid.app", "password": "review-gigbid-2026"})
    assert r.status_code == 200
    assert "gigbid_session" in r.cookies
    assert r.headers.get("x-trace-id")
    me = api.get("/api/auth/me")  # cookie
    assert me.status_code == 200 and me.json()["persona"] == "aiml"
    token = r.json()["access_token"]
    api.cookies.clear()
    assert api.get("/api/auth/me").status_code == 401
    assert api.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_register_and_onboarding(api):
    r = api.post("/api/auth/register", json={"email": "new@example.com", "password": "longpassword1"})
    assert r.status_code == 201
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert api.post("/api/auth/register", json={"email": "new@example.com", "password": "longpassword1"}
                    ).status_code == 409
    ob = api.put("/api/auth/onboarding", headers=h, json={
        "persona": "data", "rates": {"hourly_floor": 30, "hourly_target": 55},
        "budgets": {"weekly_connects": 60}, "filters": {"categories": ["data"]}})
    assert ob.status_code == 200
    body = ob.json()
    assert body["onboarded"] and body["persona"] == "data"
    assert body["settings"]["budgets"]["weekly_connects"] == 60
    conn = api.post("/api/auth/marketplace", headers=h, json={"mode": "gigsim"})
    assert conn.status_code == 200 and conn.json()["mode"] == "gigsim"
    st = api.get("/api/settings", headers=h).json()
    assert any(a["provider"] == "gigsim" and a["connected"] for a in st["accounts"])


def test_inbox_ranked_by_fit(api):
    h = login(api)
    r = api.get("/api/jobs", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["marketplace"] == "ok" and data["total"] == 3
    ids = [i["job_id"] for i in data["items"]]
    assert ids[0] == "job-high" and ids[-1] == "job-low"
    scores = [i["fit_score"] for i in data["items"]]
    assert scores == sorted(scores, reverse=True)
    assert api.post("/api/jobs/job-low/skip", headers=h, json={"reason": "off profile"}).status_code == 200
    assert "job-low" not in [i["job_id"] for i in api.get("/api/jobs", headers=h).json()["items"]]


def _start(api, h, job_id="job-high"):
    api.get("/api/jobs", headers=h)
    r = api.post(f"/api/jobs/{job_id}/analyse", headers=h)
    assert r.status_code == 202, r.text
    tid = r.json()["thread_id"]
    run = wait_status(api, h, tid)
    assert run["status"] == "interrupted", run
    return tid


def test_start_run_is_idempotent_and_streams(api):
    h = login(api)
    tid = _start(api, h)
    again = api.post("/api/jobs/job-high/analyse", headers=h).json()
    assert again["thread_id"] == tid and again["created"] is False
    events = [e["event"] for e in api.get(f"/api/runs/{tid}/events", headers=h).json()]
    for ev in ("node_start", "node_end", "progress", "interrupt", "done"):
        assert ev in events, events
    with api.stream("GET", f"/api/runs/{tid}/stream", headers=h) as s:
        body = ""
        for line in s.iter_lines():
            body += line + "\n"
            if line.startswith("event: done"):
                break
    assert "event: interrupt" in body and "event: node_end" in body


def test_pending_approval_survives_refresh_and_approve(api):
    h = login(api)
    tid = _start(api, h)
    for _ in range(2):  # a page refresh re-reads the interrupt from checkpoint state
        p = api.get(f"/api/proposals/{tid}", headers=h).json()
        assert p["pending_approval"]["payload"]["draft"]["cover_letter"].startswith("I built")
    r = api.post(f"/api/proposals/{tid}/approve", headers=h, json={})
    assert r.status_code == 200, r.text
    run = wait_status(api, h, tid, statuses=("done", "error"))
    assert run["status"] == "done" and run["outcome"] == "submitted"
    p = api.get(f"/api/proposals/{tid}", headers=h).json()
    assert p["pending_approval"] is None
    assert p["view"]["submission"]["proposal_id"] == "p-job-high"
    assert api.post(f"/api/proposals/{tid}/approve", headers=h, json={}).status_code == 409
    board = api.get("/api/pipeline", headers=h).json()
    assert any(c["job_id"] == "job-high" for c in board["columns"]["submitted"])


def test_reject_stores_reason(api):
    h = login(api)
    tid = _start(api, h)
    assert api.post(f"/api/proposals/{tid}/reject", headers=h, json={}).status_code == 422
    r = api.post(f"/api/proposals/{tid}/reject", headers=h, json={"reason": "Price too low"})
    assert r.status_code == 200
    run = wait_status(api, h, tid, statuses=("done", "error"))
    assert run["outcome"] == "rejected"
    p = api.get(f"/api/proposals/{tid}", headers=h).json()
    assert p["history"][-1]["action"] == "reject" and p["history"][-1]["reason"] == "Price too low"
    a = api.get("/api/analytics", headers=h).json()
    assert a["top_rejection_reasons"][0] == {"reason": "price too low", "count": 1}


def test_edit_diffs_and_feeds_memory(api):
    h = login(api)
    tid = _start(api, h)
    edited = "I shipped a LangGraph RAG system for a fintech client.\n\nI can start Monday."
    r = api.post(f"/api/proposals/{tid}/edit", headers=h, json={"edited_text": edited})
    assert r.status_code == 200, r.text
    assert r.json()["memory"] is not None
    wait_status(api, h, tid, statuses=("done", "error"))
    p = api.get(f"/api/proposals/{tid}", headers=h).json()
    diff = p["history"][-1]["diff"]
    assert diff["opening_changed"] is True and diff["length_delta"] > 0
    assert p["view"]["submission"]["cover_letter"] == edited
    mem = api.get("/api/settings/memory", headers=h).json()
    assert mem["available"]
    if mem["items"]:
        it = mem["items"][0]
        d = api.request("DELETE", "/api/settings/memory", headers=h,
                        json={"namespace": it["namespace"], "key": it["key"]})
        assert d.status_code == 200
        other = api.request("DELETE", "/api/settings/memory", headers=h,
                            json={"namespace": ["style", "someone-else"], "key": "x"})
        assert other.status_code == 404


def test_health_degraded_and_queued_work(api):
    from apps.api.services import marketplace
    h = login(api)
    api.get("/api/jobs", headers=h)
    ok = api.get("/api/health").json()
    assert ok["marketplace"] == "ok" and ok["status"] == "ok"
    marketplace.force_status(False)
    deg = api.get("/api/health").json()
    assert deg["marketplace"] == "unavailable" and deg["status"] == "degraded"
    inbox = api.get("/api/jobs", headers=h).json()
    assert inbox["marketplace"] == "unavailable" and inbox["total"] == 3  # served from cache
    q = api.post("/api/jobs/job-mid/analyse", headers=h).json()
    assert q["queued_degraded"] is True
    assert api.get("/api/health").json()["pending_work"] == 1
    marketplace.force_status(True)
    rec = api.get("/api/health").json()  # recovery retries queued work
    assert rec["pending_work"] == 0
    runs = api.get("/api/runs", headers=h).json()
    assert any(r["job_id"] == "job-mid" for r in runs)


def test_saved_search_and_cron(api):
    h = login(api)
    r = api.post("/api/settings/searches", headers=h, json={"name": "rag", "skills": ["rag"],
                                                             "interval_minutes": 5})
    assert r.status_code == 201
    out = api.post("/api/cron/scout").json()
    assert out["searches_run"] >= 1 and out["jobs_seen"] == 3


def test_upwork_oauth_not_configured(api, monkeypatch):
    monkeypatch.delenv("UPWORK_CLIENT_ID", raising=False)
    from apps.api import config
    config.get_settings.cache_clear()
    h = login(api)
    r = api.get("/api/oauth/upwork/start", headers=h).json()
    assert r["configured"] is False and "not configured" in r["detail"]


def test_tenant_scoping(api):
    h = login(api)
    tid = _start(api, h)
    other = api.post("/api/auth/register", json={"email": "other@example.com", "password": "longpassword1"})
    h2 = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert api.get(f"/api/proposals/{tid}", headers=h2).status_code == 404
    assert api.get(f"/api/runs/{tid}", headers=h2).status_code == 404
