"""Run list/detail, persisted events, live SSE stream and per-run trace."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from ..auth.security import get_current_user
from ..config import get_settings
from ..db import Run, RunEvent, User, get_db, get_engine
from ..graphs import runtime, thread_config
from ..integrations import optional
from ..schemas import PendingApprovalOut, RunDetailOut, RunEventOut, RunOut, TraceEventOut, TraceOut
from ..services.runs import execute, pending_interrupts, retry_pending
from ..streaming import sse_events

router = APIRouter(prefix="/api/runs", tags=["runs"])


def trace_url(trace_id: str) -> str | None:
    if os.getenv("LANGSMITH_API_KEY") and os.getenv("LANGSMITH_TRACE_URL_TEMPLATE"):
        return os.environ["LANGSMITH_TRACE_URL_TEMPLATE"].format(trace_id=trace_id)
    return None


def run_out(r: Run) -> RunOut:
    return RunOut(thread_id=r.thread_id, kind=r.kind, job_id=r.job_id, status=r.status, outcome=r.outcome,
                  trace_id=r.trace_id, trace_url=trace_url(r.trace_id) or f"/api/runs/{r.thread_id}/trace",
                  error=r.error, attempts=r.attempts, created_at=r.created_at, updated_at=r.updated_at)


def own(db: Session, user: User, thread_id: str) -> Run:
    r = db.get(Run, thread_id)
    if r is None or r.user_id != user.id:
        raise HTTPException(404, "Run not found")
    return r


@router.get("", response_model=list[RunOut])
def list_runs(status: str | None = None, kind: str | None = None, limit: int = Query(50, ge=1, le=500),
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Run).where(Run.user_id == user.id)
    if status:
        q = q.where(Run.status == status)
    if kind:
        q = q.where(Run.kind == kind)
    return [run_out(r) for r in db.scalars(q.order_by(Run.created_at.desc()).limit(limit))]


@router.post("/retry-pending")
async def retry(user: User = Depends(get_current_user)):
    return await retry_pending()


@router.get("/{thread_id}", response_model=RunDetailOut)
async def run_detail(thread_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = own(db, user, thread_id)
    events = db.scalars(select(RunEvent).where(RunEvent.thread_id == thread_id, RunEvent.user_id == user.id)
                        .order_by(RunEvent.id))
    pending = None
    graph = runtime.graph_for(r.kind)
    if graph is not None and r.status not in ("queued", "running"):
        snap = await graph.aget_state(thread_config(thread_id, user.id, r.trace_id, user.persona))
        intr = pending_interrupts(snap)
        if intr:
            pending = PendingApprovalOut(interrupt_id=intr[0]["id"], payload=intr[0]["value"])
    base = run_out(r).model_dump()
    return RunDetailOut(**base, events=[RunEventOut(id=e.id, event=e.event, data=e.data, ts=e.ts) for e in events],
                        pending_approval=pending)


@router.get("/{thread_id}/events", response_model=list[RunEventOut])
def run_events(thread_id: str, after: int = 0, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    own(db, user, thread_id)
    rows = db.scalars(select(RunEvent).where(RunEvent.thread_id == thread_id, RunEvent.user_id == user.id,
                                             RunEvent.id > after).order_by(RunEvent.id))
    return [RunEventOut(id=e.id, event=e.event, data=e.data, ts=e.ts) for e in rows]


@router.get("/{thread_id}/stream", response_class=EventSourceResponse,
            responses={200: {"content": {"text/event-stream": {}},
                             "description": "SSE: node_start, node_end, token, progress, interrupt, error, done"}})
async def stream(thread_id: str, request: Request, after: int = 0,
                 last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = own(db, user, thread_id)
    start_after = after
    if last_event_id and last_event_id.isdigit():
        start_after = max(start_after, int(last_event_id))
    user_id = user.id
    drive = get_settings().run_mode == "stream" and r.status in ("queued", "pending_retry")

    async def gen():
        if drive:
            import asyncio
            task = asyncio.create_task(execute(thread_id))
            async for ev in sse_events(thread_id, user_id, after=start_after):
                if await request.is_disconnected():
                    break
                yield ev
            await task
            return
        async for ev in sse_events(thread_id, user_id, after=start_after):
            if await request.is_disconnected():
                break
            yield ev

    return EventSourceResponse(gen(), ping=15, headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@router.get("/{thread_id}/trace", response_model=TraceOut)
def run_trace(thread_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = own(db, user, thread_id)
    events: list[TraceEventOut] = []
    available = True
    shared = optional("agent.tracing", "get_trace_events")
    if shared is not None:
        try:
            for row in shared(thread_id=thread_id):
                events.append(TraceEventOut(node=row.get("node"), event=row.get("event"),
                                            tokens_in=row.get("tokens_in"), tokens_out=row.get("tokens_out"),
                                            cost_usd=row.get("cost_usd"), latency_ms=row.get("latency_ms"),
                                            ts=str(row.get("ts")), payload=row.get("payload")))
            return TraceOut(trace_id=r.trace_id, thread_id=thread_id, events=events,
                            langsmith_url=trace_url(r.trace_id), available=True)
        except Exception:
            events = []
    try:
        with get_engine().connect() as conn:
            rows = conn.execute(text(
                "SELECT node, event, tokens_in, tokens_out, cost_usd, latency_ms, ts, payload_json "
                "FROM trace_events WHERE thread_id = :t ORDER BY ts"), {"t": thread_id}).mappings().all()
        for row in rows:
            events.append(TraceEventOut(node=row["node"], event=row["event"], tokens_in=row["tokens_in"],
                                        tokens_out=row["tokens_out"], cost_usd=row["cost_usd"],
                                        latency_ms=row["latency_ms"], ts=str(row["ts"]),
                                        payload=row["payload_json"]))
    except Exception:
        available = False
    return TraceOut(trace_id=r.trace_id, thread_id=thread_id, events=events, langsmith_url=trace_url(r.trace_id),
                    available=available)
