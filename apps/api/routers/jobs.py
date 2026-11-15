"""Job inbox (ranked by fit), detail, skip and analyse."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.security import get_current_user
from ..db import InboxItem, Run, User, get_db, utcnow
from ..deps import marketplace_token, trace_id, user_settings
from ..graphs import get_snapshot, runtime, thread_config
from ..schemas import AnalyseOut, InboxItemOut, InboxOut, JobDetailOut, OkOut, SkipIn, StateViewOut
from ..services import marketplace
from ..services.fit import quick_fit
from ..services.runs import GraphUnavailable, queue_pending, start_bid_run, state_view

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def item_out(it: InboxItem) -> InboxItemOut:
    j = it.job or {}
    return InboxItemOut(
        job_id=it.job_id, title=j.get("title", ""), category=j.get("category", ""),
        skills_required=j.get("skills_required", []) or [], budget_type=j.get("budget_type", "fixed"),
        budget_min=j.get("budget_min"), budget_max=j.get("budget_max"), posted_at=j.get("posted_at"),
        proposals_count=j.get("proposals_count"), connects_cost=j.get("connects_cost"),
        fit_score=it.fit_score, recommended_action=it.recommended_action if it.recommended_action in
        ("bid", "watch", "skip") else "watch", risk_level=it.risk_level if it.risk_level in
        ("low", "medium", "high") else "low",
        risk_flags=[{"code": f.get("code", "?"), "severity": f.get("severity"), "evidence": f.get("evidence", "")}
                    for f in (it.risk_flags or [])],
        price=it.price, status=it.status, thread_id=it.thread_id,
        analysed=it.status in ("analysed", "drafted", "submitted"))


def upsert_jobs(db: Session, user: User, jobs: list[dict]) -> int:
    st = user_settings(user).model_dump()
    existing = {i.job_id: i for i in db.scalars(select(InboxItem).where(InboxItem.user_id == user.id))}
    n = 0
    for job in jobs:
        jid = job.get("id")
        if not jid:
            continue
        it = existing.get(jid)
        if it is None:
            q = quick_fit(job, user.persona, st)
            it = InboxItem(user_id=user.id, job_id=jid, job=job, **q)
            db.add(it)
            n += 1
        else:
            it.job = job
            if it.status == "new":
                q = quick_fit(job, user.persona, st)
                for k, v in q.items():
                    setattr(it, k, v)
            it.fetched_at = utcnow()
    db.commit()
    return n


@router.get("", response_model=InboxOut)
async def inbox(response: Response, refresh: bool = True,
                action: Optional[Literal["bid", "watch", "skip"]] = None,
                risk: Optional[Literal["low", "medium", "high"]] = None,
                min_fit: float = Query(0.0, ge=0, le=1), q: str = "", category: Optional[str] = None,
                include_skipped: bool = False, limit: int = Query(50, ge=1, le=200),
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mp_ok = (await marketplace.ping())["ok"]
    refreshed = False
    if refresh and mp_ok:
        st = user_settings(user)
        try:
            data = await marketplace.list_jobs(marketplace_token(db, user), q=q, category=category,
                                               limit=min(limit * 2, 200))
            upsert_jobs(db, user, data.get("jobs", []))
            refreshed = True
        except marketplace.MarketplaceUnavailable:
            mp_ok = False
        _ = st
    rows = list(db.scalars(select(InboxItem).where(InboxItem.user_id == user.id)))
    out = []
    for it in rows:
        if not include_skipped and it.status == "skipped":
            continue
        if action and it.recommended_action != action:
            continue
        if risk and it.risk_level != risk:
            continue
        if it.fit_score < min_fit:
            continue
        if category and (it.job or {}).get("category") != category:
            continue
        if q and q.lower() not in f"{(it.job or {}).get('title', '')} {(it.job or {}).get('description', '')}".lower():
            continue
        out.append(it)
    risk_rank = {"low": 0, "medium": 1, "high": 2}
    # ranked by fit; high-risk (scam / injection) jobs sink below the rest but stay visible with a badge
    out.sort(key=lambda i: (i.risk_level == "high", -i.fit_score, risk_rank.get(i.risk_level, 0), i.job_id))
    if not mp_ok:
        response.headers["X-Marketplace"] = "unavailable"
    return InboxOut(items=[item_out(i) for i in out[:limit]], total=len(out),
                    marketplace="ok" if mp_ok else "unavailable", refreshed=refreshed)


def _get_item(db: Session, user: User, job_id: str) -> InboxItem | None:
    return db.scalar(select(InboxItem).where(InboxItem.user_id == user.id, InboxItem.job_id == job_id))


@router.get("/{job_id}", response_model=JobDetailOut)
async def job_detail(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    it = _get_item(db, user, job_id)
    job = it.job if it else None
    client = None
    token = marketplace_token(db, user)
    try:
        if job is None:
            job = await marketplace.get_job(token, job_id)
            upsert_jobs(db, user, [job])
            it = _get_item(db, user, job_id)
        if job.get("client_id"):
            client = await marketplace.get_client_history(token, job["client_id"])
    except marketplace.MarketplaceUnavailable:
        if job is None:
            raise HTTPException(503, "Marketplace unavailable and job not cached")
    run = db.scalar(select(Run).where(Run.user_id == user.id, Run.job_id == job_id, Run.kind == "bid"))
    analysis = None
    if run and runtime.bid_graph is not None:
        snap = await get_snapshot(runtime.bid_graph, thread_config(run.thread_id, user.id, run.trace_id, user.persona))
        analysis = StateViewOut(**state_view(snap.values if snap else {}))
    return JobDetailOut(job=job, inbox=item_out(it) if it else None, client=client, analysis=analysis,
                        run_status=run.status if run else None, thread_id=run.thread_id if run else None)


@router.post("/{job_id}/skip", response_model=OkOut)
def skip(job_id: str, body: SkipIn | None = None, user: User = Depends(get_current_user),
         db: Session = Depends(get_db)):
    it = _get_item(db, user, job_id)
    if it is None:
        raise HTTPException(404, "Job not in inbox")
    it.status = "skipped"
    it.skip_reason = (body.reason if body else None) or "user_skip"
    db.commit()
    return OkOut(detail="skipped")


@router.post("/{job_id}/analyse", response_model=AnalyseOut, status_code=202)
async def analyse(job_id: str, request: Request, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    tid = trace_id(request)
    if runtime.bid_graph is None:
        raise HTTPException(503, f"Agent graph unavailable: {runtime.errors.get('bid_graph', '')}"[:300])
    existing = db.scalar(select(Run).where(Run.user_id == user.id, Run.job_id == job_id, Run.kind == "bid"))
    if existing:
        return AnalyseOut(thread_id=existing.thread_id, status=existing.status, created=False,
                          stream_url=f"/api/runs/{existing.thread_id}/stream", trace_id=existing.trace_id)
    it = _get_item(db, user, job_id)
    job = it.job if it else None
    if not (await marketplace.ping())["ok"]:
        queue_pending(db, user.id, "analyse", {"job_id": job_id, "trace_id": tid})
        if it:
            it.status = "queued"
            db.commit()
        return AnalyseOut(status="queued_degraded", queued_degraded=True, trace_id=tid)
    if job is None:
        try:
            job = await marketplace.get_job(marketplace_token(db, user), job_id)
        except marketplace.MarketplaceUnavailable:
            queue_pending(db, user.id, "analyse", {"job_id": job_id, "trace_id": tid})
            return AnalyseOut(status="queued_degraded", queued_degraded=True, trace_id=tid)
        upsert_jobs(db, user, [job])
    try:
        run, created = start_bid_run(db, user, job, tid)
    except GraphUnavailable as e:
        raise HTTPException(503, str(e)[:300])
    return AnalyseOut(thread_id=run.thread_id, status=run.status, created=created,
                      stream_url=f"/api/runs/{run.thread_id}/stream", trace_id=run.trace_id)
