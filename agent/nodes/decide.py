"""Decision node: skip / watch / bid from RiskReport + FitReport + budget rules (all thresholds in config)."""
from __future__ import annotations

from agent.handoffs import BidDecision
from agent.nodes.base import Deps
from agent.retrieval import load_profile
from agent.settings import cfg


def decide(state: dict, deps: Deps) -> dict:
    job, risk, fit = state["job"], state.get("risk") or {}, state.get("fit") or {}
    th = cfg("thresholds", default={}) or {}
    opts = state.get("options") or {}
    profile = load_profile(state.get("persona") or "aiml")
    reasons: list[str] = []
    fit_score = float(fit.get("fit_score", 0.0))
    action, conf = None, 0.7
    high = [f for f in risk.get("flags", []) if f.get("severity") == "high" and f.get("code") != "prompt_injection"]
    if risk.get("is_scam"):
        action, conf = "skip", 0.9
        reasons.append("scam signals: " + ", ".join(sorted({f["code"] for f in risk.get("flags", [])})))
    elif th.get("scam_flag_high_blocks", True) and high:
        action, conf = "skip", 0.8
        reasons.append("high-severity risk: " + ", ".join(sorted({f["code"] for f in high})))
    elif float(risk.get("client_score", 1.0)) < float(th.get("client_score_min", 0.25)):
        action = "skip"
        reasons.append(f"client score {risk.get('client_score')} below minimum")
    elif state.get("duplicate_of"):
        action = "skip"
        reasons.append(f"duplicate of {state['duplicate_of']}")
    if action is None:
        bmax = job.get("budget_max")
        if job.get("budget_type") == "hourly" and bmax is not None:
            floor = float(profile.get("hourly_floor", 0)) * float(th.get("min_hourly_ratio_of_floor", 1.0))
            if float(bmax) < floor:
                action = "skip"
                reasons.append(f"hourly budget {bmax} below floor {floor:g}")
        elif job.get("budget_type") == "fixed" and bmax is not None and float(bmax) < float(th.get("min_fixed_budget", 0)):
            action = "skip"
            reasons.append(f"fixed budget {bmax} below minimum {th.get('min_fixed_budget')}")
        elif job.get("budget_type") == "fixed" and bmax is not None:
            from agent.nodes.pricing import estimate_hours

            hrs = estimate_hours(job)
            need = hrs * float(profile.get("hourly_floor", 0)) * float(th.get("fixed_floor_ratio", 0.6)) if hrs else 0
            if need and float(bmax) < need:
                action = "skip"
                reasons.append(f"fixed budget {bmax:g} implies under the hourly floor for ~{hrs:g}h of work")
    so = fit.get("skill_overlap")
    if action is None and so is not None and float(so) < float(th.get("min_skill_overlap", 0.0)):
        action, conf = "skip", 0.75
        reasons.append(f"off-profile: only {float(so):.0%} of the listed skills match the profile")
    if action is None:
        if fit_score >= float(th.get("fit_bid", 0.45)):
            action, conf = "bid", min(0.95, 0.5 + fit_score / 2)
        elif fit_score >= float(th.get("fit_watch", 0.3)):
            action, conf = "watch", 0.5
        else:
            action, conf = "skip", 0.7
        reasons.append(f"fit score {fit_score:.2f}")
        reasons += (fit.get("reasons") or [])[:3]
    if risk.get("injection_detected"):
        reasons.append("job post contains instructions aimed at AI tools; they are ignored")
    decision = BidDecision(job_id=job["id"], action=action, confidence=round(conf, 2), reasons=reasons)
    out: dict = {"decision": decision.model_dump()}
    autonomy = opts.get("autonomy") or cfg("autonomy", "default", default="suggest")
    if action == "skip":
        auto = autonomy == "auto_skip" and fit_score < float(cfg("autonomy", "auto_skip_below_fit", default=0.2))
        out["status"] = "auto_skipped" if auto else "skipped"
        out["status_reason"] = "; ".join(reasons)[:400]
    elif action == "watch":
        out["status"] = "watching"
        out["status_reason"] = "; ".join(reasons)[:400]
    return out
