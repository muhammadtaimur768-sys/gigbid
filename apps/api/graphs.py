"""LangGraph runtime: checkpointer + store lifecycle and compiled graphs.

Postgres (AsyncPostgresSaver / AsyncPostgresStore) when DATABASE_URL is postgres, else SQLite
(AsyncSqliteSaver / AsyncSqliteStore). Graphs come from agent/; when agent/ is missing or broken the
runtime reports the feature unavailable and the rest of the API still works."""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import ROOT, get_settings
from .integrations import optional

log = logging.getLogger("gigbid.graphs")


@dataclass
class GraphRuntime:
    checkpointer: Any = None
    store: Any = None
    bid_graph: Any = None
    conversation_graph: Any = None
    errors: dict[str, str] = field(default_factory=dict)
    pool: Any = None
    ready: bool = False

    def graph_for(self, kind: str):
        return self.bid_graph if kind == "bid" else self.conversation_graph


runtime = GraphRuntime()
_lock = threading.Lock()


def _sqlite_path(url: str) -> str:
    if url.startswith("sqlite:///"):
        p = url[len("sqlite:///"):]
        base = Path(p)
        return str(base.with_name(base.stem + "_checkpoints.sqlite"))
    return str(ROOT / "data/processed/checkpoints.sqlite")


def open_runtime(stack: Any = None) -> GraphRuntime:
    """Create the checkpointer + store and compile graphs. Synchronous and loop-independent on purpose:
    sync savers over a thread-safe psycopg ConnectionPool (or one sqlite3 connection) hold no asyncio
    tasks, so serverless invocations never wait on a background loop. Graphs run in worker threads."""
    with _lock:
        if runtime.ready:
            return runtime
        s = get_settings()
        url = s.checkpoint_url or s.database_url
        try:
            if url.startswith(("postgres://", "postgresql")):
                from langgraph.checkpoint.postgres import PostgresSaver
                from langgraph.store.postgres import PostgresStore
                from psycopg.rows import dict_row
                from psycopg_pool import ConnectionPool
                pg = url.replace("postgresql+psycopg://", "postgresql://").replace("postgres://", "postgresql://", 1)
                runtime.pool = ConnectionPool(
                    pg, min_size=0, max_size=int(os.getenv("CHECKPOINT_POOL_SIZE", "6")), max_idle=60,
                    check=ConnectionPool.check_connection, open=True,
                    kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row})
                runtime.checkpointer = PostgresSaver(runtime.pool)
                runtime.store = PostgresStore(runtime.pool)
            else:
                import sqlite3

                from langgraph.checkpoint.sqlite import SqliteSaver
                from langgraph.store.sqlite import SqliteStore
                path = _sqlite_path(url)
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=30)
                runtime.checkpointer = SqliteSaver(conn)
                runtime.store = SqliteStore(conn)
            runtime.checkpointer.setup()
            runtime.store.setup()
        except Exception as exc:  # noqa: BLE001
            log.exception("checkpointer/store setup failed")
            runtime.errors["checkpointer"] = f"{type(exc).__name__}: {exc}"[:300]
            from langgraph.checkpoint.memory import InMemorySaver
            from langgraph.store.memory import InMemoryStore
            runtime.checkpointer, runtime.store = InMemorySaver(), InMemoryStore()
        build_graphs()
        runtime.ready = True
        return runtime


def close_runtime() -> None:
    with _lock:
        if runtime.pool is not None:
            try:
                runtime.pool.close()
            except Exception:  # noqa: BLE001
                pass
        runtime.pool = None
        runtime.checkpointer = runtime.store = None
        runtime.bid_graph = runtime.conversation_graph = None
        runtime.ready = False


async def get_snapshot(graph, config: dict):
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(graph.get_state, config)


def build_graphs() -> None:
    build_bid = optional("agent.graphs.bid_graph", "build_bid_graph")
    if build_bid is not None and runtime.bid_graph is None:
        try:
            runtime.bid_graph = build_bid(checkpointer=runtime.checkpointer, store=runtime.store)
        except Exception as exc:  # noqa: BLE001
            log.exception("build_bid_graph failed")
            runtime.errors["bid_graph"] = f"{type(exc).__name__}: {exc}"
    elif build_bid is None:
        runtime.errors.setdefault("bid_graph", "agent.graphs.bid_graph not importable")
    build_conv = optional("agent.graphs.conversation_graph", "build_conversation_graph")
    if build_conv is not None and runtime.conversation_graph is None:
        try:
            runtime.conversation_graph = build_conv(checkpointer=runtime.checkpointer, store=runtime.store)
        except Exception as exc:  # noqa: BLE001
            log.exception("build_conversation_graph failed")
            runtime.errors["conversation_graph"] = f"{type(exc).__name__}: {exc}"
    elif build_conv is None:
        runtime.errors.setdefault("conversation_graph", "agent.graphs.conversation_graph not importable")


def thread_config(thread_id: str, user_id: str, trace_id: str, persona: str | None, **extra) -> dict:
    cfg = {
        "configurable": {"thread_id": thread_id, "user_id": user_id, "trace_id": trace_id,
                         "persona": persona or "aiml", **extra},
        "metadata": {"trace_id": trace_id, "user_id": user_id, "thread_id": thread_id},
        "tags": [f"trace:{trace_id}"],
        "run_name": f"gigbid:{thread_id}",
    }
    from .config import cfg as _cfg
    steps = _cfg("budgets.max_steps")
    if isinstance(steps, (int, float)):
        cfg["recursion_limit"] = int(steps) + 20
    try:
        from agent.tracing import callbacks_for  # type: ignore
        cbs = callbacks_for(trace_id=trace_id, thread_id=thread_id)
        if cbs:
            cfg["callbacks"] = cbs
    except Exception:
        pass
    return cfg
