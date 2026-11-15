"""Node runtime: budgets, tracing, retries → dead letter, and shared dependencies."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphBubbleUp
from langgraph.types import RetryPolicy

from agent.marketplace_port import MarketplacePort, MarketplaceUnavailable
from agent.settings import cfg
from agent.state import usage_total
from agent.tracing import emit, mask_pii

TRANSIENT_ERRORS: tuple[type[BaseException], ...] = (MarketplaceUnavailable, TimeoutError, ConnectionError)
ERROR_STATUSES = {"dead_letter", "needs_attention"}


@dataclass
class Deps:
    """Runtime dependencies injected by the graph builder (never stored in checkpoints)."""
    marketplace: MarketplacePort | None = None
    retriever_factory: Callable[[str], Any] | None = None
    workspace: Any = None
    extra: dict = field(default_factory=dict)

    def port(self, state: dict) -> MarketplacePort:
        if self.marketplace is not None:
            return self.marketplace
        from agent.marketplace_port import get_marketplace

        return get_marketplace(trace_id=state.get("trace_id"), thread_id=state.get("thread_id", ""))

    def retriever(self, persona: str):
        if self.retriever_factory is not None:
            return self.retriever_factory(persona)
        from agent.retrieval import get_evidence_retriever

        return get_evidence_retriever(persona)


def retry_policy() -> RetryPolicy:
    r = cfg("retry", default={}) or {}
    return RetryPolicy(max_attempts=int(r.get("max_attempts", 3)), initial_interval=float(r.get("initial_interval", 0.2)),
                       backoff_factor=float(r.get("backoff_factor", 2.0)), max_interval=float(r.get("max_interval", 5.0)),
                       jitter=False, retry_on=lambda e: isinstance(e, TRANSIENT_ERRORS))


_fail_counts: dict[tuple, int] = {}
_fail_lock = threading.Lock()


def _thread_id(config: dict | None) -> str:
    return ((config or {}).get("configurable") or {}).get("thread_id", "")


def instrument(name: str, fn: Callable[[dict, Deps], dict], deps: Deps, *, budget_kind: str = "bid",
               passthrough_on_error: bool = True, terminal: bool = False):
    """Wrap a node: skip on error status, enforce step/token budgets, trace, and convert failures.

    Transient errors are re-raised so the node's RetryPolicy retries them; on the last attempt (and for any
    other exception) the thread moves to the dead-letter state instead of crashing the run.
    """
    max_attempts = int(cfg("retry", "max_attempts", default=3))
    if budget_kind == "bid":
        max_steps, max_tokens = cfg("budgets", "max_steps", default=40), cfg("budgets", "max_tokens", default=60000)
    else:
        max_steps = cfg("budgets", "conversation_max_steps", default=20)
        max_tokens = cfg("budgets", "conversation_max_tokens", default=20000)

    def wrapped(state: dict, config: RunnableConfig) -> dict:
        tid = _thread_id(config) or state.get("thread_id", "")
        trace_id = state.get("trace_id", "")
        if tid and not state.get("thread_id"):
            state = {**state, "thread_id": tid}
        if not terminal and passthrough_on_error and state.get("status") in ERROR_STATUSES:
            return {"node_log": [f"{name}:skipped"]}
        steps = int(state.get("steps") or 0)
        opts = state.get("options") or {}
        lim_steps = int(opts.get("max_steps", max_steps))
        lim_tokens = int(opts.get("max_tokens", max_tokens))
        if not terminal and (steps >= lim_steps or usage_total(state) >= lim_tokens):
            reason = (f"step budget exceeded ({steps}/{lim_steps})" if steps >= lim_steps
                      else f"token budget exceeded ({usage_total(state)}/{lim_tokens})")
            emit(trace_id, tid, name, "budget_exceeded", {"reason": reason})
            return {"status": "needs_attention", "status_reason": reason, "steps": 1, "node_log": [name]}
        t0 = time.perf_counter()
        emit(trace_id, tid, name, "node_start", {"steps": steps})
        try:
            out = fn(state, deps) or {}
        except GraphBubbleUp:  # interrupt() and other control flow must propagate
            raise
        except TRANSIENT_ERRORS as exc:
            key = (tid, name, steps)
            with _fail_lock:
                _fail_counts[key] = _fail_counts.get(key, 0) + 1
                n = _fail_counts[key]
            emit(trace_id, tid, name, "node_retry", {"attempt": n, "error": str(exc)[:300]})
            if n < max_attempts:
                raise
            with _fail_lock:
                _fail_counts.pop(key, None)
            out = {"status": "dead_letter", "status_reason": f"{name}: {type(exc).__name__}: {exc}"[:400],
                   "errors": [f"{name}: {exc}"[:400]]}
        except Exception as exc:  # non-retriable failure → dead letter with a reason
            out = {"status": "dead_letter", "status_reason": f"{name}: {type(exc).__name__}: {exc}"[:400],
                   "errors": [f"{name}: {type(exc).__name__}: {exc}"[:400]]}
        latency = (time.perf_counter() - t0) * 1000
        usage = out.get("usage") or {}
        emit(trace_id, tid, name, "node_end",
             {k: mask_pii(v) for k, v in out.items() if k not in ("usage", "node_log", "steps", "job")},
             tokens_in=int(usage.get("tokens_in", 0)), tokens_out=int(usage.get("tokens_out", 0)),
             cost_usd=float(usage.get("cost_usd", 0.0)), latency_ms=latency)
        out["steps"] = out.get("steps", 0) + 1
        out["node_log"] = out.get("node_log", []) + [name]
        return out

    wrapped.__name__ = name
    return wrapped


def usage_from(*results) -> dict:
    """Aggregate LLMResult usage for the state's `usage` reducer."""
    tin = sum(r.tokens_in for r in results if r is not None)
    tout = sum(r.tokens_out for r in results if r is not None)
    cost = sum(r.cost_usd for r in results if r is not None)
    calls = sum(1 for r in results if r is not None and r.error != "heuristic")
    return {"tokens": tin + tout, "tokens_in": tin, "tokens_out": tout, "cost_usd": cost, "llm_calls": calls}
