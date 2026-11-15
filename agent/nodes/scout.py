"""Scout: brings a job into the bid thread (fetches job + client history, dedupes, tags degraded mode)."""
from __future__ import annotations

from agent.llm import call_llm, is_heuristic
from agent.marketplace_port import MarketplaceUnavailable
from agent.nodes.base import Deps, usage_from
from agent.nodes.text_utils import first_sentence, job_text, text_hash
from agent.retrieval import load_profile
from agent.settings import cfg
from agent.tracing import new_trace_id


def scout_intake(state: dict, deps: Deps) -> dict:
    port = deps.port(state)
    out: dict = {"status": "running", "degraded": []}
    job = state.get("job")
    if not job:
        job = port.get_job(state["job_id"])  # transient errors retry, then dead-letter
    out["job"] = job
    out["job_id"] = job["id"]
    out.setdefault("trace_id", state.get("trace_id") or new_trace_id())
    if not state.get("trace_id"):
        out["trace_id"] = out["trace_id"]
    persona = state.get("persona") or cfg("personas", "default", default="aiml")
    out["persona"] = persona
    client = state.get("client")
    if not client and job.get("client_id"):
        try:
            client = port.get_client_history(job["client_id"])
        except MarketplaceUnavailable:
            client = {}
            out["degraded"].append("client_history_unavailable")
        except Exception:
            client = {}
    out["client"] = client or {}
    # duplicate detection via the store (seen-job fingerprints are operational data, not long-term memory)
    try:
        from langgraph.config import get_store

        store = get_store()
    except Exception:
        store = None
    if store is not None:
        ns = ("seen_jobs", state.get("user_id") or persona)
        h = text_hash(job)
        prev = store.get(ns, h)
        if prev is not None and prev.value.get("job_id") != job["id"]:
            out["duplicate_of"] = prev.value.get("job_id")
        else:
            store.put(ns, h, {"job_id": job["id"]})
    res = None
    if cfg("scout", "llm_summary", default=False) and not is_heuristic("scout"):
        prof = load_profile(persona)
        res = call_llm("scout", "scout", {"persona": persona, "skills": ", ".join(prof.get("skills", [])[:20]),
                                          "job_text": job_text(job)[:3000]}, json_mode=True)
    summary = (res.data or {}).get("summary") if res is not None and res.ok else first_sentence(job.get("description", ""), 160)
    out["job_summary"] = summary
    out["usage"] = usage_from(res)
    return out
