"""Client threads, suggested replies (conversation graph) and approve-before-send."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.security import get_current_user
from ..db import Approval, Run, User, get_db
from ..deps import marketplace_token, trace_id
from ..graphs import runtime, thread_config
from ..schemas import (MessageOut, PendingApprovalOut, ReplyDecisionIn, ResumeOut, RunOut, ThreadDetailOut,
                       ThreadOut, ThreadsOut)
from ..services import marketplace
from ..services.memory import diff_texts, record_edit
from ..services.runs import GraphUnavailable, pending_interrupts, resume_run, start_conversation_run, state_view
from .runs import run_out

router = APIRouter(prefix="/api/messages", tags=["messages"])


def latest_conv_run(db: Session, user: User, mp_thread_id: str) -> Run | None:
    return db.scalar(select(Run).where(Run.user_id == user.id, Run.marketplace_thread_id == mp_thread_id,
                                       Run.kind == "conversation").order_by(Run.created_at.desc()))


@router.get("/threads", response_model=ThreadsOut)
async def threads(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        rows = await marketplace.list_threads(marketplace_token(db, user))
    except marketplace.MarketplaceUnavailable:
        return ThreadsOut(threads=[], marketplace="unavailable")
    pending = {r.marketplace_thread_id for r in db.scalars(select(Run).where(
        Run.user_id == user.id, Run.kind == "conversation", Run.status == "interrupted"))}
    out = [ThreadOut(thread_id=str(t.get("thread_id")), job_id=t.get("job_id"), client_id=t.get("client_id"),
                     proposal_id=t.get("proposal_id"), last_message_at=t.get("last_message_at"),
                     unread=t.get("unread") if isinstance(t.get("unread"), int) else int(bool(t.get("unread"))),
                     pending_reply=str(t.get("thread_id")) in pending) for t in rows]
    return ThreadsOut(threads=out, marketplace="ok")


@router.get("/threads/{mp_thread_id}", response_model=ThreadDetailOut)
async def thread_detail(mp_thread_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        msgs = await marketplace.list_messages(marketplace_token(db, user), mp_thread_id)
    except marketplace.MarketplaceUnavailable:
        raise HTTPException(503, "Marketplace unavailable")
    run = latest_conv_run(db, user, mp_thread_id)
    pending, reply = None, None
    if run and runtime.conversation_graph is not None:
        snap = await runtime.conversation_graph.aget_state(
            thread_config(run.thread_id, user.id, run.trace_id, user.persona))
        intr = pending_interrupts(snap)
        if intr:
            pending = PendingApprovalOut(interrupt_id=intr[0]["id"], payload=intr[0]["value"])
        reply = state_view(snap.values).get("reply")
    return ThreadDetailOut(
        thread_id=mp_thread_id,
        messages=[MessageOut(id=str(m.get("id")), sender=m.get("sender", ""), body=m.get("body", ""),
                             created_at=m.get("created_at")) for m in msgs],
        suggestion_run=run.thread_id if run else None, suggestion_status=run.status if run else None,
        pending_approval=pending, reply=reply)


@router.post("/threads/{mp_thread_id}/suggest", response_model=RunOut, status_code=202)
async def suggest(mp_thread_id: str, request: Request, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    run = latest_conv_run(db, user, mp_thread_id)
    if run and run.status in ("queued", "running", "interrupted"):
        return run_out(run)
    try:
        run = start_conversation_run(db, user, mp_thread_id, trace_id(request))
    except GraphUnavailable as e:
        raise HTTPException(503, str(e)[:300])
    return run_out(run)


@router.post("/threads/{mp_thread_id}/decision", response_model=ResumeOut)
async def decide_reply(mp_thread_id: str, body: ReplyDecisionIn, request: Request,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    run = latest_conv_run(db, user, mp_thread_id)
    if run is None or runtime.conversation_graph is None:
        raise HTTPException(404, "No suggested reply for this thread")
    snap = await runtime.conversation_graph.aget_state(
        thread_config(run.thread_id, user.id, run.trace_id, user.persona))
    intr = pending_interrupts(snap)
    if not intr:
        raise HTTPException(409, "No pending reply approval")
    if body.action == "reject" and not (body.reason or "").strip():
        raise HTTPException(422, "A reason is required to reject")
    reply = state_view(snap.values).get("reply") or {}
    payload = intr[0]["value"] if isinstance(intr[0]["value"], dict) else {}
    original = (reply.get("body") if isinstance(reply, dict) else "") or \
        ((payload.get("reply") or {}).get("body") if isinstance(payload.get("reply"), dict) else payload.get("body", ""))
    diff = diff_texts(original or "", body.edited_text) if body.action == "edit" and body.edited_text else None
    appr = Approval(user_id=user.id, thread_id=run.thread_id, kind="conversation", action=body.action,
                    reason=body.reason, original_text=original, edited_text=body.edited_text, diff=diff)
    db.add(appr)
    db.commit()
    mem = await record_edit(runtime.store, user.id, original or "", body.edited_text or "",
                            {"thread_id": run.thread_id, "kind": "reply"}, graph_records=False) if diff else None
    decision = {"action": body.action, "edited_text": body.edited_text, "reason": body.reason,
                "user_id": user.id, "slot": body.slot}
    resume_run(db, run, decision, trace_id(request))
    return ResumeOut(thread_id=run.thread_id, status=run.status, action=body.action, approval_id=appr.id,
                     stream_url=f"/api/runs/{run.thread_id}/stream", memory=mem)
