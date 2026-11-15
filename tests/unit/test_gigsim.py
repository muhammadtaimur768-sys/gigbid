"""GigSim API tests: idempotency, dry_run, rate limiting, tick and policy update."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

AIML = {"Authorization": "Bearer gs-aiml-token"}
DATA = {"Authorization": "Bearer gs-data-token"}
ADMIN = {"X-Admin-Key": "gigsim-admin"}

LETTER = ("Your post needs a document assistant with citations. Last year I built a RAG assistant over claims PDFs for an insurer, "
          "using LangChain and a vector store, and evaluated it on a held-out set. First milestone: a working chatbot with source "
          "citations on a sample of your documents, then an evaluation report. Happy to do a short call to go through the plan.")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GIGSIM_DATABASE_URL", f"sqlite:///{tmp_path / 'gigsim.db'}")
    monkeypatch.setenv("GIGSIM_ERROR_RATE", "0")
    monkeypatch.setenv("GIGSIM_POLICY_UPDATE", "1")
    monkeypatch.delenv("GIGSIM_RATE_LIMIT", raising=False)
    from gigsim import app as gs_app

    gs_app.reset_rate_limits()
    gs_app._stats_cache.clear()
    with TestClient(gs_app.app) as c:
        yield c
    gs_app.reset_rate_limits()


def open_job(c, category="AI & Machine Learning", old=True):
    jobs = c.get("/jobs", params={"category": category, "limit": 200}, headers=AIML).json()["jobs"]
    now = c.get("/health").json()["sim_now"]
    for j in jobs:
        if (j["posted_at"] < now[:11] + "07:00:00Z") == old:
            return j
    return jobs[0]


def test_health_and_auth(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/jobs").status_code == 401
    assert client.get("/jobs", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_jobs_hide_hidden_fields(client):
    r = client.get("/jobs", headers=AIML).json()
    assert r["total"] >= 100 and len(r["jobs"]) == 50
    for j in r["jobs"]:
        assert not {"hidden", "is_scam", "has_injection", "prefs"} & set(j)
    job = client.get(f"/jobs/{r['jobs'][0]['id']}", headers=AIML).json()
    assert "prefs" not in job and job["id"] == r["jobs"][0]["id"]


def test_market_stats(client):
    s = client.get("/market/stats", params={"category": "Data Analytics"}, headers=AIML).json()
    assert s["n"] > 100 and s["hourly"]["p25"] <= s["hourly"]["p50"] <= s["hourly"]["p75"]


def test_dry_run_changes_nothing(client):
    job = open_job(client)
    before = client.get("/connects", headers=AIML).json()
    r = client.post("/proposals", json={"job_id": job["id"], "cover_letter": LETTER, "bid_amount": 70, "dry_run": True}, headers=AIML)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["would_send"]["job_id"] == job["id"]
    assert body["balance_after"] == before["balance"] - body["connects_cost"]
    assert client.get("/connects", headers=AIML).json() == before
    assert all(p["job_id"] != job["id"] for p in client.get("/proposals", headers=AIML).json())


def test_idempotent_submit_does_not_double_spend(client):
    job = open_job(client)
    before = client.get("/connects", headers=AIML).json()["balance"]
    payload = {"job_id": job["id"], "cover_letter": LETTER, "bid_amount": 70, "idempotency_key": "idem-123"}
    r1 = client.post("/proposals", json=payload, headers=AIML)
    r2 = client.post("/proposals", json=payload, headers=AIML)
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()
    assert r2.headers.get("Idempotent-Replay") == "true"
    after = client.get("/connects", headers=AIML).json()["balance"]
    assert after == before - r1.json()["connects_spent"]
    assert sum(p["job_id"] == job["id"] for p in client.get("/proposals", headers=AIML).json()) == 1
    # same key, different body -> conflict; new key on same job -> already applied
    assert client.post("/proposals", json={**payload, "bid_amount": 99}, headers=AIML).status_code == 409
    assert client.post("/proposals", json={**payload, "idempotency_key": "idem-456"}, headers=AIML).json()["error"] == "already_applied"


def test_idempotency_key_required(client):
    job = open_job(client)
    r = client.post("/proposals", json={"job_id": job["id"], "cover_letter": LETTER, "bid_amount": 70}, headers=AIML)
    assert r.status_code == 422


def test_policy_update_length_and_surcharge(client):
    job = open_job(client)
    r = client.post("/proposals", json={"job_id": job["id"], "cover_letter": "x" * 2501, "bid_amount": 70, "dry_run": True}, headers=AIML)
    assert r.status_code == 422 and r.json()["error"] == "proposal_too_long"
    # a freshly released job (posted < 60 min before sim time) costs +2 connects
    tick = client.post("/admin/tick", headers=ADMIN).json()
    fresh = client.get(f"/jobs/{tick['released'][0]}", headers=AIML).json()
    d = client.post("/proposals", json={"job_id": fresh["id"], "cover_letter": LETTER, "bid_amount": 70, "dry_run": True}, headers=AIML).json()
    assert d["surcharge"] == 2 and d["connects_cost"] == fresh["connects_cost"] + 2


def test_rate_limit_returns_429_with_retry_after(client, monkeypatch):
    monkeypatch.setenv("GIGSIM_RATE_LIMIT", "60")
    codes = [client.get("/connects", headers=DATA).status_code for _ in range(61)]
    assert codes[:60] == [200] * 60
    assert codes[60] == 429
    r = client.get("/connects", headers=DATA)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    # limits are per token
    assert client.get("/connects", headers=AIML).status_code == 200


def test_error_injection(client, monkeypatch):
    monkeypatch.setenv("GIGSIM_ERROR_RATE", "1")
    assert client.get("/connects", headers=AIML).status_code == 503
    monkeypatch.setenv("GIGSIM_ERROR_RATE", "0")
    assert client.get("/connects", headers=AIML).status_code == 200


def test_tick_releases_jobs_and_advances_proposals(client):
    assert client.post("/admin/tick").status_code == 403
    total0 = client.get("/jobs", headers=AIML).json()["total"]
    job = open_job(client)
    pid = client.post("/proposals", json={"job_id": job["id"], "cover_letter": LETTER, "bid_amount": 60, "idempotency_key": "tick-1"},
                      headers=AIML).json()["proposal_id"]
    t1 = client.post("/admin/tick", headers=ADMIN).json()
    assert t1["tick"] == 1 and len(t1["released"]) == 20
    assert client.get("/jobs", headers=AIML).json()["total"] == total0 + 20
    status = {p["proposal_id"]: p["status"] for p in client.get("/proposals", headers=AIML).json()}
    assert status[pid] == "viewed"
    for _ in range(3):
        client.post("/admin/tick", headers=ADMIN)
    final = {p["proposal_id"]: p["status"] for p in client.get("/proposals", headers=AIML).json()}[pid]
    assert final in {"replied", "interview", "hired", "lost"}
    ev = client.get("/events", headers=AIML).json()
    assert any(e["type"] == "new_job" for e in ev)
    assert any(e["type"] == "proposal_status" and e["proposal_id"] == pid and e["status"] == "viewed" for e in ev)
    if final != "lost":
        threads = [t for t in client.get("/threads", headers=AIML).json() if t["proposal_id"] == pid]
        assert threads and client.get(f"/threads/{threads[0]['thread_id']}/messages", headers=AIML).json()[-1]["sender"] == "client"


def test_messages_idempotent(client):
    t = client.get("/threads", headers=AIML).json()[0]
    m1 = client.post(f"/threads/{t['thread_id']}/messages", json={"body": "Thursday 14:00 UTC works.", "idempotency_key": "msg-1"}, headers=AIML)
    m2 = client.post(f"/threads/{t['thread_id']}/messages", json={"body": "Thursday 14:00 UTC works.", "idempotency_key": "msg-1"}, headers=AIML)
    assert m1.json() == m2.json()
    msgs = client.get(f"/threads/{t['thread_id']}/messages", headers=AIML).json()
    assert sum(m["body"] == "Thursday 14:00 UTC works." for m in msgs) == 1
    assert client.get(f"/threads/{t['thread_id']}/messages", headers=DATA).status_code == 404


def test_insufficient_connects_402(client):
    jobs = client.get("/jobs", params={"limit": 200}, headers=AIML).json()["jobs"]
    letter = LETTER
    codes = []
    for i, j in enumerate(jobs):
        r = client.post("/proposals", json={"job_id": j["id"], "cover_letter": letter, "bid_amount": 50, "idempotency_key": f"k{i}"}, headers=AIML)
        codes.append(r.status_code)
        if r.status_code == 402:
            break
    assert 402 in codes


def test_score_proposal_is_pure_and_rewards_specificity():
    from gigsim.client_model import score_proposal

    a = score_proposal("d-aiml-002", LETTER, 50)
    assert a == score_proposal("d-aiml-002", LETTER, 50)
    generic = score_proposal("d-aiml-002", "Dear Sir, I am a passionate professional. I can do this job perfectly.", 50)
    assert generic["reply_prob"] <= a["reply_prob"]
    assert set(a) >= {"reply_prob", "replied", "hired"}
