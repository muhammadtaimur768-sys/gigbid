"""Bid graph (one thread per job).

scout_intake → Send(analyst, risk, matcher) in parallel → decide
  ├─ skip / watch → END
  └─ bid → pricing → writer → verifier → critic ─(revise, ≤ critic.max_rounds)→ writer
                                              └─(pass / rounds used)→ compliance ─(block)→ needs_attention
                                                                               └→ preview → approval (interrupt)
                                                                                    ├─ reject → END
                                                                                    └─ approve/edit → submit → END
Any node: step/token budget exceeded → needs_attention; unrecoverable error → dead_letter.
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from agent.nodes.analyst import analyst
from agent.nodes.approval import approval, dead_letter, needs_attention, preview, submit
from agent.nodes.base import Deps, instrument, retry_policy
from agent.nodes.compliance import compliance
from agent.nodes.critic import critic
from agent.nodes.decide import decide
from agent.nodes.matcher import matcher
from agent.nodes.pricing import pricing
from agent.nodes.risk import risk
from agent.nodes.scout import scout_intake
from agent.nodes.verifier import verifier
from agent.nodes.writer import writer
from agent.settings import cfg
from agent.state import BidState

ERR = ("needs_attention", "dead_letter")


def _err(state: dict) -> str | None:
    s = state.get("status")
    return s if s in ERR else None


def route_fanout(state: dict):
    if _err(state):
        return _err(state)
    return [Send("analyst", state), Send("risk", state), Send("matcher", state)]


def route_decide(state: dict) -> str:
    if _err(state):
        return _err(state)
    action = (state.get("decision") or {}).get("action")
    return "pricing" if action == "bid" else END


def _linear(nxt: str):
    def route(state: dict) -> str:
        return _err(state) or nxt
    route.__name__ = f"to_{nxt}"
    return route


def route_critic(state: dict) -> str:
    if _err(state):
        return _err(state)
    crit = (state.get("critiques") or [{}])[-1]
    max_rounds = int((state.get("options") or {}).get("critic_max_rounds", cfg("critic", "max_rounds", default=2)))
    # critic_round counts reviews; the writer may be sent back at most max_rounds times
    if crit.get("verdict") == "revise" and int(state.get("critic_round") or 0) <= max_rounds:
        return "writer"
    return "compliance"


def route_approval(state: dict) -> str:
    if _err(state):
        return _err(state)
    if state.get("status") == "rejected":
        return END
    return "submit"


def build_bid_graph(checkpointer=None, store=None, marketplace=None, retriever_factory=None, *, deps: Deps | None = None):
    """Compile the bid graph. `marketplace` is a MarketplacePort (default: get_marketplace())."""
    deps = deps or Deps(marketplace=marketplace, retriever_factory=retriever_factory)
    rp = retry_policy()
    g = StateGraph(BidState)

    def add(name, fn, **kw):
        g.add_node(name, instrument(name, fn, deps, **kw), retry_policy=rp)

    add("scout_intake", scout_intake)
    add("analyst", analyst)
    add("risk", risk)
    add("matcher", matcher)
    add("decide", decide)
    add("pricing", pricing)
    add("writer", writer)
    add("verifier", verifier)
    add("critic", critic)
    add("compliance", compliance)
    add("preview", preview)
    add("approval", approval)
    add("submit", submit)
    add("needs_attention", needs_attention, terminal=True)
    add("dead_letter", dead_letter, terminal=True)

    g.add_edge(START, "scout_intake")
    g.add_conditional_edges("scout_intake", route_fanout, ["analyst", "risk", "matcher", *ERR])
    for n in ("analyst", "risk", "matcher"):
        g.add_edge(n, "decide")
    g.add_conditional_edges("decide", route_decide, {"pricing": "pricing", END: END, **{e: e for e in ERR}})
    for a, b in (("pricing", "writer"), ("writer", "verifier"), ("verifier", "critic"), ("preview", "approval")):
        g.add_conditional_edges(a, _linear(b), {b: b, **{e: e for e in ERR}})
    g.add_conditional_edges("critic", route_critic, {"writer": "writer", "compliance": "compliance", **{e: e for e in ERR}})
    g.add_conditional_edges("compliance", _linear("preview"), {"preview": "preview", **{e: e for e in ERR}})
    g.add_conditional_edges("approval", route_approval, {"submit": "submit", END: END, **{e: e for e in ERR}})
    g.add_conditional_edges("submit", lambda s: _err(s) or END, {END: END, **{e: e for e in ERR}})
    g.add_edge("needs_attention", END)
    g.add_edge("dead_letter", END)
    return g.compile(checkpointer=checkpointer, store=store)


# ------------------------------------------------------------------ helpers for the API

def new_run_input(job: dict | None = None, job_id: str | None = None, *, persona: str = "aiml", user_id: str = "",
                  options: dict | None = None, trace_id: str | None = None, thread_id: str | None = None) -> dict:
    from agent.tracing import new_trace_id

    jid = (job or {}).get("id") or job_id
    inp: dict[str, Any] = {"job_id": jid, "persona": persona, "user_id": user_id, "options": options or {},
                           "trace_id": trace_id or new_trace_id(), "thread_id": thread_id or f"bid:{user_id}:{jid}",
                           "status": "running"}
    if job:
        inp["job"] = job
    return inp


def run_config(thread_id: str, **extra) -> dict:
    return {"configurable": {"thread_id": thread_id, **extra},
            "recursion_limit": int(cfg("budgets", "max_steps", default=40)) + 20}


def get_interrupt(graph, config: dict) -> dict | None:
    """Pending approval payload for a thread (None if the thread is not waiting)."""
    snap = graph.get_state(config)
    for t in snap.tasks or ():
        for it in getattr(t, "interrupts", ()) or ():
            return it.value
    return None


def resume(graph, config: dict, decision: dict):
    """Resume a waiting thread with an ApprovalDecision dict. No-op (returns state) if nothing is pending."""
    from langgraph.types import Command

    if get_interrupt(graph, config) is None:
        return graph.get_state(config).values
    return graph.invoke(Command(resume=decision), config)
