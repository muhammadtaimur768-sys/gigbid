"""Scout tick: run due saved searches, upsert inbox, auto-analyse under autopilot, retry queued work.
Called by Vercel Cron / an external scheduler; the Arq worker runs the same function on its own cron."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select

from ..config import cfg, get_settings
from ..db import InboxItem, SavedSearch, SessionLocal, User, utcnow
from ..deps import marketplace_token, user_settings
from ..schemas import CronOut
from ..services import marketplace
from ..services.runs import GraphUnavailable, retry_pending, start_bid_run

router = APIRouter(prefix="/api/cron", tags=["cron"])


async def scout_search(search_id: int, trace_id: str = "", force: bool = False) -> dict:
    from .jobs import upsert_jobs
    db = SessionLocal()
    try:
        s = db.get(SavedSearch, search_id)
        if s is None or not s.enabled:
            return {"ran": False, "jobs": 0, "runs": 0}
        if not force and s.last_run_at and utcnow() - s.last_run_at < dt.timedelta(minutes=s.interval_minutes):
            return {"ran": False, "jobs": 0, "runs": 0}
        user = db.get(User, s.user_id)
        data = await marketplace.list_jobs(marketplace_token(db, user), q=s.query, category=s.category,
                                           skills=s.skills or None, limit=50)
        jobs = data.get("jobs", [])
        upsert_jobs(db, user, jobs)
        s.last_run_at = utcnow()
        db.commit()
        runs = 0
        if user_settings(user).autonomy == "autopilot":
            cap = int(cfg("autonomy.max_auto_analyses_per_tick", 5))
            fit_bid = float(cfg("thresholds.fit_bid", 0.6))
            items = db.scalars(select(InboxItem).where(InboxItem.user_id == user.id, InboxItem.status == "new",
                                                       InboxItem.fit_score >= fit_bid)
                               .order_by(InboxItem.fit_score.desc()).limit(cap))
            for it in items:
                try:
                    _, created = start_bid_run(db, user, it.job, trace_id)
                    runs += int(created)
                except GraphUnavailable:
                    break
        return {"ran": True, "jobs": len(jobs), "runs": runs}
    finally:
        db.close()


async def scout_all(trace_id: str = "") -> CronOut:
    ok = (await marketplace.ping(force=True))["ok"]
    if not ok:
        return CronOut(searches_run=0, jobs_seen=0, runs_started=0, retried=0, marketplace="unavailable")
    db = SessionLocal()
    try:
        ids = [s.id for s in db.scalars(select(SavedSearch).where(SavedSearch.enabled.is_(True)))]
    finally:
        db.close()
    ran = seen = started = 0
    for sid in ids:
        try:
            r = await scout_search(sid, trace_id)
        except marketplace.MarketplaceUnavailable:
            break
        ran += int(r["ran"])
        seen += r["jobs"]
        started += r["runs"]
    retried = (await retry_pending())["retried"]
    return CronOut(searches_run=ran, jobs_seen=seen, runs_started=started, retried=retried, marketplace="ok")


def _check(authorization: str | None, x_cron_key: str | None) -> None:
    secret = get_settings().cron_secret
    if secret and authorization != f"Bearer {secret}" and x_cron_key != secret:
        raise HTTPException(401, "Invalid cron credentials")


@router.get("/scout", response_model=CronOut, name="cron_scout_get")
async def cron_scout_get(request: Request, authorization: str | None = Header(default=None),
                         x_cron_key: str | None = Header(default=None)):
    """GET variant for Vercel Cron (sends Authorization: Bearer $CRON_SECRET)."""
    _check(authorization, x_cron_key)
    return await scout_all(getattr(request.state, "trace_id", ""))


@router.post("/scout", response_model=CronOut)
async def cron_scout(request: Request, authorization: str | None = Header(default=None),
                     x_cron_key: str | None = Header(default=None)):
    _check(authorization, x_cron_key)
    return await scout_all(getattr(request.state, "trace_id", ""))
