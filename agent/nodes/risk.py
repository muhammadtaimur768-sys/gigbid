"""Risk Assessor: scam / injection / client-quality / duplicate checks → RiskReport."""
from __future__ import annotations

import re

from agent.handoffs import RiskFlag, RiskReport
from agent.llm import call_llm, is_heuristic
from agent.nodes.base import Deps, usage_from
from agent.nodes.text_utils import job_text
from agent.policy import detect_injection, wrap_untrusted
from agent.settings import cfg

SEVERITY = {"scam": "high", "free_work": "high", "off_platform_payment": "high", "off_platform_contact": "high",
            "unrealistic_budget": "medium"}


def client_score(client: dict) -> float:
    if not client:
        return 0.5
    s = 0.5
    rating = client.get("avg_rating")
    if rating is not None:
        s += (float(rating) - 4.0) * 0.2
    if client.get("payment_verified") is True:
        s += 0.15
    elif client.get("payment_verified") is False:
        s -= 0.25
    hires = client.get("hires") or 0
    s += min(0.15, 0.03 * float(hires))
    if (client.get("total_spent") or 0) > 1000:
        s += 0.05
    if (client.get("jobs_posted") or 0) > 3 and not hires:
        s -= 0.15
    return max(0.0, min(1.0, round(s, 3)))


def scan_scam(text: str) -> list[RiskFlag]:
    flags = []
    for code, pats in (cfg("risk", "scam_patterns", default={}) or {}).items():
        for p in pats:
            m = re.search(p, text, re.I)
            if m:
                s = max(0, m.start() - 30)
                flags.append(RiskFlag(code=code, severity=SEVERITY.get(code, "medium"),
                                      evidence=text[s:m.end() + 30].strip()[:200]))
                break
    return flags


def risk(state: dict, deps: Deps) -> dict:
    job = state["job"]
    text = job_text(job)
    inj = detect_injection(text)
    scan_text = text
    for h in inj:  # contact requests inside an injection are the injection, not a scam signal
        for sent in re.split(r"(?<=[.!?])\s+|\n+", text):
            if h["snippet"][:40] in sent or sent[:40] in h["snippet"]:
                scan_text = scan_text.replace(sent, " ")
    flags = scan_scam(scan_text)
    for h in inj:
        flags.append(RiskFlag(code="prompt_injection", severity="high", evidence=h["snippet"][:200]))
    client = state.get("client") or {}
    cs = client_score(client)
    low = cfg("risk", "low_client", default={}) or {}
    if client and ((client.get("avg_rating") is not None and float(client["avg_rating"]) < low.get("min_avg_rating", 3.5))
                   or (low.get("require_payment_verified") and client.get("payment_verified") is False)):
        flags.append(RiskFlag(code="low_client_quality", severity="medium",
                              evidence=f"rating={client.get('avg_rating')} verified={client.get('payment_verified')}"))
    if state.get("duplicate_of"):
        flags.append(RiskFlag(code="duplicate", severity="medium", evidence=f"same text as {state['duplicate_of']}"))
    scam_codes = {"scam", "free_work", "off_platform_payment", "off_platform_contact", "unrealistic_budget"}
    n_high = sum(1 for f in flags if f.code in scam_codes and f.severity == "high")
    n_med = sum(1 for f in flags if f.code in scam_codes and f.severity == "medium")
    is_scam = n_high >= int(cfg("risk", "scam_min_high_flags", default=1)) or n_med >= 2
    summary = ", ".join(sorted({f.code for f in flags})) or "no risk signals"
    res = None
    if not is_heuristic("risk"):
        res = call_llm("risk", "risk", {"hits": summary, "client": {k: client.get(k) for k in ("avg_rating", "payment_verified", "hires", "total_spent")},
                                        "job_text": wrap_untrusted(text[:3500], "job")}, json_mode=True)
        if res.ok and isinstance(res.data, dict):
            if res.data.get("is_scam") and not is_scam and cs < 0.6:
                is_scam = True
                flags.append(RiskFlag(code="scam", severity="medium", evidence=str(res.data.get("summary", ""))[:200]))
            if res.data.get("injection_detected") and not inj:
                flags.append(RiskFlag(code="prompt_injection", severity="medium", evidence="model judgement"))
            summary = (str(res.data.get("summary") or "")[:300] or summary)
    report = RiskReport(job_id=job["id"], client_score=cs, is_scam=is_scam,
                        injection_detected=any(f.code == "prompt_injection" for f in flags), flags=flags, summary=summary)
    return {"risk": report.model_dump(), "usage": usage_from(res)}
