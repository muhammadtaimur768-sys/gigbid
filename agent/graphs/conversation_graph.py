"""Conversation graph (one thread per client conversation).

read_messages → classify_intent ─(scam_signal)→ END (flagged)
                               └→ draft_reply (+ workspace free_slots for interviews) → compliance
                                    ─(block)→ needs_attention
                                    └→ approval (interrupt) ─(reject)→ END
                                                            └→ send → END
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agent.nodes.approval import dead_letter, needs_attention
from agent.nodes.base import Deps, instrument, retry_policy
from agent.nodes.liaison import classify_intent, conv_approval, conv_compliance, draft_reply, read_messages, send
from agent.state import ConvState

ERR = ("needs_attention", "dead_letter")


def _err(s):
    return s.get("status") if s.get("status") in ERR else None


def build_conversation_graph(checkpointer=None, store=None, marketplace=None, workspace=None, *, deps: Deps | None = None):
    deps = deps or Deps(marketplace=marketplace, workspace=workspace)
    rp = retry_policy()
    g = StateGraph(ConvState)
    for name, fn, term in (("read_messages", read_messages, False), ("classify_intent", classify_intent, False),
                           ("draft_reply", draft_reply, False), ("compliance", conv_compliance, False),
                           ("approval", conv_approval, False), ("send", send, False),
                           ("needs_attention", needs_attention, True), ("dead_letter", dead_letter, True)):
        g.add_node(name, instrument(name, fn, deps, budget_kind="conversation", terminal=term), retry_policy=rp)
    m = {e: e for e in ERR}
    g.add_edge(START, "read_messages")
    g.add_conditional_edges("read_messages", lambda s: _err(s) or "classify_intent", {"classify_intent": "classify_intent", **m})
    g.add_conditional_edges("classify_intent", lambda s: _err(s) or (END if s.get("status") == "flagged_scam" else "draft_reply"),
                            {"draft_reply": "draft_reply", END: END, **m})
    g.add_conditional_edges("draft_reply", lambda s: _err(s) or "compliance", {"compliance": "compliance", **m})
    g.add_conditional_edges("compliance", lambda s: _err(s) or "approval", {"approval": "approval", **m})
    g.add_conditional_edges("approval", lambda s: _err(s) or (END if s.get("status") == "rejected" else "send"),
                            {"send": "send", END: END, **m})
    g.add_conditional_edges("send", lambda s: _err(s) or END, {END: END, **m})
    g.add_edge("needs_attention", END)
    g.add_edge("dead_letter", END)
    return g.compile(checkpointer=checkpointer, store=store)


def new_conversation_input(conversation_id: str, *, persona: str = "aiml", user_id: str = "", job: dict | None = None,
                           messages: list[dict] | None = None, options: dict | None = None, trace_id: str | None = None) -> dict:
    from agent.tracing import new_trace_id

    inp = {"conversation_id": conversation_id, "persona": persona, "user_id": user_id, "options": options or {},
           "trace_id": trace_id or new_trace_id(), "thread_id": f"conv:{user_id}:{conversation_id}", "status": "running",
           "job": job or {}}
    if messages:
        inp["messages"] = messages
    return inp
