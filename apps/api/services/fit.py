"""Fast inbox pre-ranking. A cheap, deterministic score (skill overlap with the persona profile plus
policy-pack red-flag patterns) so the inbox is sorted by fit before any graph run. Once the agent has
analysed a job, its FitReport score replaces this estimate."""
from __future__ import annotations

import json
import re
from functools import lru_cache

import yaml

from ..config import ROOT, cfg


@lru_cache(maxsize=8)
def persona_profile(persona: str) -> dict:
    path = ROOT / "data" / "personas" / persona / "profile.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}


@lru_cache(maxsize=1)
def _risk_patterns() -> list[tuple[str, re.Pattern, str]]:
    out: list[tuple[str, re.Pattern, str]] = []
    path = ROOT / "data" / "policy_pack" / "rules.yaml"
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text()) or {}
            for rule in data.get("rules", []):
                if rule.get("kind", "regex") != "regex":
                    continue
                for p in rule.get("patterns", []) or []:
                    try:
                        out.append((rule.get("id", "rule"), re.compile(p, re.I), rule.get("action", "block")))
                    except re.error:
                        continue
        except Exception:
            pass
    for p in cfg("injection.patterns", []) or cfg("guardrails.injection_patterns", []) or []:
        try:
            out.append(("prompt_injection", re.compile(p, re.I), "block"))
        except re.error:
            continue
    return out


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", " ", s.lower()).strip()


def quick_fit(job: dict, persona: str | None, user_settings: dict | None = None) -> dict:
    profile = persona_profile(persona or "aiml")
    skills = {_norm(s) for s in profile.get("skills", [])}
    req = [_norm(s) for s in job.get("skills_required", []) or []]
    text = _norm(f"{job.get('title', '')} {job.get('description', '')}")
    if req:
        hits = sum(1 for r in req if r in skills or any(r in s or s in r for s in skills if len(s) > 2))
        overlap = hits / len(req)
    else:
        overlap = 0.0
    mention = sum(1 for s in skills if len(s) > 2 and f" {s} " in f" {text} ")
    mention_score = min(mention / 5.0, 1.0)
    score = 0.75 * overlap + 0.25 * mention_score

    flags: list[dict] = []
    raw = f"{job.get('title', '')}\n{job.get('description', '')}"
    for rule_id, pat, _action in _risk_patterns():
        m = pat.search(raw)
        if m and not any(f["code"] == rule_id for f in flags):
            flags.append({"code": rule_id, "evidence": m.group(0)[:120]})
    risk_level = "high" if flags else "low"

    floor = (user_settings or {}).get("rates", {}).get("hourly_floor") or profile.get("hourly_floor")
    if job.get("budget_type") == "hourly" and floor and job.get("budget_max") and job["budget_max"] < floor:
        score *= 0.5
        flags.append({"code": "below_floor", "evidence": f"max {job['budget_max']}/h < floor {floor}/h"})
        risk_level = "medium" if risk_level == "low" else risk_level

    fit_bid = float(cfg("thresholds.fit_bid", cfg("decide.fit_bid", 0.6)))
    fit_watch = float(cfg("thresholds.fit_watch", cfg("decide.fit_watch", 0.4)))
    if risk_level == "high":
        action = "skip"
    elif score >= fit_bid:
        action = "bid"
    elif score >= fit_watch:
        action = "watch"
    else:
        action = "skip"
    price = None
    if job.get("budget_max") or job.get("budget_min"):
        lo, hi = job.get("budget_min") or job.get("budget_max"), job.get("budget_max") or job.get("budget_min")
        price = round((lo + hi) / 2, 2)
        if job.get("budget_type") == "hourly" and profile.get("hourly_target"):
            price = float(min(max(profile["hourly_target"], lo), hi))
    return {"fit_score": round(score, 4), "recommended_action": action, "risk_level": risk_level,
            "risk_flags": flags, "price": price}
