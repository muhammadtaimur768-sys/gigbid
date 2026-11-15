"""Arq worker: scouting crons (one per saved search, plus a tick that picks up new searches) and
graph execution off the web request path. Idempotent: a job is analysed once per (user, job_id)
because start_bid_run inserts into job_analyses (UNIQUE(user_id, job_id)) before running, and a run
segment is claimed with a conditional UPDATE (queued -> running) so a restart never double-runs it.
Submission idempotency is the graph's idempotency key (hash(thread_id, version))."""
from __future__ import annotations

import logging
import os

from arq import cron
from arq.connections import RedisSettings

from apps.api.db import SavedSearch, SessionLocal, User, init_db
from apps.api.graphs import close_runtime, open_runtime

log = logging.getLogger("gigbid.worker")


async def startup(ctx: dict) -> None:
    import asyncio
    init_db()
    ctx["runtime"] = await asyncio.to_thread(open_runtime)


async def shutdown(ctx: dict) -> None:
    close_runtime()


async def execute_run(ctx: dict, thread_id: str) -> str:
    """Run one queued graph segment (start or resume) for thread_id."""
    from apps.api.services.runs import execute
    return await execute(thread_id)


async def run_bid_job(ctx: dict, user_id: str, job_id: str, trace_id: str = "") -> dict:
    """Analyse one job for one user. Safe to retry: the (user, job_id) unique constraint makes a second
    call return the existing thread instead of starting a new analysis."""
    from apps.api.deps import marketplace_token
    from apps.api.services import marketplace
    from apps.api.services.runs import execute, start_bid_run
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user is None:
            return {"status": "unknown_user"}
        job = await marketplace.get_job(marketplace_token(db, user), job_id)
        run, created = start_bid_run(db, user, job, trace_id, auto_dispatch=False)
        status = await execute(run.thread_id) if created or run.status == "queued" else run.status
        return {"thread_id": run.thread_id, "created": created, "status": status}
    finally:
        db.close()


async def scout_search(ctx: dict, search_id: int) -> dict:
    from apps.api.routers.cron import scout_search as _scout
    return await _scout(search_id)


async def scout_tick(ctx: dict) -> dict:
    """Runs every minute; each saved search is executed when its own interval_minutes has elapsed."""
    from apps.api.routers.cron import scout_all
    return (await scout_all()).model_dump()


async def retry_pending(ctx: dict) -> dict:
    from apps.api.services.runs import retry_pending as _retry
    return await _retry()


def _per_search_crons() -> list:
    """One Arq cron per saved search known at worker start (minute grid from its interval)."""
    jobs = []
    try:
        init_db()
        db = SessionLocal()
        try:
            searches = list(db.query(SavedSearch).filter(SavedSearch.enabled.is_(True)))
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        return jobs
    for s in searches:
        step = max(1, min(int(s.interval_minutes or 30), 59))
        minutes = set(range(s.id % step, 60, step))

        async def _job(ctx, _sid=s.id):
            from apps.api.routers.cron import scout_search as _scout
            return await _scout(_sid, force=True)
        _job.__qualname__ = _job.__name__ = f"scout_saved_search_{s.id}"
        jobs.append(cron(_job, minute=minutes, run_at_startup=False, unique=True, name=f"scout:{s.id}"))
    return jobs


class WorkerSettings:
    functions = [execute_run, run_bid_job, scout_search, retry_pending]
    cron_jobs = [cron(scout_tick, minute=set(range(0, 60, 5)), unique=True, name="scout:tick"),
                 cron(retry_pending, minute=set(range(1, 60, 2)), unique=True, name="retry:pending"),
                 *_per_search_crons()]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(os.getenv("REDIS_URL", "redis://localhost:6379"))
    max_jobs = int(os.getenv("WORKER_MAX_JOBS", "4"))
    job_timeout = int(os.getenv("WORKER_JOB_TIMEOUT", "600"))
    keep_result = 3600
