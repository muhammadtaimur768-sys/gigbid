"""Pricing Strategist: market stats + profile rates + client range + Connects → PriceQuote."""
from __future__ import annotations

from agent.handoffs import PriceQuote
from agent.llm import call_llm, is_heuristic
from agent.marketplace_port import MarketplaceUnavailable
from agent.nodes.base import Deps, usage_from
from agent.policy import connects_cost
from agent.retrieval import load_profile
from agent.settings import cfg


def estimate_hours(job: dict) -> float | None:
    table = {k.lower(): v for k, v in (cfg("pricing", "hours_by_duration", default={}) or {}).items()}
    return table.get(str(job.get("duration") or "").strip().lower())


def implied_hours(job: dict, hourly_p50: float | None) -> float | None:
    """Effort implied by the client's budget at the market hourly median, clamped to the timeline's range."""
    rng = {k.lower(): v for k, v in (cfg("pricing", "hours_range_by_duration", default={}) or {}).items()}
    lo_h, hi_h = rng.get(str(job.get("duration") or "").strip().lower(), [None, None])
    if not hourly_p50 or job.get("budget_max") is None:
        return estimate_hours(job)
    mid = (float(job.get("budget_min") or job["budget_max"]) + float(job["budget_max"])) / 2
    h = mid / float(hourly_p50)
    if lo_h is not None:
        h = min(max(h, lo_h), hi_h)
    return h


def pricing(state: dict, deps: Deps) -> dict:
    job, fit = state["job"], state.get("fit") or {}
    port = deps.port(state)
    profile = load_profile(state.get("persona") or "aiml")
    degraded = []
    try:
        stats = port.get_market_stats(job.get("category", ""))
    except MarketplaceUnavailable:
        stats, degraded = {}, ["market_stats_unavailable"]
    try:
        balance = int((port.get_connects_balance() or {}).get("balance", 0))
    except MarketplaceUnavailable:
        balance, degraded = -1, degraded + ["connects_unavailable"]
    btype = job.get("budget_type", "fixed")
    q = (stats or {}).get(btype) or {}
    p25, p50, p75 = q.get("p25"), q.get("p50"), q.get("p75")
    lo, hi = job.get("budget_min"), job.get("budget_max")
    floor, target = float(profile.get("hourly_floor", 30)), float(profile.get("hourly_target", 60))
    fs = float(fit.get("fit_score", 0.5))
    if btype == "hourly":
        amount = max(target, p50 or 0) if fs >= 0.6 else max(floor, min(target, p50 or target))
        if hi:
            amount = min(amount, float(hi))
        if lo:
            amount = max(amount, float(lo))
        amount = max(amount, floor)
    else:
        hrs = implied_hours(job, ((stats or {}).get("hourly") or {}).get("p50"))
        cap = float(cfg("pricing", "fixed_cap_ratio", default=1.05))
        if hrs and hi is not None:
            # never price the estimated effort below the freelancer's floor, even above the client's range
            amount = max(min(max(hrs * target, float(lo or 0)), float(hi) * cap), hrs * floor)
        elif lo is not None and hi is not None:
            pos = 0.45 + 0.3 * min(1.0, fs)  # stronger fit → higher inside the client's range
            amount = float(lo) + pos * (float(hi) - float(lo))
        elif hi is not None:
            amount = float(hi) * 0.85
        else:
            amount = float(p50 or 500)
    amount = round(amount / 5) * 5 if amount >= 50 else round(amount, 2)
    cost = connects_cost(job)
    worth = (balance < 0 or balance >= cost) and fs >= float(cfg("thresholds", "fit_watch", default=0.3))
    rationale = (f"{btype} bid {amount:g} inside client range {lo}-{hi}; market p25/p50/p75 {p25}/{p50}/{p75}; "
                 f"floor {floor:g}, target {target:g}; fit {fs:.2f}; {cost} connects (balance {balance if balance >= 0 else 'unknown'}).")
    res = None
    if not is_heuristic("pricing") and cfg("pricing", "llm_rationale", default=False):
        res = call_llm("pricing", "pricing", {"budget_type": btype, "budget": f"{lo}-{hi}", "market": f"{p25}/{p50}/{p75}",
                                              "floor": floor, "target": target, "amount": amount, "connects": cost,
                                              "balance": balance})
        if res.ok and res.text.strip():
            rationale = res.text.strip()[:400]
    quote = PriceQuote(job_id=job["id"], amount=float(amount), budget_type=btype, connects_cost=cost, worth_connects=worth,
                       rationale=rationale, market_p25=p25, market_p50=p50, market_p75=p75)
    return {"price": quote.model_dump(), "degraded": degraded, "usage": usage_from(res)}
