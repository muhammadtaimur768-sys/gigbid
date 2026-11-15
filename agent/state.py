"""Typed graph state.

State = what this job / conversation needs right now. The execution trace (every tool call and node
event) lives in the `trace_events` table (agent/tracing.py), and long-term memory lives in the LangGraph
store (agent/memory). Hand-off objects are stored as `model_dump()` dicts of agent/handoffs.py models.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def merge_dict(a: dict | None, b: dict | None) -> dict:
    out = dict(a or {})
    out.update(b or {})
    return out


def add_usage(a: dict | None, b: dict | None) -> dict:
    out = dict(a or {})
    for k, v in (b or {}).items():
        if isinstance(v, (int, float)):
            out[k] = out.get(k, 0) + v
    return out


def last_value(a: Any, b: Any) -> Any:
    return b if b is not None else a


def status_reducer(a: str | None, b: str | None) -> str | None:
    """Last write wins, except a dead-letter is never downgraded to needs-attention in the same step."""
    if b is None:
        return a
    if a == "dead_letter" and b == "needs_attention":
        return a
    return b


class BidState(TypedDict, total=False):
    # identity
    thread_id: str
    trace_id: str
    user_id: str
    persona: str
    options: dict                      # per-run overrides (strategy, autonomy, critic_min_score ...)
    # job
    job_id: str
    job: dict                          # raw Job JSON from the marketplace (untrusted)
    client: dict                       # client history
    # analyses written by parallel branches (distinct keys) + shared reducers
    job_spec: dict                     # JobSpec
    risk: dict                         # RiskReport
    fit: dict                          # FitReport
    evidence: Annotated[list[dict], operator.add]   # EvidenceRef dicts
    # decision and price
    decision: dict                     # BidDecision
    price: dict                        # PriceQuote
    # drafting loop
    draft: dict                        # current ProposalDraft
    drafts: Annotated[list[dict], operator.add]     # every version
    critiques: Annotated[list[dict], operator.add]  # Critique per round
    critic_round: int
    compliance: dict                   # ComplianceVerdict
    preview: dict                      # dry_run preview from the marketplace
    # approval / submission / outcomes
    approval: dict                     # ApprovalDecision
    approvals: Annotated[list[dict], operator.add]
    submission: dict
    outcome: dict
    # control
    status: Annotated[str, status_reducer]  # running|skipped|watching|awaiting_approval|submitted|rejected|needs_attention|dead_letter
    status_reason: Annotated[str, last_value]
    duplicate_of: str
    degraded: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]
    steps: Annotated[int, operator.add]
    usage: Annotated[dict, add_usage]  # {"tokens": int, "cost_usd": float}
    node_log: Annotated[list[str], operator.add]


class ConvState(TypedDict, total=False):
    thread_id: str
    trace_id: str
    user_id: str
    persona: str
    options: dict
    conversation_id: str               # marketplace thread id
    job_id: str
    job: dict
    messages: list[dict]
    intent: dict                       # MessageIntent
    slots: list[dict]
    reply: dict                        # ReplyDraft
    compliance: dict
    approval: dict
    approvals: Annotated[list[dict], operator.add]
    sent: dict
    status: Annotated[str, status_reducer]
    status_reason: Annotated[str, last_value]
    degraded: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]
    steps: Annotated[int, operator.add]
    usage: Annotated[dict, add_usage]
    node_log: Annotated[list[str], operator.add]


TERMINAL_STATUSES = {"skipped", "watching", "submitted", "rejected", "needs_attention", "dead_letter",
                     "sent", "flagged_scam", "auto_skipped"}


def usage_total(state: dict) -> int:
    return int((state.get("usage") or {}).get("tokens", 0))

