"""Analytics aggregates. Every number is computed from stored rows; nothing is estimated."""
from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..auth.security import get_current_user
from ..db import Approval, Proposal, Run, User, get_db, get_engine
from ..schemas import AnalyticsOut, CategoryStat
from ..integrations import optional
from .proposals import sync_proposal_statuses

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
REPLIED = {"replied", "interview", "hired"}


def _pct(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, int(round(p * (len(xs) - 1)))))
    return round(xs[k], 2)


@router.get("", response_model=AnalyticsOut)
async def analytics(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    await sync_proposal_statuses(db, user)
    props = list(db.scalars(select(Proposal).where(Proposal.user_id == user.id)))
    sent = [p for p in props if p.status not in ("drafted", "rejected")]
    by_cat: dict[str, list[Proposal]] = defaultdict(list)
    for p in sent:
        by_cat[p.category or "uncategorised"].append(p)
    cats = []
    for cat, ps in sorted(by_cat.items()):
        replied = sum(1 for p in ps if p.status in REPLIED)
        hired = sum(1 for p in ps if p.status == "hired")
        cats.append(CategoryStat(category=cat, proposals=len(ps), replied=replied, hired=hired,
                                 reply_rate=round(replied / len(ps), 4) if ps else None,
                                 hire_rate=round(hired / len(ps), 4) if ps else None,
                                 connects_spent=sum(p.connects_spent for p in ps)))
    outcomes = Counter(p.status for p in props)
    connects_total = sum(p.connects_spent for p in sent)
    replies = sum(1 for p in sent if p.status in REPLIED)

    thread_ids = [r.thread_id for r in db.scalars(select(Run).where(Run.user_id == user.id, Run.kind == "bid"))]
    costs: list[float] = []
    latencies: list[float] = []
    shared = optional("agent.tracing", "get_trace_events")
    if thread_ids and shared is not None:
        for tid in thread_ids:
            try:
                evs = shared(thread_id=tid)
            except Exception:
                break
            if evs:
                costs.append(sum(float(e.get("cost_usd") or 0) for e in evs))
                latencies.append(sum(float(e.get("latency_ms") or 0) for e in evs if e.get("event") != "run"))
    elif thread_ids:
        try:
            with get_engine().connect() as conn:
                rows = conn.execute(text(
                    "SELECT thread_id, SUM(COALESCE(cost_usd,0)) AS cost, SUM(COALESCE(latency_ms,0)) AS lat "
                    "FROM trace_events GROUP BY thread_id")).mappings().all()
            for row in rows:
                if row["thread_id"] in thread_ids:
                    costs.append(float(row["cost"] or 0))
                    latencies.append(float(row["lat"] or 0))
        except Exception:
            pass
    approvals = list(db.scalars(select(Approval).where(Approval.user_id == user.id)))
    reasons = Counter((a.reason or "").strip().lower() for a in approvals if a.action == "reject" and a.reason)
    return AnalyticsOut(
        by_category=cats, connects_spent_total=connects_total, outcomes=dict(outcomes),
        connects_per_reply=round(connects_total / replies, 2) if replies else None,
        cost_per_proposal_usd=round(sum(costs) / len(costs), 6) if costs else None,
        latency_p50_ms=_pct(latencies, 0.5), latency_p95_ms=_pct(latencies, 0.95), runs_measured=len(costs),
        top_rejection_reasons=[{"reason": r, "count": c} for r, c in reasons.most_common(10)],
        approvals=dict(Counter(a.action for a in approvals)),
        note=("latency = sum of node latencies per run from trace_events" if costs else "cost/latency not measured yet (no trace_events for this user's runs)"))
