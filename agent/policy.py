"""Policy-pack driven checks: injection detection on inbound text and compliance on outbound text.

All patterns, actions and limits come from data/policy_pack/rules.yaml (+ updates/*.yaml whose effective
date has passed), so a platform policy change is absorbed by editing config only.
"""
from __future__ import annotations

import re
from typing import Iterable

from agent.settings import cfg, load_policy, max_proposal_chars

UNTRUSTED_TAGS = {
    "job": "untrusted_job_post",
    "message": "untrusted_client_message",
    "evidence": "untrusted_evidence",
    "draft": "untrusted_draft",
}


def wrap_untrusted(text: str, kind: str = "job") -> str:
    """Neutralise delimiter tags inside third-party text.

    The prompt templates put the text between <untrusted_*> tags (UNTRUSTED_TAGS[kind]); removing any
    tag the author planted stops the text from closing the delimiter early.
    """
    safe = re.sub(r"</?\s*untrusted_[a-z_]*\s*>", "[tag removed]", text or "", flags=re.I)
    return safe  # the prompt templates place the delimiters around the substituted text


def _scopes(rule: dict) -> set[str]:
    sc = rule.get("applies_to") or rule.get("scope") or rule.get("targets")
    if sc is None:
        return set()
    if isinstance(sc, str):
        sc = [sc]
    return {str(s).lower() for s in sc}


def _is_injection_rule(rule: dict) -> bool:
    blob = f"{rule.get('id', '')} {rule.get('category', '')} {rule.get('type', '')}".lower()
    return "inject" in blob


def _compile(patterns: Iterable[str]) -> list[re.Pattern]:
    out = []
    for p in patterns or []:
        try:
            out.append(re.compile(p, re.I))
        except re.error:
            out.append(re.compile(re.escape(p), re.I))
    return out


def injection_rules() -> list[dict]:
    rules = [r for r in load_policy().get("rules", []) if _is_injection_rule(r)]
    if not rules:  # policy pack missing: conservative fallback patterns from agent/config.yaml
        rules = [{"id": "prompt_injection", "kind": "regex", "action": "block",
                  "patterns": cfg("risk", "injection_fallback_patterns", default=[])}]
    return rules


def detect_injection(text: str) -> list[dict]:
    """Return [{rule_id, snippet}] for injection patterns found in inbound (untrusted) text."""
    hits = []
    for r in injection_rules():
        if r.get("kind", "regex") != "regex":
            continue
        for rx in _compile(r.get("patterns")):
            m = rx.search(text or "")
            if m:
                s = max(0, m.start() - 20)
                hits.append({"rule_id": r.get("id"), "snippet": (text[s:m.end() + 30]).strip()})
                break
    return hits


def outbound_rules() -> list[dict]:
    out = []
    for r in load_policy().get("rules", []):
        if _is_injection_rule(r):
            continue
        sc = _scopes(r)
        if sc and not sc & {"proposal", "proposals", "outbound", "message", "messages", "reply", "all", "draft"}:
            continue
        out.append(r)
    return out


def check_outbound(text: str, kind: str = "proposal") -> dict:
    """Apply regex rules (block / redact) and length limits to outgoing text.

    Returns {allowed, violations[rule ids], redactions[rule ids], cleaned_text, reasons[]}.
    """
    cleaned = text or ""
    violations: list[str] = []
    redactions: list[str] = []
    reasons: list[str] = []
    for r in outbound_rules():
        if r.get("kind", "regex") != "regex":
            continue
        sc = _scopes(r)
        if sc and kind == "message" and not sc & {"message", "messages", "reply", "all", "outbound"}:
            continue
        if sc and kind == "proposal" and not sc & {"proposal", "proposals", "all", "outbound", "draft"}:
            continue
        action = str(r.get("action", "block")).lower()
        for rx in _compile(r.get("patterns")):
            if rx.search(cleaned):
                if action == "redact":
                    cleaned = rx.sub("[removed]", cleaned)
                    if r.get("id") not in redactions:
                        redactions.append(r.get("id"))
                else:
                    if r.get("id") not in violations:
                        violations.append(r.get("id"))
                        reasons.append(f"{r.get('id')}: {r.get('description', '')}".strip())
    limit = max_proposal_chars() if kind == "proposal" else None
    if limit and len(cleaned) > limit and (_length_rule_id() or "max_proposal_chars") not in violations:
        rid = _length_rule_id() or "max_proposal_chars"
        violations.append(rid)
        reasons.append(f"{rid}: proposal is {len(cleaned)} characters, limit {limit}")
    return {"allowed": not violations, "violations": violations, "redactions": redactions,
            "cleaned_text": cleaned, "reasons": reasons}


def _length_rule_id() -> str | None:
    for r in load_policy().get("rules", []):
        if r.get("max_chars") or "length" in str(r.get("id", "")) or r.get("kind") in ("length", "max_chars", "max_length"):
            return r.get("id")
    return None


def connects_cost(job: dict) -> int:
    """Connects cost for a job: the job's listed cost plus any policy-pack surcharges in force."""
    import datetime as dt

    pol = load_policy()
    bidding = pol.get("bidding") or {}
    base = job.get("connects_cost")
    if base is None:
        base = bidding.get("connects_per_proposal_default", 4)
    cost = int(base)
    surcharges = list(bidding.get("surcharges") or pol.get("surcharges") or [])
    for key, val in bidding.items():  # e.g. early_bird_surcharge: {connects, window_minutes}
        if isinstance(val, dict) and "surcharge" in key:
            surcharges.append({"connects": val.get("connects", 0),
                               "when": {"posted_within_minutes": val.get("window_minutes", 60)}})
    for s in surcharges:
        cond = s.get("when") or s.get("condition") or {}
        extra = int(s.get("extra_connects") or s.get("connects") or s.get("amount") or 0)
        if "posted_within_minutes" in cond or "posted_within_hours" in cond:
            mins = cond.get("posted_within_minutes") or 60 * cond.get("posted_within_hours")
            posted = job.get("posted_at")
            now = job.get("_now")
            try:
                pdt = dt.datetime.fromisoformat(str(posted).replace("Z", "+00:00"))
                ndt = dt.datetime.fromisoformat(str(now).replace("Z", "+00:00")) if now else dt.datetime.now(dt.timezone.utc)
                if pdt.tzinfo is None:
                    pdt = pdt.replace(tzinfo=dt.timezone.utc)
                if ndt.tzinfo is None:
                    ndt = ndt.replace(tzinfo=dt.timezone.utc)
                if (ndt - pdt).total_seconds() / 60 < float(mins):
                    cost += extra
            except (ValueError, TypeError):
                pass
        elif "min_proposals" in cond:
            if int(job.get("proposals_count") or 0) >= int(cond["min_proposals"]):
                cost += extra
    return cost
