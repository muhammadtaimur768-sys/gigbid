"""Execution trace: trace ids, PII masking and the `trace_events` table writer.

The trace is kept apart from graph state and long-term memory: every node event and tool call is written
here (PII-masked) for audit and debugging. LangSmith tracing switches on automatically when
LANGSMITH_API_KEY is set.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
import uuid
from typing import Any

from sqlalchemy import Column, DateTime, Float, Integer, MetaData, String, Table, Text, create_engine, select

if os.environ.get("LANGSMITH_API_KEY") and not os.environ.get("LANGSMITH_TRACING"):
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ.setdefault("LANGSMITH_PROJECT", "gigbid")

metadata = MetaData()
trace_events = Table(
    "trace_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trace_id", String(64), index=True),
    Column("thread_id", String(128), index=True),
    Column("node", String(64)),
    Column("event", String(64)),
    Column("payload_json", Text),
    Column("tokens_in", Integer, default=0),
    Column("tokens_out", Integer, default=0),
    Column("cost_usd", Float, default=0.0),
    Column("latency_ms", Float, default=0.0),
    Column("ts", DateTime),
)

_PII = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,4})?\b"), "[IBAN]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[CARD]"),
    (re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)"),
     lambda m: "[PHONE]" if sum(c.isdigit() for c in m.group(0)) >= 9 else m.group(0)),
    (re.compile(r"(?i)(?:t\.me|telegram\.me|wa\.me)/\S+"), "[HANDLE]"),
    (re.compile(r"(?<![\w@])@[A-Za-z0-9_]{4,}"), "[HANDLE]"),
]


def new_trace_id() -> str:
    return uuid.uuid4().hex


def mask_pii(value: Any) -> Any:
    """Mask emails, phones, card numbers, IBANs and messaging handles in strings / nested data."""
    if isinstance(value, str):
        out = value
        for rx, repl in _PII:
            out = rx.sub(repl, out)
        return out
    if isinstance(value, dict):
        return {k: mask_pii(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [mask_pii(v) for v in value]
    return value


class TraceWriter:
    def __init__(self, url: str | None = None):
        self.url = url or os.environ.get("TRACE_DATABASE_URL") or os.environ.get(
            "DATABASE_URL", "sqlite:///data/processed/gigbid.db")
        if self.url.startswith("sqlite:///") and not self.url.startswith("sqlite:////"):
            path = self.url[len("sqlite:///"):]
            if path and path != ":memory:":
                os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        if self.url.startswith("postgres://"):
            self.url = "postgresql+psycopg://" + self.url[len("postgres://"):]
        elif self.url.startswith("postgresql://"):
            self.url = "postgresql+psycopg://" + self.url[len("postgresql://"):]
        self.engine = create_engine(self.url, future=True)
        metadata.create_all(self.engine, checkfirst=True)
        self._lock = threading.Lock()

    def write(self, *, trace_id: str, thread_id: str, node: str, event: str, payload: Any = None,
              tokens_in: int = 0, tokens_out: int = 0, cost_usd: float = 0.0, latency_ms: float = 0.0) -> None:
        row = dict(trace_id=trace_id or "", thread_id=thread_id or "", node=node, event=event,
                   payload_json=json.dumps(mask_pii(payload), default=str)[:20000],
                   tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd, latency_ms=latency_ms,
                   ts=dt.datetime.now(dt.timezone.utc))
        with self._lock, self.engine.begin() as conn:
            conn.execute(trace_events.insert().values(**row))

    def events(self, thread_id: str | None = None, trace_id: str | None = None) -> list[dict]:
        q = select(trace_events).order_by(trace_events.c.id)
        if thread_id:
            q = q.where(trace_events.c.thread_id == thread_id)
        if trace_id:
            q = q.where(trace_events.c.trace_id == trace_id)
        with self.engine.connect() as conn:
            rows = conn.execute(q).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["payload"] = json.loads(d.pop("payload_json") or "null")
            except json.JSONDecodeError:
                d["payload"] = None
            out.append(d)
        return out


_writer: TraceWriter | None = None
_writer_lock = threading.Lock()


def tracing_enabled() -> bool:
    return os.environ.get("TRACING_DISABLED", "0") not in ("1", "true", "yes")


def get_writer() -> TraceWriter | None:
    global _writer
    if not tracing_enabled():
        return None
    with _writer_lock:
        url = os.environ.get("TRACE_DATABASE_URL") or os.environ.get("DATABASE_URL", "sqlite:///data/processed/gigbid.db")
        if _writer is None or _writer.url.split("://", 1)[-1] != url.split("://", 1)[-1]:
            _writer = TraceWriter(url)
        return _writer


def emit(trace_id: str, thread_id: str, node: str, event: str, payload: Any = None, **metrics) -> None:
    """Best-effort trace write; tracing failures never break a run."""
    w = get_writer()
    if w is None:
        return
    try:
        w.write(trace_id=trace_id, thread_id=thread_id, node=node, event=event, payload=payload, **metrics)
    except Exception:
        pass


def get_trace_events(thread_id: str | None = None, trace_id: str | None = None) -> list[dict]:
    w = get_writer()
    return w.events(thread_id=thread_id, trace_id=trace_id) if w else []


def callbacks_for(trace_id: str, thread_id: str) -> list:
    """LangChain callbacks that write every LLM call (model, tokens, latency) to trace_events."""
    import time

    from langchain_core.callbacks import BaseCallbackHandler

    class _TraceHandler(BaseCallbackHandler):
        def __init__(self):
            self._t0: dict = {}

        def on_chat_model_start(self, serialized, messages, *, run_id, **kw):
            self._t0[run_id] = time.perf_counter()

        def on_llm_end(self, response, *, run_id, **kw):
            lat = (time.perf_counter() - self._t0.pop(run_id, time.perf_counter())) * 1000
            usage = (response.llm_output or {}).get("token_usage") or {}
            tin, tout = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
            try:
                gen = response.generations[0][0]
                um = getattr(gen.message, "usage_metadata", None) or {}
                tin, tout = tin or int(um.get("input_tokens") or 0), tout or int(um.get("output_tokens") or 0)
                model = (gen.message.response_metadata or {}).get("model_name") or (gen.message.response_metadata or {}).get("model")
            except Exception:
                model = None
            emit(trace_id, thread_id, (kw.get("tags") or ["llm"])[0] if kw.get("tags") else "llm", "llm_call",
                 {"model": model}, tokens_in=tin, tokens_out=tout, latency_ms=lat)

    return [_TraceHandler()] if tracing_enabled() else []
