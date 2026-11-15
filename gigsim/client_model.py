"""Simulated client decision model.

``score_proposal`` is a pure, deterministic function of (job_id, cover_letter, bid_amount): it reads the job
and the client's hidden preferences from gigsim/seed_data and returns reply/interview/hire outcomes.
Weights live in gigsim/config.yaml. An optional Ollama-backed judgement (env GIGSIM_CLIENT_LLM=1) can be
blended in by the simulator's tick; it is off by default so results stay reproducible.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from functools import lru_cache

from gigsim import vocab as V
from gigsim.storage import PKG, SEED_DIR, config


@lru_cache(maxsize=1)
def _jobs() -> dict:
    jobs = {s["job"]["id"]: s["job"] for s in json.loads((SEED_DIR / "jobs_stream.json").read_text())}
    jobs.update({j["id"]: j for j in json.loads((SEED_DIR / "jobs_dev.json").read_text())})
    return jobs


@lru_cache(maxsize=1)
def _hidden() -> dict:
    return json.loads((SEED_DIR / "hidden.json").read_text())["jobs"]


@lru_cache(maxsize=1)
def _aliases() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for p in V.PERSONAS.values():
        for name, info in p["skills"].items():
            out.setdefault(name, {name}).update(a.lower() for a in info["aliases"])
    return out


def _mentions(text: str, skill: str) -> bool:
    t = text.lower()
    for term in _aliases().get(skill, {skill}):
        if re.search(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])", t):
            return True
    return False


def _uniform(*parts) -> float:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:12], 16) / float(16 ** 12)


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def deterministic_prob(job: dict, prefs: dict, cover_letter: str, bid_amount: float, screening_answers=None) -> tuple[float, dict]:
    w = config()["client_model"]
    factors: dict[str, float] = {}
    p = w["base"]
    must = prefs.get("must_have_skills") or []
    if must:
        frac = sum(_mentions(cover_letter, s) for s in must) / len(must)
        factors["must_have"] = w["must_have_weight"] * frac
    ceiling = prefs.get("budget_ceiling") or job.get("budget_max") or 0
    if ceiling and bid_amount is not None:
        if bid_amount <= ceiling:
            factors["budget"] = w["within_ceiling_bonus"]
        else:
            factors["budget"] = -w["over_ceiling_penalty"] * min(1.0, (bid_amount / ceiling - 1) * 2)
    opening = cover_letter.strip().lower()[:80]
    if any(opening.startswith(g) or g in opening[:40] for g in w["generic_openers"]):
        factors["generic_opening"] = -(w["generic_opening_penalty_disliked"] if prefs.get("dislikes_generic_opening") else w["generic_opening_penalty"])
    words = len(cover_letter.split())
    if words > w["long_words"] and prefs.get("prefers_short"):
        factors["length"] = -w["long_penalty_if_prefers_short"]
    elif words < w["short_words"]:
        factors["length"] = -w["too_short_penalty"]
    title_terms = {t for t in re.findall(r"[a-z][a-z0-9.+#-]{3,}", job.get("title", "").lower())}
    if title_terms and sum(t in cover_letter.lower() for t in title_terms) >= 2:
        factors["title_overlap"] = w["title_overlap_bonus"]
    if job.get("screening_questions") and screening_answers:
        factors["screening"] = w["screening_answered_bonus"]
    p += sum(factors.values())
    return _clip(p, w["min_prob"], w["max_prob"]), factors


def score_proposal(job_id: str, cover_letter: str, bid_amount: float, screening_answers=None, reply_prob_override: float | None = None) -> dict:
    """Return {reply_prob, replied, interview, hired, factors} for a proposal. Pure and deterministic."""
    job = _jobs().get(job_id)
    hidden = _hidden().get(job_id)
    if job is None or hidden is None:
        raise KeyError(f"unknown job {job_id}")
    if hidden.get("is_scam"):
        return dict(reply_prob=0.0, replied=False, interview=False, hired=False, factors={"scam_job": 1.0})
    prob, factors = deterministic_prob(job, hidden["prefs"], cover_letter, bid_amount, screening_answers)
    if reply_prob_override is not None:
        prob = reply_prob_override
    w = config()["client_model"]
    u1 = _uniform(job_id, cover_letter, bid_amount, "reply")
    u2 = _uniform(job_id, cover_letter, bid_amount, "interview")
    u3 = _uniform(job_id, cover_letter, bid_amount, "hire")
    replied = u1 < prob
    interview = replied and u2 < min(0.95, prob * w["interview_given_reply"] + 0.3)
    hired = interview and u3 < w["hire_given_interview"]
    return dict(reply_prob=round(prob, 4), replied=replied, interview=interview, hired=hired, factors=factors)


def llm_reply_prob(job: dict, prefs: dict, cover_letter: str, bid_amount: float) -> float | None:
    """Optional Ollama judgement; returns None on any failure so callers fall back to the deterministic score."""
    if os.environ.get("GIGSIM_CLIENT_LLM", "0") != "1":
        return None
    try:
        import httpx

        cfg = config()["client_model"]["llm"]
        tmpl = (PKG / "prompts" / "client_decision.md").read_text()
        prompt = tmpl.format(title=job["title"], description=job["description"], must_have=", ".join(prefs["must_have_skills"]),
                             ceiling=prefs["budget_ceiling"], dislikes_generic=prefs["dislikes_generic_opening"],
                             prefers_short=prefs["prefers_short"], bid=bid_amount, cover_letter=cover_letter)
        base = os.environ.get(cfg["base_url_env"], cfg["base_url_default"])
        r = httpx.post(f"{base}/api/generate", json=dict(model=cfg["model"], prompt=prompt, stream=False, format="json",
                                                         options={"temperature": 0, "seed": 42}), timeout=60)
        val = float(json.loads(r.json()["response"])["reply_prob"])
        return _clip(val, 0.0, 1.0)
    except Exception:
        return None
