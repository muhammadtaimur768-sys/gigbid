"""Proposal studio (draft + pending approval from checkpoint state), approve/edit/reject via
Command(resume=...), paragraph regeneration, and the pipeline board."""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.security import get_current_user
from ..db import Approval, InboxItem, Proposal, Run, User, get_db
from ..deps import marketplace_token, trace_id
from ..graphs import get_snapshot, runtime, thread_config
from ..integrations import first_attr
from ..schemas import (ApprovalOut, ApproveIn, EditIn, PendingApprovalOut, PipelineCard, PipelineOut, ProposalOut,
                       RegenerateIn, RegenerateOut, RejectIn, ResumeOut, StateViewOut)
from ..services import marketplace
from ..services.memory import diff_texts, record_edit, record_outcome
from ..services.runs import pending_interrupts, resume_run, state_view

router = APIRouter(prefix="/api/proposals", tags=["proposals"])
pipeline_router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

COLUMNS = ["drafted", "submitted", "viewed", "replied", "interview", "hired", "lost"]


def own_run(db: Session, user: User, thread_id: str) -> Run:
    run = db.get(Run, thread_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(404, "Run not found")
    return run


async def snapshot(run: Run, user: User):
    graph = runtime.graph_for(run.kind)
    if graph is None:
        raise HTTPException(503, f"{run.kind} graph unavailable")
    return await get_snapshot(graph, thread_config(run.thread_id, user.id, run.trace_id, user.persona))


def approvals_for(db: Session, user: User, thread_id: str) -> list[ApprovalOut]:
    rows = db.scalars(select(Approval).where(Approval.user_id == user.id, Approval.thread_id == thread_id)
                      .order_by(Approval.id))
    return [ApprovalOut(id=a.id, thread_id=a.thread_id, action=a.action, reason=a.reason, diff=a.diff,
                        created_at=a.created_at) for a in rows]


def _draft_text(payload: Any, view: dict) -> str:
    for src in (payload, view):
        if not isinstance(src, dict):
            continue
        d = src.get("draft") or src.get("proposal")
        if isinstance(d, dict) and d.get("cover_letter"):
            return d["cover_letter"]
        if isinstance(d, str):
            return d
        if src.get("cover_letter"):
            return src["cover_letter"]
    return ""


@router.get("", response_model=list[PipelineCard])
def list_proposals(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Proposal).where(Proposal.user_id == user.id).order_by(Proposal.updated_at.desc()))
    return [_card(p) for p in rows]


@router.get("/{thread_id}", response_model=ProposalOut)
async def get_proposal(thread_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    run = own_run(db, user, thread_id)
    snap = await snapshot(run, user)
    intr = pending_interrupts(snap)
    pending = PendingApprovalOut(interrupt_id=intr[0]["id"], payload=intr[0]["value"]) if intr else None
    if intr and run.status not in ("interrupted", "queued", "running"):
        run.status = "interrupted"
        db.commit()
    return ProposalOut(thread_id=thread_id, job_id=run.job_id, run_status=run.status, pending_approval=pending,
                       view=StateViewOut(**state_view(snap.values if snap else {})),
                       history=approvals_for(db, user, thread_id), trace_id=run.trace_id)


async def _decide(request: Request, thread_id: str, user: User, db: Session, action: str,
                  edited_text: str | None = None, reason: str | None = None, extra: dict | None = None,
                  category: str | None = None) -> ResumeOut:
    run = own_run(db, user, thread_id)
    if run.status in ("queued", "running"):
        raise HTTPException(409, "Run is still executing")
    snap = await snapshot(run, user)
    intr = pending_interrupts(snap)
    if not intr:
        raise HTTPException(409, "No pending approval for this run")
    payload = intr[0]["value"]
    view = state_view(snap.values)
    original = _draft_text(payload, view)
    diff = diff_texts(original, edited_text) if action == "edit" and edited_text is not None else None
    job = view.get("job") or {}
    appr = Approval(user_id=user.id, thread_id=thread_id, kind=run.kind, action=action, reason=reason,
                    original_text=original, edited_text=edited_text, diff=diff,
                    category=category or (job.get("category") if isinstance(job, dict) else None))
    db.add(appr)
    db.commit()
    mem = None
    if diff is not None:
        mem = await record_edit(runtime.store, user.id, original, edited_text,
                                {"thread_id": thread_id, "job_id": run.job_id, "category": appr.category},
                                graph_records=True)
        mem["diff_ops"] = len(diff.get("ops", []))
    decision = {"action": action, "edited_text": edited_text, "reason": reason, "user_id": user.id}
    if extra:
        decision.update(extra)
    if action == "reject":
        prop = db.scalar(select(Proposal).where(Proposal.user_id == user.id, Proposal.job_id == run.job_id))
        if prop:
            prop.status = "rejected"
        item = db.scalar(select(InboxItem).where(InboxItem.user_id == user.id, InboxItem.job_id == run.job_id))
        if item:
            item.status, item.skip_reason = "skipped", f"rejected: {reason}"
        db.commit()
    resume_run(db, run, decision, trace_id(request))
    return ResumeOut(thread_id=thread_id, status=run.status, action=action, approval_id=appr.id,
                     stream_url=f"/api/runs/{thread_id}/stream", memory=mem)


@router.post("/{thread_id}/approve", response_model=ResumeOut)
async def approve(thread_id: str, request: Request, body: ApproveIn | None = None,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return await _decide(request, thread_id, user, db, "approve", reason=body.note if body else None)


@router.post("/{thread_id}/edit", response_model=ResumeOut)
async def edit(thread_id: str, body: EditIn, request: Request, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    extra = {"screening_answers": body.screening_answers} if body.screening_answers else None
    return await _decide(request, thread_id, user, db, "edit", edited_text=body.edited_text, extra=extra)


@router.post("/{thread_id}/reject", response_model=ResumeOut)
async def reject(thread_id: str, body: RejectIn, request: Request, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    reason = body.reason.strip()
    return await _decide(request, thread_id, user, db, "reject", reason=reason,
                         category=None, extra={"reason_category": body.category} if body.category else None)


def _paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", text or "") if p.strip()]


@router.post("/{thread_id}/regenerate", response_model=RegenerateOut)
async def regenerate(thread_id: str, body: RegenerateIn, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """Regenerate one paragraph of the pending draft without touching the others. The result is
    returned for the user to accept into the editor (then sent via /edit)."""
    run = own_run(db, user, thread_id)
    snap = await snapshot(run, user)
    intr = pending_interrupts(snap)
    view = state_view(snap.values)
    text = _draft_text(intr[0]["value"] if intr else None, view)
    paras = _paragraphs(text)
    if body.paragraph_index >= len(paras):
        raise HTTPException(422, f"Draft has {len(paras)} paragraphs")
    fn = first_attr("agent.nodes.writer", ["regenerate_paragraph", "rewrite_paragraph"])
    if fn is not None:
        res = fn(state=snap.values, paragraph_index=body.paragraph_index, instruction=body.instruction,
                 persona=user.persona or "aiml")
        if hasattr(res, "__await__"):
            res = await res
        new_para = res.get("paragraph") if isinstance(res, dict) else str(res)
        claims = res.get("claims", []) if isinstance(res, dict) else []
        source = f"{fn.__module__}.{fn.__name__}"
    else:
        writer = first_attr("agent.nodes.writer", ["writer"])
        if writer is None:
            raise HTTPException(503, "Paragraph regeneration unavailable (agent writer not loaded)")
        new_para, claims = await _regenerate_with_writer(writer, snap.values, body, paras)
        source = "agent.nodes.writer.writer"
    paras[body.paragraph_index] = new_para
    return RegenerateOut(paragraph_index=body.paragraph_index, paragraph=new_para,
                         cover_letter="\n\n".join(paras), claims=claims, source=source)


async def _regenerate_with_writer(writer, values: dict, body: RegenerateIn, paras: list[str]):
    """Re-run the writer node with revise feedback (and the alternate strategy) and take the
    corresponding paragraph from the new draft; the other paragraphs are left untouched."""
    import asyncio

    from ..config import cfg
    state = dict(values or {})
    opts = dict(state.get("options") or {})
    current = (state.get("draft") or {}).get("strategy") or opts.get("strategy")
    strategies = list((cfg("writer.strategies", {}) or {}).keys())
    alt = next((k for k in strategies if k != current), current)
    if alt:
        opts["strategy"] = alt
    state["options"] = opts
    feedback = [body.instruction or f"rewrite paragraph {body.paragraph_index + 1} with different evidence"]
    state["critiques"] = list(state.get("critiques") or []) + [{"verdict": "revise", "reasons": feedback,
                                                               "score": 0, "round": 99, "job_id": state.get("job_id")}]
    deps_cls = first_attr("agent.nodes.base", ["Deps"])
    out = await asyncio.to_thread(writer, state, deps_cls() if deps_cls else None)
    text = ((out or {}).get("draft") or {}).get("cover_letter", "")
    new_paras = _paragraphs(text)
    if not new_paras:
        raise HTTPException(502, "Writer returned an empty draft")
    idx = min(body.paragraph_index, len(new_paras) - 1)
    candidate = new_paras[idx]
    if candidate.strip() == paras[body.paragraph_index].strip():
        others = [p for p in new_paras if p.strip() not in {x.strip() for x in paras}]
        candidate = others[0] if others else candidate
    claims = []
    verify = first_attr("rag.verify", ["verify_proposal"])
    get_retriever = first_attr("rag.retriever", ["get_retriever"])
    if verify and get_retriever:
        try:
            res = await asyncio.to_thread(verify, candidate, get_retriever(state.get("persona") or "aiml"),
                                          state.get("persona") or "aiml")
            claims = [c.model_dump() if hasattr(c, "model_dump") else c for c in (res or {}).get("claims", [])]
        except Exception:
            claims = []
    return candidate, claims


def _card(p: Proposal) -> PipelineCard:
    return PipelineCard(job_id=p.job_id, thread_id=p.thread_id, title=p.title, category=p.category,
                        status=p.status, bid_amount=p.bid_amount, connects_spent=p.connects_spent,
                        updated_at=p.updated_at)


async def sync_proposal_statuses(db: Session, user: User) -> bool:
    try:
        remote = await marketplace.list_proposals(marketplace_token(db, user))
    except marketplace.MarketplaceUnavailable:
        return False
    by_pid = {r.get("proposal_id"): r for r in remote if isinstance(r, dict)}
    by_job = {r.get("job_id"): r for r in remote if isinstance(r, dict)}
    for p in db.scalars(select(Proposal).where(Proposal.user_id == user.id)):
        r = by_pid.get(p.marketplace_proposal_id) or by_job.get(p.job_id)
        if r and r.get("status") in COLUMNS:
            if r["status"] != p.status and r["status"] not in ("drafted", "submitted"):
                await record_outcome(runtime.store, user.id, p.category or "general", r["status"],
                                     r.get("proposal_id") or p.marketplace_proposal_id or p.job_id)
            p.status = r["status"]
            p.marketplace_proposal_id = r.get("proposal_id") or p.marketplace_proposal_id
            if r.get("connects_spent") is not None:
                p.connects_spent = int(r["connects_spent"])
    db.commit()
    return True


@pipeline_router.get("", response_model=PipelineOut)
async def pipeline(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ok = await sync_proposal_statuses(db, user)
    cols: dict[str, list[PipelineCard]] = {c: [] for c in COLUMNS}
    for p in db.scalars(select(Proposal).where(Proposal.user_id == user.id).order_by(Proposal.updated_at.desc())):
        if p.status in cols:
            cols[p.status].append(_card(p))
    return PipelineOut(columns=cols, marketplace="ok" if ok else "unavailable")
