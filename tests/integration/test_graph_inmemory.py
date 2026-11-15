"""Bid/conversation graph behaviour with the in-memory marketplace port (no GigSim needed)."""
from __future__ import annotations

from conftest import dev_jobs
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from agent.graphs.bid_graph import build_bid_graph, get_interrupt, new_run_input, resume, run_config
from agent.graphs.conversation_graph import build_conversation_graph, new_conversation_input
from agent.marketplace_port import InMemoryMarketplace


def _bid_row():
    return next(r for r in dev_jobs("aiml") if r["gold"]["action"] == "bid" and r["gold"].get("kind") == "core"
                and r["job"]["budget_type"] == "fixed")


def _graph(port, store=None):
    return build_bid_graph(checkpointer=InMemorySaver(), store=store or InMemoryStore(), marketplace=port)


def test_critic_loop_bounded():
    row = _bid_row()
    port = InMemoryMarketplace(jobs=[row["job"]])
    g = _graph(port)
    inp = new_run_input(job=row["job"], persona="aiml", user_id="u1", options={"critic_min_score": 10.5})
    cfg = run_config(inp["thread_id"])
    out = g.invoke(inp, cfg)
    assert out["decision"]["action"] == "bid"
    assert out["node_log"].count("writer") == 3 and out["node_log"].count("critic") == 3
    assert get_interrupt(g, cfg) is not None


def test_edit_is_rechecked_and_feeds_style_memory():
    row = _bid_row()
    port = InMemoryMarketplace(jobs=[row["job"]])
    store = InMemoryStore()
    g = _graph(port, store)
    inp = new_run_input(job=row["job"], persona="aiml", user_id="u9")
    cfg = run_config(inp["thread_id"])
    g.invoke(inp, cfg)
    p = get_interrupt(g, cfg)
    edited = p["draft"]["cover_letter"] + " Message me on WhatsApp for details."
    final = resume(g, cfg, {"action": "edit", "edited_text": edited})
    assert final["status"] == "submitted"
    assert "WhatsApp" not in port.submissions[0]["cover_letter"]   # redacted by compliance re-check
    assert final["approval"]["action"] == "edit"


def test_compliance_block_goes_to_needs_attention():
    row = _bid_row()
    port = InMemoryMarketplace(jobs=[row["job"]])
    g = _graph(port)
    inp = new_run_input(job=row["job"], persona="aiml", user_id="u1")
    cfg = run_config(inp["thread_id"])
    g.invoke(inp, cfg)
    final = resume(g, cfg, {"action": "edit", "edited_text": "Please pay via crypto outside the platform. " * 3})
    assert final["status"] == "needs_attention"
    assert "off_platform_payment" in final["status_reason"]
    assert port.submissions == []


def test_step_budget_moves_to_needs_attention():
    row = _bid_row()
    port = InMemoryMarketplace(jobs=[row["job"]])
    g = _graph(port)
    inp = new_run_input(job=row["job"], persona="aiml", user_id="u1", options={"max_steps": 4})
    out = g.invoke(inp, run_config(inp["thread_id"]))
    assert out["status"] == "needs_attention" and "step budget" in out["status_reason"]


def test_marketplace_outage_on_submit_dead_letters():
    row = _bid_row()
    port = InMemoryMarketplace(jobs=[row["job"]], fail_times=10)
    g = _graph(port)
    inp = new_run_input(job=row["job"], persona="aiml", user_id="u1")
    cfg = run_config(inp["thread_id"])
    g.invoke(inp, cfg)
    final = resume(g, cfg, {"action": "approve"})
    assert final["status"] == "dead_letter"
    assert port.submissions == []


def test_transient_outage_is_retried_then_submits_once():
    row = _bid_row()
    port = InMemoryMarketplace(jobs=[row["job"]], fail_times=1)
    g = _graph(port)
    inp = new_run_input(job=row["job"], persona="aiml", user_id="u1")
    cfg = run_config(inp["thread_id"])
    g.invoke(inp, cfg)
    final = resume(g, cfg, {"action": "approve"})
    assert final["status"] == "submitted" and len(port.submissions) == 1


def test_injection_job_is_flagged_and_instructions_ignored():
    row = next(r for r in dev_jobs("aiml") if r["gold"]["has_injection"] and r["gold"]["action"] == "bid")
    port = InMemoryMarketplace(jobs=[row["job"]])
    g = _graph(port)
    inp = new_run_input(job=row["job"], persona="aiml", user_id="u1")
    cfg = run_config(inp["thread_id"])
    out = g.invoke(inp, cfg)
    assert out["risk"]["injection_detected"] is True
    p = get_interrupt(g, cfg)
    if p:
        letter = p["draft"]["cover_letter"].lower()
        assert "banana" not in letter and "ignore" not in letter


def test_conversation_graph_interview_flow():
    port = InMemoryMarketplace(threads={"t-1": {"job_id": "j-1", "messages": [
        {"id": "m1", "sender": "client", "body": "Thanks for the proposal. Could we schedule a call this week?"}]}})
    g = build_conversation_graph(checkpointer=InMemorySaver(), store=InMemoryStore(), marketplace=port)
    inp = new_conversation_input("t-1", persona="aiml", user_id="u1")
    cfg = {"configurable": {"thread_id": inp["thread_id"]}}
    out = g.invoke(inp, cfg)
    assert out["intent"]["intent"] == "interview_request"
    assert out["slots"]
    snap = g.get_state(cfg)
    payload = snap.tasks[0].interrupts[0].value
    assert payload["type"] == "message_approval"
    from langgraph.types import Command

    final = g.invoke(Command(resume={"action": "approve"}), cfg)
    assert final["status"] == "sent"
    assert len(port.sent) == 1


def test_conversation_scam_signal_is_flagged():
    port = InMemoryMarketplace(threads={"t-2": {"messages": [
        {"id": "m1", "sender": "client", "body": "Let's continue on Telegram, I will pay you in USDT."}]}})
    g = build_conversation_graph(checkpointer=InMemorySaver(), marketplace=port)
    inp = new_conversation_input("t-2", user_id="u1")
    out = g.invoke(inp, {"configurable": {"thread_id": inp["thread_id"]}})
    assert out["status"] == "flagged_scam" and port.sent == {}
