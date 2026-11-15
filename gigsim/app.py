"""GigSim: a deterministic freelance-marketplace simulator (FastAPI).

    uvicorn gigsim.app:app --port 8100
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import numpy as np
import sqlalchemy as sa
from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from gigsim import client_model
from gigsim import vocab as V
from gigsim.storage import (SEED_DIR, config, get_engine, get_state, gs_clients, gs_events, gs_freelancers, gs_idempotency, gs_jobs,
                            gs_messages, gs_proposals, gs_threads, seed, set_state)

app = FastAPI(title="GigSim", version="1.0.0", description="Synthetic freelance marketplace for GigBid development and grading.")

_TOKENS: dict[str, str] = json.loads((SEED_DIR / "tokens.json").read_text())
_err_rng = random.Random(42)
_lock = threading.RLock()


class SimError(Exception):
    def __init__(self, status: int, code: str, message: str, headers: dict | None = None):
        self.status, self.code, self.message, self.headers = status, code, message, headers or {}


@app.exception_handler(SimError)
async def _sim_error(_req: Request, exc: SimError):
    return JSONResponse(status_code=exc.status, content={"error": exc.code, "detail": exc.message}, headers=exc.headers)


# ---------------------------------------------------------------------------
# Rate limiting, error injection, auth
# ---------------------------------------------------------------------------

class RateLimiter:
    def __init__(self):
        self.hits: dict[str, deque] = defaultdict(deque)

    def reset(self):
        self.hits.clear()

    def check(self, token: str) -> None:
        limit = int(os.environ.get("GIGSIM_RATE_LIMIT", config()["rate_limit_per_minute"]))
        now = time.monotonic()
        q = self.hits[token]
        while q and now - q[0] >= 60:
            q.popleft()
        if len(q) >= limit:
            retry = max(1, math.ceil(60 - (now - q[0])))
            raise SimError(429, "rate_limited", f"rate limit of {limit} requests/minute exceeded", {"Retry-After": str(retry)})
        q.append(now)


limiter = RateLimiter()


def reset_rate_limits() -> None:
    limiter.reset()


def engine() -> sa.Engine:
    return get_engine()


def current_freelancer(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise SimError(401, "unauthorized", "missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    fl = _TOKENS.get(token)
    if not fl:
        raise SimError(401, "unauthorized", "invalid token")
    limiter.check(token)
    rate = float(os.environ.get("GIGSIM_ERROR_RATE", config()["error_rate_default"]))
    if rate > 0 and _err_rng.random() < rate:
        raise SimError(503, "upstream_unavailable", "simulated transient server error, retry with backoff")
    return fl


def require_admin(x_admin_key: Optional[str] = Header(default=None)) -> None:
    if x_admin_key != os.environ.get("GIGSIM_ADMIN_KEY", config()["admin_key"]):
        raise SimError(403, "forbidden", "invalid admin key")


def policy_active() -> bool:
    return os.environ.get("GIGSIM_POLICY_UPDATE", "1") == "1"


def parse_ts(s: str) -> datetime:
    return datetime.strptime(s.replace("+00:00", "Z"), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sim_now(conn) -> datetime:
    return parse_ts(get_state(conn, "sim_now"))


def emit(conn, type_: str, ts: str, payload: dict, freelancer_id: str | None = None) -> None:
    conn.execute(gs_events.insert().values(freelancer_id=freelancer_id, type=type_, ts=ts, payload=payload))


def public_job(row) -> dict:
    return dict(row.data)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ScreeningAnswer(BaseModel):
    question: str
    answer: str


class ProposalIn(BaseModel):
    job_id: str
    cover_letter: str = Field(min_length=1)
    screening_answers: list[ScreeningAnswer] = Field(default_factory=list)
    bid_amount: float = Field(gt=0)
    idempotency_key: Optional[str] = Field(default=None, min_length=1, max_length=128)
    dry_run: bool = False


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    idempotency_key: str = Field(min_length=1, max_length=128)


class TickIn(BaseModel):
    n_jobs: Optional[int] = Field(default=None, ge=0, le=600)
    hours: Optional[float] = Field(default=None, ge=0, le=168)


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    with engine().connect() as conn:
        return {"status": "ok", "sim_now": get_state(conn, "sim_now"), "tick": int(get_state(conn, "tick", "0")),
                "policy_update": policy_active()}


@app.get("/jobs")
def list_jobs(q: Optional[str] = None, category: Optional[str] = None, skills: Optional[str] = None, since: Optional[str] = None,
              limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), fl: str = Depends(current_freelancer)):
    with engine().connect() as conn:
        rows = conn.execute(sa.select(gs_jobs.c.data).where(gs_jobs.c.pool == "stream", gs_jobs.c.status == "open")).all()
    jobs = [dict(r.data) for r in rows]
    if category:
        jobs = [j for j in jobs if j["category"].lower() == category.lower()]
    if q:
        terms = q.lower().split()
        jobs = [j for j in jobs if all(t in (j["title"] + " " + j["description"]).lower() for t in terms)]
    if skills:
        want = {s.strip().lower() for s in skills.split(",") if s.strip()}
        jobs = [j for j in jobs if want & {s.lower() for s in j["skills_required"]}]
    if since:
        jobs = [j for j in jobs if j["posted_at"] >= since.replace("+00:00", "Z")]
    jobs.sort(key=lambda j: (j["posted_at"], j["id"]), reverse=True)
    return {"jobs": jobs[offset:offset + limit], "total": len(jobs)}


@app.get("/jobs/{job_id}")
def get_job(job_id: str, fl: str = Depends(current_freelancer)):
    with engine().connect() as conn:
        row = conn.execute(sa.select(gs_jobs).where(gs_jobs.c.id == job_id)).first()
    if row is None or row.status == "pending":
        raise SimError(404, "not_found", f"job {job_id} not found")
    job = public_job(row)
    job["status"] = row.status
    return job


@app.get("/clients/{client_id}/history")
def client_history(client_id: str, fl: str = Depends(current_freelancer)):
    with engine().connect() as conn:
        row = conn.execute(sa.select(gs_clients.c.data).where(gs_clients.c.id == client_id)).first()
    if row is None:
        raise SimError(404, "not_found", f"client {client_id} not found")
    d = dict(row.data)
    return {"client_id": d["id"], **{k: d[k] for k in ("name", "country", "total_spent", "hires", "jobs_posted", "avg_rating",
                                                       "payment_verified", "member_since", "reviews")}}


@app.get("/connects")
def connects(fl: str = Depends(current_freelancer)):
    with engine().connect() as conn:
        r = conn.execute(sa.select(gs_freelancers).where(gs_freelancers.c.id == fl)).first()
    return {"freelancer_id": fl, "balance": r.balance, "weekly_spent": r.weekly_spent}


_stats_cache: dict = {}


def _pct(vals: list[float]) -> dict:
    if not vals:
        return {"p25": None, "p50": None, "p75": None, "n": 0}
    a = np.array(vals, dtype=float)
    return {"p25": round(float(np.percentile(a, 25)), 2), "p50": round(float(np.percentile(a, 50)), 2),
            "p75": round(float(np.percentile(a, 75)), 2), "n": len(vals)}


@app.get("/market/stats")
def market_stats(category: Optional[str] = None, fl: str = Depends(current_freelancer)):
    key = (str(engine().url), (category or "").lower())
    if key not in _stats_cache:
        with engine().connect() as conn:
            rows = conn.execute(sa.select(gs_jobs.c.data).where(gs_jobs.c.pool == "historical")).all()
        jobs = [r.data for r in rows if not category or r.data["category"].lower() == category.lower()]
        _stats_cache[key] = {"category": category, "n": len(jobs),
                             "hourly": _pct([j["awarded_amount"] for j in jobs if j["budget_type"] == "hourly"]),
                             "fixed": _pct([j["awarded_amount"] for j in jobs if j["budget_type"] == "fixed"])}
    return _stats_cache[key]


@app.get("/policy")
def policy(fl: str = Depends(current_freelancer)):
    pu = config()["policy_update"]
    return {"policy_update_active": policy_active(), "effective": pu["effective"],
            "early_bird_surcharge": {"connects": pu["early_bird_surcharge_connects"], "window_minutes": pu["early_bird_window_minutes"]},
            "max_proposal_chars": pu["max_proposal_chars"] if policy_active() else None}


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------

def _req_hash(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def _idem_lookup(conn, fl: str, endpoint: str, key: str, req_hash: str):
    row = conn.execute(sa.select(gs_idempotency).where(gs_idempotency.c.freelancer_id == fl, gs_idempotency.c.endpoint == endpoint,
                                                       gs_idempotency.c.key == key)).first()
    if row is None:
        return None
    if row.request_hash != req_hash:
        raise SimError(409, "idempotency_conflict", "idempotency_key reused with a different request body")
    return JSONResponse(status_code=row.status_code, content=row.response, headers={"Idempotent-Replay": "true"})


def connects_cost(job: dict, now: datetime) -> tuple[int, int]:
    surcharge = 0
    if policy_active() and job.get("posted_at"):
        pu = config()["policy_update"]
        if now - parse_ts(job["posted_at"]) < timedelta(minutes=pu["early_bird_window_minutes"]):
            surcharge = pu["early_bird_surcharge_connects"]
    return job["connects_cost"] + surcharge, surcharge


@app.post("/proposals")
def create_proposal(body: ProposalIn, fl: str = Depends(current_freelancer)):
    if not body.dry_run and not body.idempotency_key:
        raise SimError(422, "idempotency_key_required", "idempotency_key is required unless dry_run is true")
    req = body.model_dump(exclude={"idempotency_key", "dry_run"})
    with _lock, engine().begin() as conn:
        if not body.dry_run:
            replay = _idem_lookup(conn, fl, "proposals", body.idempotency_key, _req_hash(req))
            if replay is not None:
                return replay
        jrow = conn.execute(sa.select(gs_jobs).where(gs_jobs.c.id == body.job_id)).first()
        if jrow is None or jrow.status == "pending":
            raise SimError(404, "not_found", f"job {body.job_id} not found")
        if jrow.status != "open":
            raise SimError(409, "job_closed", f"job {body.job_id} is not accepting proposals")
        job = dict(jrow.data)
        if policy_active() and len(body.cover_letter) > config()["policy_update"]["max_proposal_chars"]:
            raise SimError(422, "proposal_too_long",
                           f"cover letter has {len(body.cover_letter)} characters; the limit is {config()['policy_update']['max_proposal_chars']}")
        dup = conn.execute(sa.select(gs_proposals.c.proposal_id).where(gs_proposals.c.freelancer_id == fl,
                                                                      gs_proposals.c.job_id == body.job_id)).first()
        if dup:
            raise SimError(409, "already_applied", f"already applied to {body.job_id} as {dup.proposal_id}")
        now = sim_now(conn)
        cost, surcharge = connects_cost(job, now)
        frow = conn.execute(sa.select(gs_freelancers).where(gs_freelancers.c.id == fl)).first()
        if frow.balance < cost:
            raise SimError(402, "insufficient_connects", f"need {cost} connects, balance is {frow.balance}")
        if body.dry_run:
            return {"would_send": req, "connects_cost": cost, "surcharge": surcharge, "balance_after": frow.balance - cost, "dry_run": True}
        pid = "p-" + hashlib.sha1(f"{fl}|{body.job_id}|{body.idempotency_key}".encode()).hexdigest()[:12]
        ts = iso(now)
        conn.execute(gs_proposals.insert().values(proposal_id=pid, freelancer_id=fl, job_id=body.job_id, status="submitted",
                                                  cover_letter=body.cover_letter, screening_answers=[a.model_dump() for a in body.screening_answers],
                                                  bid_amount=body.bid_amount, connects_spent=cost, created_at=ts, updated_at=ts, decision=None))
        conn.execute(gs_freelancers.update().where(gs_freelancers.c.id == fl).values(balance=frow.balance - cost,
                                                                                    weekly_spent=frow.weekly_spent + cost))
        job["proposals_count"] = job.get("proposals_count", 0) + 1
        conn.execute(gs_jobs.update().where(gs_jobs.c.id == body.job_id).values(data=job))
        emit(conn, "proposal_status", ts, {"proposal_id": pid, "job_id": body.job_id, "status": "submitted"}, fl)
        resp = {"proposal_id": pid, "job_id": body.job_id, "status": "submitted", "connects_spent": cost, "surcharge": surcharge,
                "balance_after": frow.balance - cost}
        conn.execute(gs_idempotency.insert().values(freelancer_id=fl, endpoint="proposals", key=body.idempotency_key,
                                                    request_hash=_req_hash(req), status_code=200, response=resp))
        return resp


@app.get("/proposals")
def list_proposals(fl: str = Depends(current_freelancer)):
    with engine().connect() as conn:
        rows = conn.execute(sa.select(gs_proposals, gs_jobs.c.data).join(gs_jobs, gs_jobs.c.id == gs_proposals.c.job_id)
                            .where(gs_proposals.c.freelancer_id == fl).order_by(gs_proposals.c.created_at.desc())).all()
    return [{"proposal_id": r.proposal_id, "job_id": r.job_id, "job_title": r.data["title"], "status": r.status, "bid_amount": r.bid_amount,
             "connects_spent": r.connects_spent, "created_at": r.created_at, "updated_at": r.updated_at} for r in rows]


# ---------------------------------------------------------------------------
# Threads and messages
# ---------------------------------------------------------------------------

def _own_thread(conn, fl: str, thread_id: str):
    t = conn.execute(sa.select(gs_threads).where(gs_threads.c.thread_id == thread_id)).first()
    if t is None or t.freelancer_id != fl:
        raise SimError(404, "not_found", f"thread {thread_id} not found")
    return t


@app.get("/threads")
def list_threads(fl: str = Depends(current_freelancer)):
    with engine().connect() as conn:
        rows = conn.execute(sa.select(gs_threads).where(gs_threads.c.freelancer_id == fl).order_by(gs_threads.c.last_message_at.desc())).all()
    return [{"thread_id": r.thread_id, "job_id": r.job_id, "client_id": r.client_id, "proposal_id": r.proposal_id,
             "last_message_at": r.last_message_at, "unread": bool(r.unread)} for r in rows]


@app.get("/threads/{thread_id}/messages")
def list_messages(thread_id: str, fl: str = Depends(current_freelancer)):
    with engine().begin() as conn:
        _own_thread(conn, fl, thread_id)
        rows = conn.execute(sa.select(gs_messages).where(gs_messages.c.thread_id == thread_id).order_by(gs_messages.c.created_at, gs_messages.c.id)).all()
        conn.execute(gs_threads.update().where(gs_threads.c.thread_id == thread_id).values(unread=0))
    return [{"id": r.id, "sender": r.sender, "body": r.body, "created_at": r.created_at} for r in rows]


@app.post("/threads/{thread_id}/messages")
def send_message(thread_id: str, body: MessageIn, fl: str = Depends(current_freelancer)):
    with _lock, engine().begin() as conn:
        endpoint = f"messages:{thread_id}"
        replay = _idem_lookup(conn, fl, endpoint, body.idempotency_key, _req_hash({"body": body.body}))
        if replay is not None:
            return replay
        _own_thread(conn, fl, thread_id)
        ts = iso(sim_now(conn))
        n = conn.execute(sa.select(sa.func.count()).select_from(gs_messages).where(gs_messages.c.thread_id == thread_id)).scalar()
        mid = f"m-{thread_id}-{n + 1}-" + hashlib.sha1(body.idempotency_key.encode()).hexdigest()[:6]
        msg = {"id": mid, "sender": "freelancer", "body": body.body, "created_at": ts}
        conn.execute(gs_messages.insert().values(thread_id=thread_id, **msg))
        conn.execute(gs_threads.update().where(gs_threads.c.thread_id == thread_id).values(last_message_at=ts))
        conn.execute(gs_idempotency.insert().values(freelancer_id=fl, endpoint=endpoint, key=body.idempotency_key,
                                                    request_hash=_req_hash({"body": body.body}), status_code=200, response=msg))
        return msg


@app.get("/events")
def events(since: Optional[str] = None, limit: int = Query(500, ge=1, le=2000), fl: str = Depends(current_freelancer)):
    with engine().connect() as conn:
        stmt = sa.select(gs_events).where(sa.or_(gs_events.c.freelancer_id == fl, gs_events.c.freelancer_id.is_(None)))
        if since:
            stmt = stmt.where(gs_events.c.ts > since.replace("+00:00", "Z"))
        rows = conn.execute(stmt.order_by(gs_events.c.id).limit(limit)).all()
    return [{"id": r.id, "type": r.type, "ts": r.ts, **(r.payload or {})} for r in rows]


# ---------------------------------------------------------------------------
# Simulation tick
# ---------------------------------------------------------------------------

def _decide(conn, prop) -> dict:
    if prop.decision:
        return prop.decision
    jrow = conn.execute(sa.select(gs_jobs).where(gs_jobs.c.id == prop.job_id)).first()
    hidden = jrow.hidden or {}
    if hidden.get("is_scam"):
        d = {"reply_prob": 0.0, "replied": False, "interview": False, "hired": False, "factors": {"scam_job": 1.0}}
    elif not hidden.get("prefs"):
        d = {"reply_prob": 0.0, "replied": False, "interview": False, "hired": False, "factors": {}}
    else:
        det, _ = client_model.deterministic_prob(jrow.data, hidden["prefs"], prop.cover_letter, prop.bid_amount, prop.screening_answers)
        llm = client_model.llm_reply_prob(jrow.data, hidden["prefs"], prop.cover_letter, prop.bid_amount)
        override = None
        if llm is not None:
            w = config()["client_model"]["llm"]["weight"]
            override = (1 - w) * det + w * llm
        d = client_model.score_proposal(prop.job_id, prop.cover_letter, prop.bid_amount, prop.screening_answers, reply_prob_override=override) \
            if prop.job_id in client_model._hidden() else {"reply_prob": det, "replied": False, "interview": False, "hired": False, "factors": {}}
    conn.execute(gs_proposals.update().where(gs_proposals.c.proposal_id == prop.proposal_id).values(decision=d))
    return d


def _client_message(conn, prop, job: dict, templates: list[str], ts: str) -> None:
    tid = "t-" + prop.proposal_id[2:]
    t = conn.execute(sa.select(gs_threads).where(gs_threads.c.proposal_id == prop.proposal_id)).first()
    if t is None:
        conn.execute(gs_threads.insert().values(thread_id=tid, freelancer_id=prop.freelancer_id, job_id=prop.job_id,
                                                client_id=job["client_id"], proposal_id=prop.proposal_id, last_message_at=ts, unread=1))
    else:
        tid = t.thread_id
    n = conn.execute(sa.select(sa.func.count()).select_from(gs_messages).where(gs_messages.c.thread_id == tid)).scalar()
    idx = int(hashlib.sha1(f"{prop.proposal_id}{n}".encode()).hexdigest(), 16) % len(templates)
    body = templates[idx].format(topic=(job.get("skills_required") or ["the project"])[0])
    mid = f"m-{tid}-{n + 1}-c"
    conn.execute(gs_messages.insert().values(id=mid, thread_id=tid, sender="client", body=body, created_at=ts))
    conn.execute(gs_threads.update().where(gs_threads.c.thread_id == tid).values(last_message_at=ts, unread=1))
    emit(conn, "new_message", ts, {"thread_id": tid, "message_id": mid, "proposal_id": prop.proposal_id}, prop.freelancer_id)


def _set_status(conn, prop, status: str, ts: str) -> None:
    conn.execute(gs_proposals.update().where(gs_proposals.c.proposal_id == prop.proposal_id).values(status=status, updated_at=ts))
    emit(conn, "proposal_status", ts, {"proposal_id": prop.proposal_id, "job_id": prop.job_id, "status": status}, prop.freelancer_id)


def run_tick(n_jobs: int | None = None, hours: float | None = None) -> dict:
    cfg = config()["tick"]
    n_jobs = cfg["jobs_per_tick"] if n_jobs is None else n_jobs
    hours = cfg["hours_per_tick"] if hours is None else hours
    with _lock, engine().begin() as conn:
        tick = int(get_state(conn, "tick", "0")) + 1
        now = sim_now(conn) + timedelta(hours=hours)
        ts = iso(now)
        set_state(conn, "tick", str(tick))
        set_state(conn, "sim_now", ts)
        # 1. release new stream jobs
        pending = conn.execute(sa.select(gs_jobs).where(gs_jobs.c.pool == "stream", gs_jobs.c.status == "pending")
                               .order_by(gs_jobs.c.release_order).limit(n_jobs)).all()
        released = []
        for row in pending:
            job = dict(row.data)
            mins = int(hashlib.sha1(row.id.encode()).hexdigest(), 16) % 50
            job["posted_at"] = iso(now - timedelta(minutes=mins))
            conn.execute(gs_jobs.update().where(gs_jobs.c.id == row.id).values(status="open", posted_at=job["posted_at"], data=job))
            emit(conn, "new_job", ts, {"job_id": row.id, "title": job["title"], "category": job["category"]})
            released.append(row.id)
        # 2. close stale stream jobs
        cutoff = iso(now - timedelta(days=cfg["close_after_days"]))
        conn.execute(gs_jobs.update().where(gs_jobs.c.pool == "stream", gs_jobs.c.status == "open", gs_jobs.c.posted_at < cutoff).values(status="closed"))
        # 3. simulated clients act on proposals, one stage per tick
        decisions = []
        props = conn.execute(sa.select(gs_proposals).where(gs_proposals.c.status.in_(["submitted", "viewed", "replied", "interview"]))).all()
        for p in props:
            if p.decision and p.decision.get("frozen"):
                continue  # seeded conversations stay put so conversation flows can be exercised
            job = conn.execute(sa.select(gs_jobs.c.data).where(gs_jobs.c.id == p.job_id)).scalar()
            if p.status == "submitted":
                _set_status(conn, p, "viewed", ts)
                decisions.append({"proposal_id": p.proposal_id, "status": "viewed"})
                continue
            d = _decide(conn, p)
            new = None
            if p.status == "viewed":
                new = "replied" if d["replied"] else "lost"
                if new == "replied":
                    _client_message(conn, p, job, V.CLIENT_REPLY_TEMPLATES, ts)
            elif p.status == "replied" and d.get("interview"):
                new = "interview"
                _client_message(conn, p, job, V.CLIENT_INTERVIEW_TEMPLATES, ts)
            elif p.status == "interview":
                new = "hired" if d.get("hired") else "lost"
                _client_message(conn, p, job, V.CLIENT_HIRE_TEMPLATES if new == "hired" else V.CLIENT_LOST_TEMPLATES, ts)
            if new:
                _set_status(conn, p, new, ts)
                decisions.append({"proposal_id": p.proposal_id, "status": new, "reply_prob": d.get("reply_prob")})
        return {"tick": tick, "sim_now": ts, "released": released, "decisions": decisions}


@app.post("/admin/tick", dependencies=[Depends(require_admin)])
def admin_tick(body: Optional[TickIn] = None):
    body = body or TickIn()
    return run_tick(body.n_jobs, body.hours)


@app.post("/admin/reset", dependencies=[Depends(require_admin)])
def admin_reset():
    with _lock:
        counts = seed(engine())
    _stats_cache.clear()
    limiter.reset()
    return {"reset": True, "counts": counts}


@app.get("/admin/hidden/{job_id}", dependencies=[Depends(require_admin)])
def admin_hidden(job_id: str):
    """Grader/eval-only view of a job's hidden labels. Never exposed to freelancer tokens."""
    with engine().connect() as conn:
        row = conn.execute(sa.select(gs_jobs.c.hidden).where(gs_jobs.c.id == job_id)).first()
    if row is None:
        raise SimError(404, "not_found", f"job {job_id} not found")
    return row.hidden or {}


Status = Literal["submitted", "viewed", "replied", "interview", "hired", "lost"]
