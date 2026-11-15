"""Client Liaison nodes for the conversation graph: read → classify intent → draft reply → compliance → approval → send."""
from __future__ import annotations

import datetime as dt
import hashlib
import re

from langgraph.types import interrupt

from agent.handoffs import ApprovalDecision, MessageIntent, ReplyDraft
from agent.llm import call_llm, is_heuristic
from agent.marketplace_port import MarketplaceError
from agent.nodes.base import Deps, usage_from
from agent.nodes.compliance import check_text
from agent.policy import detect_injection, wrap_untrusted
from agent.retrieval import load_profile


INTENT_CUES = [
    ("scam_signal", r"telegram|whatsapp|wechat|outside (of )?(the )?platform|crypto|bitcoin|gift ?card|bank details|send .*(id|passport)|free (sample|test)|unpaid"),
    ("interview_request", r"\b(call|interview|meet|zoom|chat live|schedule|availability|available (on|for)|time slot|google meet)\b"),
    ("negotiation", r"\b(rate|budget|price|discount|lower|cheaper|cost|fixed price|hourly|quote|\$\d+)\b"),
    ("question", r"\?|\b(how|what|which|could you|can you|do you)\b"),
]


def _client_text(messages: list[dict], n: int = 6) -> str:
    return "\n".join(f"{m.get('sender', '?')}: {m.get('body', '')}" for m in messages[-n:])


def read_messages(state: dict, deps: Deps) -> dict:
    if state.get("messages"):
        return {"status": "running"}
    msgs = deps.port(state).list_messages(state["conversation_id"])
    return {"messages": msgs, "status": "running"}


def classify_intent(state: dict, deps: Deps) -> dict:
    msgs = state.get("messages") or []
    last_client = next((m for m in reversed(msgs) if m.get("sender") == "client"), {"body": ""})
    text = last_client.get("body", "")
    inj = bool(detect_injection(text))
    intent, conf = "other", 0.4
    for name, rx in INTENT_CUES:
        if re.search(rx, text, re.I):
            intent, conf = name, 0.75
            break
    res = None
    if not is_heuristic("intent") and intent != "scam_signal":
        res = call_llm("intent", "intent", {"messages": wrap_untrusted(_client_text(msgs), "message")}, json_mode=True)
        if res.ok and isinstance(res.data, dict) and res.data.get("intent") in (
                "question", "negotiation", "interview_request", "scam_signal", "other"):
            intent = res.data["intent"]
            try:
                conf = max(0.0, min(1.0, float(res.data.get("confidence", 0.7))))
            except (TypeError, ValueError):
                conf = 0.7
    mi = MessageIntent(thread_id=state["conversation_id"], intent=intent, confidence=conf, injection_detected=inj)
    out = {"intent": mi.model_dump(), "usage": usage_from(res)}
    if intent == "scam_signal":
        out["status"] = "flagged_scam"
        out["status_reason"] = "client message shows scam signals (off-platform contact/payment or free work)"
    return out


def _free_slots(state: dict, deps: Deps) -> list[dict]:
    """Interview slots from the Workspace MCP server; local fallback if it is unavailable."""
    try:
        if deps.workspace is not None:
            r = deps.workspace.free_slots(days=5, duration_min=30)
        else:
            from agent.mcp_client import call_tool

            r = call_tool("liaison", "workspace", "free_slots", {"days": 5, "duration_min": 30},
                          trace_id=state.get("trace_id"), thread_id=state.get("thread_id", ""))
        slots = r.get("slots", r) if isinstance(r, dict) else r
        return list(slots)[:3]
    except Exception:
        base = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
        out = []
        for d in range(1, 4):
            s = (base + dt.timedelta(days=d)).replace(hour=10)
            out.append({"start": s.isoformat(), "end": (s + dt.timedelta(minutes=30)).isoformat(), "source": "fallback"})
        return out


def draft_reply(state: dict, deps: Deps) -> dict:
    intent = (state.get("intent") or {}).get("intent", "other")
    prof = load_profile(state.get("persona") or "aiml")
    msgs = state.get("messages") or []
    job = state.get("job") or {}
    slots = _free_slots(state, deps) if intent == "interview_request" else []
    first = (prof.get("name") or "").split(" ")[0]
    if intent == "interview_request":
        opts = "; ".join(s["start"][:16].replace("T", " ") + " UTC" for s in slots)
        body = f"Thanks, happy to talk. I can do any of these 30-minute slots: {opts}. Which works best for you?"
    elif intent == "negotiation":
        body = ("Thanks for the details. My quote reflects the scope we discussed; if the budget is fixed, I can suggest a "
                "smaller first milestone so you can see results before committing to the rest. Would that work?")
    elif intent == "question":
        body = ("Good question. Based on what you described, I would start with a short scoping step to confirm the data and "
                "success criteria, then deliver a first working version early. Happy to go into detail here in the chat.")
    else:
        body = "Thanks for the message. Could you tell me a bit more about what you would like to do next?"
    body += f"\n\n{first}" if first else ""
    res = None
    if not is_heuristic("liaison"):
        rules = []
        try:
            from langgraph.config import get_store

            st = get_store()
            rules = [i.key for i in st.search(("style", state.get("user_id") or ""), limit=20)] if st else []
        except Exception:
            pass
        res = call_llm("liaison", "liaison", {
            "intent": intent, "name": prof.get("name", ""), "job_title": job.get("title", ""), "bid": job.get("bid_amount", ""),
            "slots": "; ".join(s["start"] for s in slots) or "none",
            "messages": wrap_untrusted(_client_text(msgs), "message"), "style_rules": ", ".join(rules) or "none"})
        if res.ok and len(res.text.strip()) > 20:
            body = res.text.strip()[:1500]
    rd = ReplyDraft(thread_id=state["conversation_id"], body=body, proposed_slots=slots)
    return {"reply": rd.model_dump(), "slots": slots, "usage": usage_from(res)}


def conv_compliance(state: dict, deps: Deps) -> dict:
    v, _ = check_text(state["conversation_id"], state["reply"]["body"], "message")
    reply = dict(state["reply"])
    reply["body"] = v["cleaned_text"]
    out = {"compliance": v, "reply": reply}
    if not v["allowed"]:
        out["status"] = "needs_attention"
        out["status_reason"] = f"compliance blocked: {v['reason']}"[:400]
    return out


def conv_approval(state: dict, deps: Deps) -> dict:
    raw = interrupt({"type": "message_approval", "thread_id": state.get("thread_id"),
                     "conversation_id": state["conversation_id"], "intent": state.get("intent"),
                     "reply": state.get("reply"), "slots": state.get("slots") or [],
                     "compliance": state.get("compliance"), "messages": (state.get("messages") or [])[-6:],
                     "actions": ["approve", "edit", "reject"]})
    if isinstance(raw, str):
        raw = {"action": raw}
    d = ApprovalDecision(**raw)
    out: dict = {"approval": d.model_dump(), "approvals": [d.model_dump()]}
    if d.action == "reject":
        out.update(status="rejected", status_reason=f"rejected by user: {d.reason or 'no reason given'}")
    elif d.action == "edit" and d.edited_text:
        v, _ = check_text(state["conversation_id"], d.edited_text, "message")
        out["reply"] = {**state["reply"], "body": v["cleaned_text"], "edited": True}
        out["compliance"] = v
        if not v["allowed"]:
            out.update(status="needs_attention", status_reason=f"edited reply blocked: {v['reason']}"[:400])
    return out


def send(state: dict, deps: Deps) -> dict:
    if (state.get("sent") or {}).get("status") == "sent":
        return {}
    body = state["reply"]["body"]
    key = "msg-" + hashlib.sha256(f"{state.get('thread_id')}:{body}".encode()).hexdigest()[:32]
    try:
        r = deps.port(state).send_message(state["conversation_id"], body, key)
    except MarketplaceError as exc:
        return {"status": "needs_attention", "status_reason": f"marketplace refused the message: {exc}"[:400]}
    return {"sent": {**r, "idempotency_key": key}, "status": "sent"}


