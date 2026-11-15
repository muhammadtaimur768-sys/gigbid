"""Worker idempotency: run_bid_job analyses a (user, job_id) once even if the task is retried."""
from __future__ import annotations

from sqlalchemy import func, select
import pytest
from test_api_support import client_fixture, login


@pytest.fixture
def api(tmp_path, monkeypatch):
    yield from client_fixture(tmp_path, monkeypatch)


def test_run_bid_job_idempotent(api):
    from apps.api.db import JobAnalysis, Run, SessionLocal, User
    from worker.settings import WorkerSettings, run_bid_job
    login(api)
    db = SessionLocal()
    uid = db.scalar(select(User.id).where(User.email == "reviewer@gigbid.app"))
    db.close()
    first = api.portal.call(run_bid_job, {}, uid, "job-high", "workertrace01")
    assert first["created"] is True and first["status"] == "interrupted"
    second = api.portal.call(run_bid_job, {}, uid, "job-high", "workertrace01")  # retry / restart
    assert second["created"] is False and second["thread_id"] == first["thread_id"]
    db = SessionLocal()
    assert db.scalar(select(func.count()).select_from(JobAnalysis).where(JobAnalysis.user_id == uid)) == 1
    assert db.get(Run, first["thread_id"]).attempts == 1
    db.close()
    names = {f.__name__ for f in WorkerSettings.functions}
    assert {"run_bid_job", "execute_run", "scout_search"} <= names
    assert any(c.name == "scout:tick" for c in WorkerSettings.cron_jobs)
