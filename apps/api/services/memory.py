"""Edit diffing + hand-off to the agent's memory promotion rules, and the memory viewer."""
from __future__ import annotations

import difflib
import logging
import re
from typing import Any

from ..integrations import first_attr
from ..streaming import to_jsonable

log = logging.getLogger("gigbid.memory")
KINDS = ("style", "outcome", "style_events", "outcome_events", "edits")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s.strip()]


def diff_texts(original: str, edited: str) -> dict:
    a, b = _sentences(original), _sentences(edited)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    ops = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        ops.append({"op": tag, "before": a[i1:i2], "after": b[j1:j2]})
    unified = list(difflib.unified_diff((original or "").splitlines(), (edited or "").splitlines(),
                                        "draft", "edited", lineterm="", n=1))
    first_a, first_b = (a[0] if a else ""), (b[0] if b else "")
    return {
        "ops": ops,
        "similarity": round(difflib.SequenceMatcher(a=original or "", b=edited or "").ratio(), 4),
        "opening_changed": first_a != first_b,
        "opening_before": first_a,
        "opening_after": first_b,
        "length_before": len(original or ""),
        "length_after": len(edited or ""),
        "length_delta": len(edited or "") - len(original or ""),
        "removed": [s for o in ops for s in o["before"] if s not in b],
        "added": [s for o in ops for s in o["after"] if s not in a],
        "unified": "\n".join(unified[:400]),
    }


async def record_edit(store, user_id: str, before: str, after: str, context: dict | None = None,
                      graph_records: bool = True) -> dict:
    """Hand the edit to the agent's promotion rules. Style memory is promoted only when the same
    pattern repeats across edits (agent/memory/promotion_rules.py). For proposal edits the bid graph's
    approval node records the edit on resume (graph_records=True), so here we only report the
    detected patterns; otherwise we record it ourselves."""
    import asyncio
    ctx = context or {}
    patterns_fn = first_attr("agent.memory.promotion_rules", ["edit_patterns"])
    patterns = patterns_fn(before, after) if patterns_fn else []
    if graph_records:
        return {"handled_by": "agent.nodes.approval", "patterns": patterns, "promoted": []}
    rec = first_attr("agent.memory.store", ["record_edit"])
    if rec is not None and store is not None:
        try:
            promoted = await asyncio.to_thread(rec, store, user_id, before, after, ctx.get("job_id") or
                                               ctx.get("thread_id", ""), ctx.get("category") or "")
            return {"handled_by": "agent.memory.store.record_edit", "patterns": patterns,
                    "promoted": to_jsonable(promoted)}
        except Exception as exc:  # noqa: BLE001
            log.exception("memory promotion failed")
            return {"handled_by": None, "patterns": patterns, "error": f"{type(exc).__name__}: {exc}"[:300]}
    if store is not None:  # agent memory module missing: keep the raw observation for later promotion
        import uuid
        await asyncio.to_thread(store.put, ("edits", user_id), uuid.uuid4().hex,
                                {"before": before[:4000], "after": after[:4000], "context": ctx})
    return {"handled_by": "api.fallback", "patterns": patterns, "promoted": []}


async def record_outcome(store, user_id: str, category: str, status: str, proposal_id: str) -> bool:
    """Outcome memory is fed only from marketplace proposal-status events."""
    import asyncio
    fn = first_attr("agent.memory.store", ["record_outcome_event"])
    if fn is None or store is None:
        return False
    try:
        return bool(await asyncio.to_thread(fn, store, user_id, category, status, None, proposal_id))
    except Exception:  # noqa: BLE001
        log.exception("outcome memory update failed")
        return False


def _arity(fn) -> int:
    import inspect
    try:
        return len(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        return 3


def _list_memory_sync(store, user_id: str) -> list[dict]:
    out: list[dict] = []
    for kind in KINDS:
        try:
            namespaces = store.list_namespaces(prefix=(kind, user_id), limit=200)
        except Exception:
            namespaces = [(kind, user_id)]
        if (kind, user_id) not in namespaces:
            namespaces = [(kind, user_id), *namespaces]
        for ns in namespaces:
            try:
                items = store.search(ns, limit=200)
            except Exception:
                continue
            for it in items:
                if tuple(it.namespace) != tuple(ns):
                    continue
                out.append({"namespace": list(it.namespace), "key": it.key, "value": to_jsonable(it.value),
                            "kind": kind, "created_at": str(getattr(it, "created_at", "") or ""),
                            "updated_at": str(getattr(it, "updated_at", "") or "")})
    return out


async def list_memory(store, user_id: str) -> list[dict]:
    import asyncio
    if store is None:
        return []
    return await asyncio.to_thread(_list_memory_sync, store, user_id)


async def delete_memory(store, user_id: str, namespace: list[str], key: str) -> bool:
    import asyncio
    if store is None or len(namespace) < 2 or namespace[1] != user_id or namespace[0] not in KINDS:
        return False  # tenant scope: a user may only delete their own namespaces
    existing = await asyncio.to_thread(store.get, tuple(namespace), key)
    if existing is None:
        return False
    await asyncio.to_thread(store.delete, tuple(namespace), key)
    return True


def to_any(v: Any) -> Any:
    return to_jsonable(v)
