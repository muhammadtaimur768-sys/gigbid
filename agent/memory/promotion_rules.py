"""Explicit promotion rules: raw events never go straight into long-term memory.

Style memory: an edit pattern is promoted to ("style", user_id) only when it appears in at least
`memory.style.min_occurrences` separate edits.
Outcome memory: a category summary is promoted to ("outcome", user_id, category) only from marketplace
outcome events, once positive events (replied / interview / hired) reach `memory.outcome.min_positive_events`.
"""
from __future__ import annotations

import re

from agent.settings import cfg


def edit_patterns(before: str, after: str) -> list[str]:
    """Detect generalisable patterns in one user edit (deterministic)."""
    pats: list[str] = []
    b, a = (before or "").strip(), (after or "").strip()
    if not b or not a:
        return pats
    b_first = re.split(r"(?<=[.!?])\s+", b, maxsplit=1)[0]
    if b_first and b_first not in a and len(b_first) > 15:
        rest = b[len(b_first):].strip()
        if rest and a.startswith(rest[:40]):
            pats.append("cut_first_sentence")
    for w in cfg("memory", "style", "watch_words", default=[]) or []:
        if re.search(rf"\b{re.escape(w)}\b", b, re.I) and not re.search(rf"\b{re.escape(w)}\b", a, re.I):
            pats.append(f"never_say:{w}")
    if len(a) <= float(cfg("memory", "style", "shorten_ratio", default=0.8)) * len(b):
        pats.append("prefer_shorter")
    return pats


def should_promote_style(occurrences: int) -> bool:
    return occurrences >= int(cfg("memory", "style", "min_occurrences", default=2))


POSITIVE = {"replied", "interview", "hired", "won"}


def should_promote_outcome(counts: dict) -> bool:
    pos = sum(int(counts.get(k, 0)) for k in POSITIVE)
    return pos >= int(cfg("memory", "outcome", "min_positive_events", default=3))


def outcome_hints(counts: dict, strategies: dict) -> list[str]:
    hints = []
    tot = sum(strategies.get(s, {}).get("sent", 0) for s in strategies) or 0
    best = None
    for s, v in strategies.items():
        sent = v.get("sent", 0)
        rate = v.get("positive", 0) / sent if sent else 0
        if sent >= 2 and (best is None or rate > best[1]):
            best = (s, rate)
    if best:
        hints.append(f"strategy {best[0]} has the best reply rate here ({best[1]:.0%} of {tot} tracked proposals)")
    return hints
