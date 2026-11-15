"""LangGraph runtime: checkpointer + store lifecycle and compiled graphs.

Postgres (AsyncPostgresSaver / AsyncPostgresStore) when DATABASE_URL is postgres, else SQLite
(AsyncSqliteSaver / AsyncSqliteStore). Graphs come from agent/; when agent/ is missing or broken the
runtime reports the feature unavailable and the rest of the API still works."""
from __future__ import annotations

import logging
from contextlib import AsyncExitStack
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

    def graph_for(self, kind: str):
        return self.bid_graph if kind == "bid" else self.conversation_graph


runtime = GraphRuntime()


def _sqlite_path(url: str) -> str:
    if url.startswith("sqlite:///"):
        p = url[len("sqlite:///"):]
        base = Path(p)
        return str(base.with_name(base.stem + "_checkpoints.sqlite"))
    return str(ROOT / "data/processed/checkpoints.sqlite")


async def open_runtime(stack: AsyncExitStack) -> GraphRuntime:
    s = get_settings()
    url = s.checkpoint_url or s.database_url
    try:
        if url.startswith(("postgres://", "postgresql")):
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from langgraph.store.postgres.aio import AsyncPostgresStore
            pg = url.replace("postgresql+psycopg://", "postgresql://")
            runtime.checkpointer = await stack.enter_async_context(AsyncPostgresSaver.from_conn_string(pg))
            runtime.store = await stack.enter_async_context(AsyncPostgresStore.from_conn_string(pg))
        else:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
            from langgraph.store.sqlite.aio import AsyncSqliteStore
            path = _sqlite_path(url)
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            runtime.checkpointer = await stack.enter_async_context(AsyncSqliteSaver.from_conn_string(path))
            runtime.store = await stack.enter_async_context(AsyncSqliteStore.from_conn_string(path))
        await runtime.checkpointer.setup()
        await runtime.store.setup()
    except Exception as exc:  # noqa: BLE001
        log.exception("checkpointer/store setup failed")
        runtime.errors["checkpointer"] = f"{type(exc).__name__}: {exc}"
        from langgraph.checkpoint.memory import InMemorySaver
        from langgraph.store.memory import InMemoryStore
        runtime.checkpointer, runtime.store = InMemorySaver(), InMemoryStore()
    build_graphs()
    return runtime


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
