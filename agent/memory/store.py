"""Long-term memory on a LangGraph BaseStore (style + outcome), written only via promotion rules.

Namespaces:
  ("style_events", user_id)            raw edit pattern counters (operational, not memory)
  ("style", user_id)                   promoted style rules, key = rule (e.g. "never_say:passionate")
  ("outcome_events", user_id, cat)     raw outcome counters per category
  ("outcome", user_id, cat)            promoted outcome summary, key "summary"
"""
from __future__ import annotations

import datetime as dt
import os

from langgraph.store.base import BaseStore

from agent.memory.promotion_rules import (POSITIVE, edit_patterns, outcome_hints, should_promote_outcome,
                                          should_promote_style)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def record_edit(store: BaseStore, user_id: str, before: str, after: str, job_id: str = "", category: str = "") -> list[str]:
    """Count edit patterns; promote any pattern that meets the rule. Returns newly promoted rules."""
    promoted = []
    for pat in edit_patterns(before, after):
        ns = ("style_events", user_id)
        cur = store.get(ns, pat)
        val = dict(cur.value) if cur else {"count": 0, "jobs": []}
        if job_id and job_id in val["jobs"]:
            continue
        val["count"] += 1
        val["jobs"] = (val["jobs"] + [job_id])[-20:]
        store.put(ns, pat, val)
        if should_promote_style(val["count"]) and store.get(("style", user_id), pat) is None:
            store.put(("style", user_id), pat, {"rule": pat, "evidence_edits": val["count"], "promoted_at": _now(),
                                                "source": "user_edits"})
            promoted.append(pat)
    return promoted


def record_outcome_event(store: BaseStore, user_id: str, category: str, status: str, strategy: str | None = None,
                         proposal_id: str = "") -> bool:
    """Feed one marketplace outcome event (proposal_status). Returns True when the summary was (re)promoted."""
    cat = category or "general"
    ns = ("outcome_events", user_id, cat)
    cur = store.get(ns, "counts")
    val = dict(cur.value) if cur else {"counts": {}, "strategies": {}, "seen": []}
    key = f"{proposal_id}:{status}"
    if proposal_id and key in val["seen"]:
        return False
    val["seen"] = (val["seen"] + [key])[-500:]
    val["counts"][status] = val["counts"].get(status, 0) + 1
    if strategy:
        s = val["strategies"].setdefault(strategy, {"sent": 0, "positive": 0})
        if status == "submitted":
            s["sent"] += 1
        if status in POSITIVE:
            s["positive"] += 1
    store.put(ns, "counts", val)
    if should_promote_outcome(val["counts"]):
        store.put(("outcome", user_id, cat), "summary", {
            "category": cat, "counts": val["counts"], "hints": outcome_hints(val["counts"], val["strategies"]),
            "promoted_at": _now(), "source": "marketplace_outcomes"})
        return True
    return False


def list_memory(store: BaseStore, user_id: str) -> dict:
    style = [{"key": i.key, **i.value} for i in store.search(("style", user_id), limit=100)]
    outcome = [{"namespace": list(i.namespace), **i.value} for i in store.search(("outcome", user_id), limit=100)]
    return {"style": style, "outcome": outcome}


def delete_memory(store: BaseStore, namespace: tuple, key: str) -> None:
    store.delete(namespace, key)


def make_store(url: str | None = None) -> BaseStore:
    """Store matching DATABASE_URL: PostgresStore for postgres, SqliteStore for sqlite, else in-memory."""
    url = url or os.environ.get("DATABASE_URL", "")
    if url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
        from langgraph.store.postgres import PostgresStore
        from psycopg import Connection

        conn = Connection.connect(url.replace("postgresql+psycopg://", "postgresql://"), autocommit=True, prepare_threshold=0)
        st = PostgresStore(conn)
        st.setup()
        return st
    if url.startswith("sqlite:///"):
        import sqlite3

        from langgraph.store.sqlite import SqliteStore

        path = url[len("sqlite:///"):]
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        st = SqliteStore(sqlite3.connect(path.replace(".db", "_store.db"), check_same_thread=False, isolation_level=None))
        st.setup()
        return st
    from langgraph.store.memory import InMemoryStore

    return InMemoryStore()


def promote_outcomes_from_events(store: BaseStore, user_id: str, events: list[dict], proposals_meta: dict) -> int:
    """Consume GigSim /events (proposal_status) → outcome memory. proposals_meta: proposal_id → {category, strategy}."""
    n = 0
    for e in events:
        if e.get("type") != "proposal_status":
            continue
        pid = e.get("proposal_id") or (e.get("data") or {}).get("proposal_id")
        status = e.get("status") or (e.get("data") or {}).get("status")
        meta = proposals_meta.get(pid, {})
        if status and record_outcome_event(store, user_id, meta.get("category", "general"), status,
                                           meta.get("strategy"), pid or ""):
            n += 1
    return n
