"""Dry-run preview, human approval (interrupt), idempotent submit, and terminal nodes."""
from __future__ import annotations

import difflib
import hashlib

from langgraph.types import interrupt

from agent.handoffs import ApprovalDecision
from agent.marketplace_port import MarketplaceError, MarketplaceUnavailable
from agent.nodes.base import Deps
from agent.nodes.compliance import check_text


def idempotency_key(thread_id: str, version: int | str, kind: str = "proposal") -> str:
    return f"{kind[:4]}-" + hashlib.sha256(f"{thread_id}:{version}".encode()).hexdigest()[:32]


def preview(state: dict, deps: Deps) -> dict:
    """Ask the marketplace what would be sent and what it costs (dry_run: nothing is created or spent)."""
    draft, price = state["draft"], state.get("price") or {}
    try:
        p = deps.port(state).submit_proposal(state["job"]["id"], draft["cover_letter"], draft.get("screening_answers") or [],
                                             float(price.get("amount", 0)), idempotency_key(state.get("thread_id", ""), draft.get("version", 1)) + "-dry",
                                             dry_run=True)
        return {"preview": p, "status": "awaiting_approval"}
    except MarketplaceUnavailable as exc:
        return {"preview": {"unavailable": True, "error": str(exc)[:200]}, "degraded": ["dry_run_unavailable"],
                "status": "awaiting_approval"}
    except MarketplaceError as exc:
        return {"preview": {"error": str(exc)[:300]}, "status": "awaiting_approval"}


def approval_payload(state: dict) -> dict:
    draft = state["draft"]
    return {
        "type": "proposal_approval",
        "thread_id": state.get("thread_id"),
        "job_id": state["job"]["id"],
        "job": {k: state["job"].get(k) for k in ("id", "title", "category", "budget_type", "budget_min", "budget_max",
                                                 "connects_cost", "screening_questions", "posted_at")},
        "draft": {"version": draft.get("version"), "cover_letter": draft.get("cover_letter"),
                  "screening_answers": draft.get("screening_answers"), "strategy": draft.get("strategy")},
        "claims": draft.get("claims") or [],
        "unsupported_before": draft.get("unsupported_before", 0),
        "unsupported_after": draft.get("unsupported_after", 0),
        "evidence": (state.get("fit") or {}).get("matches", []),
        "risk": state.get("risk"),
        "decision": state.get("decision"),
        "price": state.get("price"),
        "critiques": state.get("critiques") or [],
        "compliance": state.get("compliance"),
        "dry_run": state.get("preview"),
        "actions": ["approve", "edit", "reject"],
    }


def approval(state: dict, deps: Deps) -> dict:
    """interrupt() with the full payload; resume with {"action": "approve"|"edit"|"reject", ...}."""
    raw = interrupt(approval_payload(state))
    if isinstance(raw, str):
        raw = {"action": raw}
    decision = ApprovalDecision(**raw)
    rec = decision.model_dump()
    out: dict = {"approval": rec, "approvals": [rec]}
    if decision.action == "reject":
        out.update(status="rejected", status_reason=f"rejected by user: {decision.reason or 'no reason given'}")
        return out
    if decision.action == "edit" and decision.edited_text:
        draft = dict(state["draft"])
        before = draft.get("cover_letter", "")
        diff = list(difflib.unified_diff(before.splitlines(), decision.edited_text.splitlines(), lineterm="", n=0))
        rec["diff"] = diff[:200]
        try:
            from langgraph.config import get_store

            from agent.memory.store import record_edit

            store = get_store()
            if store is not None:
                record_edit(store, state.get("user_id") or decision.user_id or "anonymous", before, decision.edited_text,
                            job_id=state["job"]["id"], category=state["job"].get("category", ""))
        except Exception:
            pass
        v, _ = check_text(state["job"]["id"], decision.edited_text, "proposal")  # edits are re-checked
        draft.update(cover_letter=v["cleaned_text"], version=int(draft.get("version", 1)) + 1, edited=True)
        out["draft"] = draft
        out["drafts"] = [draft]
        out["compliance"] = v
        if not v["allowed"]:
            out.update(status="needs_attention", status_reason=f"edited draft blocked by compliance: {v['reason']}"[:400])
    return out


def submit(state: dict, deps: Deps) -> dict:
    """Submit exactly once: skip if already submitted; marketplace dedupes on the idempotency key."""
    if (state.get("submission") or {}).get("status") == "submitted":
        return {}
    draft, price = state["draft"], state.get("price") or {}
    key = idempotency_key(state.get("thread_id", ""), draft.get("version", 1))
    try:
        res = deps.port(state).submit_proposal(state["job"]["id"], draft["cover_letter"], draft.get("screening_answers") or [],
                                               float(price.get("amount", 0)), key, dry_run=False)
    except MarketplaceError as exc:
        return {"status": "needs_attention", "status_reason": f"marketplace refused the proposal: {exc}"[:400],
                "errors": [str(exc)[:300]]}
    return {"submission": {**res, "idempotency_key": key}, "status": "submitted",
            "status_reason": f"submitted proposal {res.get('proposal_id')}"}


def needs_attention(state: dict, deps: Deps) -> dict:
    return {"status": "needs_attention", "status_reason": state.get("status_reason") or "needs attention"}


def dead_letter(state: dict, deps: Deps) -> dict:
    return {"status": "dead_letter", "status_reason": state.get("status_reason") or "could not complete"}
