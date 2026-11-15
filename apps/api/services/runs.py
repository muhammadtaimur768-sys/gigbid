"""Run lifecycle: start (idempotent per user+job), resume via Command(resume=...), execute inline,
in the Arq worker, or driven by the SSE request; degraded-mode queueing and retry."""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import logging
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import InboxItem, JobAnalysis, PendingWork, Proposal, Run, SessionLocal, User, utcnow
from ..graphs import runtime, thread_config
from ..integrations import first_attr
from ..streaming import bridge, persist_emitter, to_jsonable
from ..tracing import trace_id_var

log = logging.getLogger("gigbid.runs")
_tasks: set[asyncio.Task] = set()


class GraphUnavailable(Exception):
    pass


def bid_thread_id(user_id: str, job_id: str) -> str:
    return f"bid-{hashlib.sha1(f'{user_id}:{job_id}'.encode()).hexdigest()[:16]}"


def conv_thread_id(user_id: str, mp_thread_id: str, n: int = 0) -> str:
    return f"conv-{hashlib.sha1(f'{user_id}:{mp_thread_id}'.encode()).hexdigest()[:12]}-{n}"


def claim_analysis(db: Session, user_id: str, job_id: str) -> tuple[str, bool]:
    """Insert the (user, job) idempotency row. Returns (thread_id, created)."""
    thread_id = bid_thread_id(user_id, job_id)
    try:
        db.add(JobAnalysis(user_id=user_id, job_id=job_id, thread_id=thread_id))
        db.commit()
        return thread_id, True
    except IntegrityError:
        db.rollback()
        row = db.scalar(select(JobAnalysis).where(JobAnalysis.user_id == user_id, JobAnalysis.job_id == job_id))
        return (row.thread_id if row else thread_id), False


def start_bid_run(db: Session, user: User, job: dict, trace_id: str,
                  auto_dispatch: bool = True) -> tuple[Run, bool]:
    if runtime.bid_graph is None:
        raise GraphUnavailable(runtime.errors.get("bid_graph", "bid graph unavailable"))
    thread_id, created = claim_analysis(db, user.id, job["id"])
    run = db.get(Run, thread_id)
    if not created and run is not None:
        return run, False
    run = Run(thread_id=thread_id, user_id=user.id, kind="bid", job_id=job["id"], status="queued",
              trace_id=trace_id, pending_input={"type": "start", "job": job})
    db.add(run)
    item = db.scalar(select(InboxItem).where(InboxItem.user_id == user.id, InboxItem.job_id == job["id"]))
    if item:
        item.status, item.thread_id = "analysing", thread_id
    db.commit()
    if auto_dispatch:
        dispatch(thread_id)
    return run, True


def start_conversation_run(db: Session, user: User, mp_thread_id: str, trace_id: str) -> Run:
    if runtime.conversation_graph is None:
        raise GraphUnavailable(runtime.errors.get("conversation_graph", "conversation graph unavailable"))
    n = len(list(db.scalars(select(Run.thread_id).where(Run.user_id == user.id,
                                                        Run.marketplace_thread_id == mp_thread_id))))
    thread_id = conv_thread_id(user.id, mp_thread_id, n)
    run = Run(thread_id=thread_id, user_id=user.id, kind="conversation", marketplace_thread_id=mp_thread_id,
              status="queued", trace_id=trace_id, pending_input={"type": "start", "thread_id": mp_thread_id})
    db.add(run)
    db.commit()
    dispatch(thread_id)
    return run


def resume_run(db: Session, run: Run, value: dict, trace_id: str) -> Run:
    run.pending_input = {"type": "resume", "value": value}
    run.status = "queued"
    # the run keeps its original trace id so one trace covers analysis -> approval -> submit;
    # the resuming request's own id is recorded on the resume event.
    run.pending_input["request_trace_id"] = trace_id
    run.error = None
    db.commit()
    dispatch(run.thread_id)
    return run


def dispatch(thread_id: str) -> None:
    mode = get_settings().run_mode
    if mode == "stream":
        return  # the SSE request drives execution (serverless hosts)
    if mode == "worker":
        try:
            asyncio.get_running_loop().create_task(_enqueue_arq(thread_id))
            return
        except RuntimeError:
            pass
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    t = loop.create_task(execute(thread_id))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


async def _enqueue_arq(thread_id: str) -> None:
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
        await pool.enqueue_job("execute_run", thread_id, _job_id=f"exec:{thread_id}:{utcnow().timestamp()}")
        await pool.aclose()
    except Exception:  # noqa: BLE001
        log.exception("enqueue failed; executing inline")
        await execute(thread_id)


def _is_unavailable(exc: BaseException) -> bool:
    names = {type(e).__name__ for e in _chain(exc)}
    return bool(names & {"MarketplaceUnavailable", "ConnectError", "ConnectTimeout"})


def _chain(exc: BaseException):
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        yield exc
        for sub in getattr(exc, "exceptions", []) or []:
            yield from _chain(sub)
        exc = exc.__cause__ or exc.__context__


def _graph_input(run: Run, user: User):
    from langgraph.types import Command
    pi = run.pending_input or {}
    if pi.get("type") == "resume":
        return Command(resume=pi.get("value"))
    st = user.settings or {}
    options = {"autonomy": st.get("autonomy", "manual"), "rates": st.get("rates", {}),
               "budgets": st.get("budgets", {})}
    persona = user.persona or "aiml"
    if run.kind == "bid":
        job = pi.get("job") or {}
        helper = first_attr("agent.graphs.bid_graph", ["new_run_input"])
        if helper is not None:
            return helper(job=job, job_id=run.job_id, persona=persona, user_id=user.id, options=options,
                          trace_id=run.trace_id, thread_id=run.thread_id)
        return {"job_id": run.job_id, "job": job, "user_id": user.id, "persona": persona,
                "trace_id": run.trace_id, "thread_id": run.thread_id, "options": options, "status": "running"}
    helper = first_attr("agent.graphs.conversation_graph", ["new_conversation_input"])
    if helper is not None:
        inp = helper(pi.get("thread_id"), persona=persona, user_id=user.id, options=options, trace_id=run.trace_id)
        inp["thread_id"] = run.thread_id
        return inp
    return {"thread_id": run.thread_id, "conversation_id": pi.get("thread_id"), "user_id": user.id,
            "persona": persona, "trace_id": run.trace_id, "options": options, "status": "running"}


async def execute(thread_id: str) -> str:
    """Claim and run one graph segment in a worker thread. Returns the resulting run status."""
    import anyio
    return await anyio.to_thread.run_sync(execute_sync, thread_id)


def execute_sync(thread_id: str) -> str:
    db = SessionLocal()
    try:
        res = db.execute(update(Run).where(Run.thread_id == thread_id, Run.status.in_(["queued", "pending_retry"]))
                         .values(status="running", attempts=Run.attempts + 1, updated_at=utcnow()))
        db.commit()
        if res.rowcount != 1:
            return "skipped"
        run = db.get(Run, thread_id)
        user = db.get(User, run.user_id)
        graph = runtime.graph_for(run.kind)
        emit = persist_emitter(thread_id, run.user_id)
        token = trace_id_var.set(run.trace_id)
        if graph is None:
            emit("error", {"message": f"{run.kind} graph unavailable", "degraded": False})
            _set(db, run, "error", error="graph unavailable")
            emit("done", {"status": "error"})
            return "error"
        config = thread_config(thread_id, run.user_id, run.trace_id, user.persona)
        try:
            pi = run.pending_input or {}
            emit("progress", {"stage": "run_start", "trace_id": run.trace_id, "resume": pi.get("type") == "resume",
                              "request_trace_id": pi.get("request_trace_id")})
            bridge(graph, _graph_input(run, user), config, emit)
            snapshot = graph.get_state(config)
            interrupts = pending_interrupts(snapshot)
            status = "interrupted" if interrupts else "done"
            _set(db, run, status, outcome=_outcome(snapshot.values))
            sync_from_state(db, run, snapshot.values, interrupted=bool(interrupts))
            emit("done", {"status": status, "outcome": run.outcome})
            return status
        except Exception as exc:  # noqa: BLE001
            log.exception("run %s failed", thread_id)
            db.rollback()
            if _is_unavailable(exc):
                _set(db, run, "pending_retry", error=str(exc)[:500])
                db.add(PendingWork(user_id=run.user_id, kind="execute", payload={"thread_id": thread_id},
                                   next_attempt_at=utcnow() + dt.timedelta(seconds=30)))
                db.commit()
                emit("error", {"message": "Marketplace unavailable; run queued for retry", "degraded": True})
                emit("done", {"status": "pending_retry"})
                return "pending_retry"
            _set(db, run, "error", error=f"{type(exc).__name__}: {exc}"[:1000])
            emit("error", {"message": f"{type(exc).__name__}: {exc}"[:500], "degraded": False})
            emit("done", {"status": "error"})
            return "error"
        finally:
            trace_id_var.reset(token)
    finally:
        db.close()


def _set(db: Session, run: Run, status: str, **fields) -> None:
    run.status = status
    for k, v in fields.items():
        setattr(run, k, v)
    if status != "queued":
        run.pending_input = None if status in ("done", "interrupted") else run.pending_input
    db.commit()


def pending_interrupts(snapshot) -> list[dict]:
    if snapshot is None:
        return []
    out = []
    for intr in getattr(snapshot, "interrupts", ()) or ():
        out.append({"id": getattr(intr, "id", None), "value": to_jsonable(getattr(intr, "value", intr))})
    if not out:
        for task in getattr(snapshot, "tasks", ()) or ():
            for intr in getattr(task, "interrupts", ()) or ():
                out.append({"id": getattr(intr, "id", None), "value": to_jsonable(getattr(intr, "value", intr)),
                            "node": getattr(task, "name", None)})
    return out


def _get(values: dict, *names):
    for n in names:
        if isinstance(values, dict) and values.get(n) is not None:
            return to_jsonable(values[n])
    return None


def state_view(values: dict | None) -> dict:
    """Normalise graph state into the shapes the UI renders."""
    values = values or {}
    draft = _get(values, "draft", "proposal", "proposal_draft")
    critiques = _get(values, "critiques", "critique")
    if isinstance(critiques, dict):
        critiques = [critiques]
    return {
        "job": _get(values, "job", "raw_job"),
        "job_spec": _get(values, "job_spec", "spec"),
        "risk": _get(values, "risk", "risk_report"),
        "fit": _get(values, "fit", "fit_report"),
        "decision": _get(values, "decision", "bid_decision"),
        "price": _get(values, "price", "price_quote", "quote"),
        "draft": draft,
        "critiques": critiques or [],
        "compliance": _get(values, "compliance", "compliance_verdict"),
        "submission": _get(values, "submission", "submit_result", "sent"),
        "status": _get(values, "status", "final_status"),
        "approval": _get(values, "approval", "approval_decision"),
        "dry_run": _get(values, "preview", "dry_run", "dry_run_preview"),
        "errors": _get(values, "errors") or [],
        "reply": _get(values, "reply", "reply_draft"),
        "intent": _get(values, "intent", "message_intent"),
        "status_reason": _get(values, "status_reason"),
        "outcome": _get(values, "outcome"),
        "usage": _get(values, "usage"),
        "evidence": _get(values, "evidence") or [],
        "client": _get(values, "client"),
        "slots": _get(values, "slots") or [],
    }


def _outcome(values: dict | None) -> str | None:
    v = state_view(values)
    if v["status"]:
        return str(v["status"])[:32]
    if v["submission"]:
        return "submitted"
    if isinstance(v["decision"], dict):
        return v["decision"].get("action")
    return None


def sync_from_state(db: Session, run: Run, values: dict | None, interrupted: bool) -> None:
    if run.kind != "bid" or not run.job_id:
        return
    v = state_view(values)
    item = db.scalar(select(InboxItem).where(InboxItem.user_id == run.user_id, InboxItem.job_id == run.job_id))
    job = v["job"] or (item.job if item else {}) or {}
    if item:
        if isinstance(v["fit"], dict) and v["fit"].get("fit_score") is not None:
            item.fit_score = float(v["fit"]["fit_score"])
        if isinstance(v["decision"], dict) and v["decision"].get("action"):
            item.recommended_action = v["decision"]["action"]
        if isinstance(v["risk"], dict):
            flags = v["risk"].get("flags") or []
            item.risk_flags = flags
            item.risk_level = ("high" if v["risk"].get("is_scam") or v["risk"].get("injection_detected")
                               or any(f.get("severity") == "high" for f in flags)
                               else "medium" if flags else "low")
        if isinstance(v["price"], dict) and v["price"].get("amount") is not None:
            item.price = float(v["price"]["amount"])
    if interrupted or v["draft"] or v["submission"]:
        prop = db.scalar(select(Proposal).where(Proposal.user_id == run.user_id, Proposal.job_id == run.job_id))
        if prop is None:
            prop = Proposal(user_id=run.user_id, job_id=run.job_id, thread_id=run.thread_id,
                            title=job.get("title", ""), category=job.get("category", ""))
            db.add(prop)
        if isinstance(v["price"], dict) and v["price"].get("amount") is not None:
            prop.bid_amount = float(v["price"]["amount"])
        sub = v["submission"]
        if isinstance(sub, dict) and (sub.get("proposal_id") or sub.get("status") == "submitted"):
            prop.status = "submitted"
            prop.marketplace_proposal_id = sub.get("proposal_id")
            prop.connects_spent = int(sub.get("connects_spent") or 0)
            if item:
                item.status = "submitted"
        elif interrupted and prop.status in ("drafted",):
            if item:
                item.status = "drafted"
    elif item and item.status == "analysing":
        item.status = "analysed"
    db.commit()


async def retry_pending(limit: int = 20) -> dict:
    """Re-dispatch work queued while degraded. Called from health recovery, cron and the worker."""
    from . import marketplace
    if not (await marketplace.ping())["ok"]:
        return {"retried": 0, "remaining": _pending_count()}
    db = SessionLocal()
    retried = 0
    try:
        rows = list(db.scalars(select(PendingWork).where(PendingWork.status == "pending",
                                                         PendingWork.next_attempt_at <= utcnow()).limit(limit)))
        for w in rows:
            w.attempts += 1
            try:
                if w.kind == "execute":
                    tid = w.payload.get("thread_id")
                    run = db.get(Run, tid)
                    if run and run.status == "pending_retry":
                        run.status = "queued"
                        db.commit()
                        dispatch(tid)
                elif w.kind == "analyse":
                    user = db.get(User, w.user_id)
                    from .marketplace import get_job
                    from ..auth.token_store import get_token
                    token = get_token(db, user.id, "gigsim") or marketplace.default_token(user.persona)
                    job = await get_job(token, w.payload["job_id"])
                    start_bid_run(db, user, job, w.payload.get("trace_id", ""))
                w.status = "done"
                retried += 1
            except Exception as exc:  # noqa: BLE001
                w.last_error = str(exc)[:500]
                w.next_attempt_at = utcnow() + dt.timedelta(seconds=min(30 * 2 ** w.attempts, 3600))
                if w.attempts >= 8:
                    w.status = "failed"
            db.commit()
    finally:
        db.close()
    return {"retried": retried, "remaining": _pending_count()}


def _pending_count(user_id: str | None = None) -> int:
    db = SessionLocal()
    try:
        q = select(PendingWork).where(PendingWork.status == "pending")
        if user_id:
            q = q.where(PendingWork.user_id == user_id)
        return len(list(db.scalars(q)))
    finally:
        db.close()


def queue_pending(db: Session, user_id: str, kind: str, payload: dict[str, Any]) -> PendingWork:
    w = PendingWork(user_id=user_id, kind=kind, payload=payload)
    db.add(w)
    db.commit()
    return w
