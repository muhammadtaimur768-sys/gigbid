"""SSE bridge: graph.astream(stream_mode=["updates","custom","messages","tasks"]) -> EventSource events.

Event vocabulary sent to the browser:
  node_start {node}            a node began (from the "tasks" stream)
  node_end   {node, keys, summary}   a node finished (from "updates")
  token      {node, text}      coalesced LLM tokens (from "messages")
  progress   {node?, ...}      custom events written by nodes via get_stream_writer()
  interrupt  {payload}         the graph paused for human approval
  error      {message, degraded}
  done       {status}          end of this segment: interrupted | done | error | pending_retry
Events are persisted (run_events) so a page refresh or reconnect replays the whole run.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Awaitable, Callable

from pydantic import BaseModel
from sqlalchemy import select

from .db import Run, RunEvent, SessionLocal

Emit = Callable[[str, dict], Awaitable[None]]
TERMINAL_EVENTS = {"done", "error"}
STREAM_MODES = ["updates", "custom", "messages", "tasks"]


def to_jsonable(obj: Any, depth: int = 0) -> Any:
    if depth > 8:
        return str(obj)
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v, depth + 1) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if hasattr(obj, "content") and hasattr(obj, "type"):  # langchain message
        return {"type": getattr(obj, "type", ""), "content": to_jsonable(getattr(obj, "content", ""), depth + 1)}
    if hasattr(obj, "value") and hasattr(obj, "id") and type(obj).__name__ == "Interrupt":
        return {"id": obj.id, "value": to_jsonable(obj.value, depth + 1)}
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        return str(obj)


def _summary(update: Any) -> tuple[list[str], dict]:
    data = to_jsonable(update)
    if not isinstance(data, dict):
        return [], {"value": str(data)[:300]}
    keys = list(data.keys())
    small: dict = {}
    for k, v in data.items():
        text = json.dumps(v, default=str)
        small[k] = v if len(text) <= 1500 else (text[:1500] + "...")
    return keys, small


async def bridge(graph, graph_input: Any, config: dict, emit: Emit) -> None:
    """Run the graph and translate its multi-mode stream into UI events (without 'done')."""
    token_buf: dict[str, str] = {}

    async def flush(node: str | None = None):
        for n in [node] if node else list(token_buf):
            if n in token_buf and token_buf[n]:
                await emit("token", {"node": n, "text": token_buf.pop(n)})

    async for item in graph.astream(graph_input, config, stream_mode=STREAM_MODES, subgraphs=False):
        mode, chunk = item if isinstance(item, tuple) and len(item) == 2 else ("updates", item)
        if mode == "tasks":
            if isinstance(chunk, dict) and "input" in chunk and "result" not in chunk:
                await emit("node_start", {"node": chunk.get("name"), "task_id": chunk.get("id")})
            elif isinstance(chunk, dict) and chunk.get("error"):
                await emit("progress", {"node": chunk.get("name"), "error": str(chunk.get("error"))[:500]})
        elif mode == "updates":
            if not isinstance(chunk, dict):
                continue
            for node, update in chunk.items():
                if node == "__interrupt__":
                    await flush()
                    payload = to_jsonable(update)
                    await emit("interrupt", {"payload": payload})
                    continue
                await flush(node)
                keys, summary = _summary(update)
                await emit("node_end", {"node": node, "keys": keys, "summary": summary})
        elif mode == "messages":
            try:
                msg, meta = chunk
            except (TypeError, ValueError):
                continue
            node = (meta or {}).get("langgraph_node", "llm")
            text = getattr(msg, "content", "")
            if isinstance(text, list):
                text = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in text)
            if text:
                token_buf[node] = token_buf.get(node, "") + text
                if len(token_buf[node]) >= 120:
                    await flush(node)
        elif mode == "custom":
            data = to_jsonable(chunk)
            await emit("progress", data if isinstance(data, dict) else {"value": data})
    await flush()


def persist_emitter(thread_id: str, user_id: str, mirror: asyncio.Queue | None = None) -> Emit:
    async def emit(event: str, data: dict) -> None:
        db = SessionLocal()
        try:
            row = RunEvent(thread_id=thread_id, user_id=user_id, event=event, data=to_jsonable(data))
            db.add(row)
            db.commit()
            if mirror is not None:
                await mirror.put({"id": row.id, "event": event, "data": row.data})
        finally:
            db.close()
    return emit


def _fmt(row_id: int, event: str, data: dict) -> dict:
    return {"id": str(row_id), "event": event, "data": json.dumps(data, default=str)}


async def sse_events(thread_id: str, user_id: str, after: int = 0, poll_s: float = 0.25,
                     max_wait_s: float = 600.0) -> AsyncIterator[dict]:
    """Replay persisted events after `after`, then tail until a terminal event for a non-running run."""
    waited = 0.0
    last = after
    while True:
        db = SessionLocal()
        try:
            rows = list(db.scalars(select(RunEvent).where(
                RunEvent.thread_id == thread_id, RunEvent.user_id == user_id, RunEvent.id > last
            ).order_by(RunEvent.id)))
            run = db.get(Run, thread_id)
            status = run.status if run else None
        finally:
            db.close()
        terminal_seen = False
        for r in rows:
            last = r.id
            yield _fmt(r.id, r.event, r.data)
            if r.event in TERMINAL_EVENTS:
                terminal_seen = True
        if terminal_seen and status not in ("queued", "running"):
            return
        if not rows and status in ("done", "error", "interrupted", "pending_retry") and last > 0 and after >= 0:
            # nothing new and run already settled: close so EventSource doesn't spin
            if waited > 1.0:
                return
        if run is None and waited > 5.0:
            yield _fmt(0, "error", {"message": "run not found"})
            return
        await asyncio.sleep(poll_s)
        waited += poll_s
        if waited > max_wait_s:
            return
