"""R&D question C: (a) one ReAct agent with all tools vs (b) langgraph-supervisor vs (c) the hand-built graph.

All three use the same hosted open model (Groq gpt-oss-20b by default) and the same tools/data.
    python -m evals.runners.arch_comparison --n 12
"""
from __future__ import annotations

import argparse
import json
import statistics
import time

from evals.runners.agent_harness import (fixed_subset, load_dev, make_port, pct, run_graph_on, score_outcomes,
                                         setup_env, write_json)


def _tools(port, persona):
    from langchain_core.tools import tool

    from agent.retrieval import get_evidence_retriever

    retr = get_evidence_retriever(persona)

    @tool
    def get_client_history(client_id: str) -> str:
        """Client history (rating, payment verified, hires, spend) for a client id."""
        return json.dumps(port.get_client_history(client_id))[:1500]

    @tool
    def get_market_stats(category: str) -> str:
        """Hourly and fixed price quantiles (p25/p50/p75) for a job category."""
        return json.dumps(port.get_market_stats(category))

    @tool
    def search_evidence(requirement: str) -> str:
        """Search the freelancer's portfolio for evidence of a requirement. Returns item ids and text."""
        evs = retr.search(requirement, k=3, filters={"type": ["case_study", "repo", "code", "review", "cv"]})
        return "\n".join(f"[{e.item_id}] {e.text[:350]}" for e in evs)

    return [get_client_history, get_market_stats, search_evidence]


def _answer_tool(sink: dict):
    from langchain_core.tools import tool

    @tool
    def submit_answer(action: str, is_scam: bool, price: float | None = None, cover_letter: str = "") -> str:
        """Submit the final decision: action is 'bid' or 'skip'; include price and cover_letter when bidding."""
        sink.update({"action": action, "is_scam": is_scam, "price": price, "cover_letter": cover_letter})
        return "recorded"

    return submit_answer


def _usage(messages) -> int:
    tot = 0
    for m in messages:
        um = getattr(m, "usage_metadata", None) or {}
        tot += int(um.get("total_tokens") or (um.get("input_tokens", 0) + um.get("output_tokens", 0)) or 0)
    return tot


def _final_json(messages) -> dict:
    from agent.llm import extract_json

    for m in reversed(messages):
        if getattr(m, "type", "") == "ai" and m.content:
            d = extract_json(m.content if isinstance(m.content, str) else str(m.content))
            if isinstance(d, dict) and "action" in d:
                return d
    return {}


def run_baseline(kind: str, rows: list[dict]) -> list[dict]:
    from langgraph.prebuilt import create_react_agent

    from agent.llm import _build, node_config
    from agent.policy import check_outbound
    from agent.prompts import render_prompt
    from agent.retrieval import load_profile

    port = make_port(rows)
    # same hosted open model as the graph's writer; the client backs off on HTTP 429 (free-tier TPM limits)
    model = _build({**node_config("writer"), "max_retries": 8})
    recs = []
    for r in rows:
        job, persona = r["job"], r["persona"]
        prof = load_profile(persona)
        vars_ = {"persona": persona, "skills": ", ".join(prof["skills"][:15]), "floor": prof["hourly_floor"],
                 "job": json.dumps({k: job[k] for k in ("id", "title", "description", "category", "skills_required", "budget_type",
                                                       "budget_min", "budget_max", "client_id", "screening_questions")})}
        tools = _tools(port, persona)
        sink: dict = {}
        answer = _answer_tool(sink)
        t0 = time.perf_counter()
        err = None
        try:
            if kind == "react":
                prompt, _ = render_prompt("react_baseline", vars_)
                agent = create_react_agent(model, tools + [answer])
                out = agent.invoke({"messages": [("user", prompt)]}, {"recursion_limit": 16})
            else:
                from langgraph_supervisor import create_supervisor

                rp, _ = render_prompt("supervisor_researcher", vars_)
                wp, _ = render_prompt("supervisor_writer", {})
                sp, _ = render_prompt("supervisor_baseline", {})
                researcher = create_react_agent(model, tools, name="researcher", prompt=rp)
                writer_a = create_react_agent(model, [], name="proposal_writer", prompt=wp)
                sup = create_supervisor([researcher, writer_a], model=model, prompt=sp, tools=[answer]).compile()
                out = sup.invoke({"messages": [("user", "Job:\n" + vars_["job"])]}, {"recursion_limit": 24})
            msgs = out["messages"]
            d = dict(sink) or _final_json(msgs)
            tokens = _usage(msgs)
        except Exception as exc:
            d, tokens, err = dict(sink), 0, f"{type(exc).__name__}: {exc}"[:300]
            if d:  # the agent answered before failing
                err = None
        lat = time.perf_counter() - t0
        letter = str(d.get("cover_letter") or "")
        unsupported = None
        violations = []
        if letter:
            try:
                from rag.retriever import get_retriever
                from rag.verify import verify_proposal

                unsupported = verify_proposal(letter, get_retriever(persona), persona)["unsupported_before"]
            except Exception:
                unsupported = None
            violations = check_outbound(letter)["violations"] + check_outbound(letter)["redactions"]
        recs.append({"job_id": job["id"], "persona": persona, "gold": r["gold"],
                     "action": d.get("action", "error" if err else "skip"), "is_scam_pred": bool(d.get("is_scam")),
                     "price": d.get("price"), "cover_letter": letter or None, "screening_answers": [],
                     "unsupported_before": unsupported, "violations_uncaught": violations, "tokens": tokens,
                     "latency_s": round(lat, 2), "error": err})
    return recs


def summarize_arch(recs: list[dict], graph: bool = False) -> dict:
    ok = [r for r in recs if not r.get("error")]
    acc = sum(1 for r in ok if (r["action"] == "bid") == (r["gold"]["action"] == "bid")) / max(1, len(ok))
    props = [r for r in ok if r.get("cover_letter")]
    unsup = [r["unsupported_before"] if not graph else r["unsupported_after"] for r in props]
    unsup = [u for u in unsup if u is not None]
    outc, _ = score_outcomes(ok)
    if graph:
        caught = sum(len(r["compliance"].get("violations", [])) + len(r["compliance"].get("redactions", [])) for r in props)
        uncaught = 0
    else:
        caught = 0
        uncaught = sum(len(r["violations_uncaught"]) for r in props)
    return {"n": len(recs), "errors": len(recs) - len(ok), "bid_skip_accuracy": round(acc, 4),
            "scam_recall": round(sum(1 for r in ok if r["is_scam_pred"] and r["gold"]["is_scam"]) / max(1, sum(1 for r in ok if r["gold"]["is_scam"])), 4)
            if any(r["gold"]["is_scam"] for r in ok) else None,
            "proposals": len(props), "unsupported_claims_per_proposal_sent": round(statistics.mean(unsup), 3) if unsup else None,
            "compliance_violations_caught": caught, "compliance_violations_in_sent_text": uncaught,
            "gigsim_reply_rate": outc["reply_rate"], "gigsim_n_scored": outc["n"],
            "tokens_per_job_mean": round(statistics.mean([r["tokens"] for r in ok]), 1) if ok else None,
            "latency_s_p50": pct([r["latency_s"] for r in ok], 0.5), "latency_s_p95": pct([r["latency_s"] for r in ok], 0.95)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--provider", default="groq_small")
    ap.add_argument("--archs", nargs="*", default=["react", "supervisor", "graph"])
    args = ap.parse_args(argv)
    setup_env(args.provider)
    rows = fixed_subset(load_dev(), args.n, seed=31)
    out = {"provider": args.provider, "n_jobs": len(rows), "job_ids": [r["job"]["id"] for r in rows], "results": {}}
    from agent.llm import node_config

    out["model"] = node_config("writer").get("model")
    for a in args.archs:
        print("running", a, flush=True)
        if a == "graph":
            recs = run_graph_on(rows, label="arch-graph")
            out["results"]["c_hand_built_graph"] = summarize_arch(recs, graph=True)
        else:
            recs = run_baseline(a, rows)
            write_json(f"arch_records_{a}.json", recs)
            out["results"]["a_react_single_agent" if a == "react" else "b_langgraph_supervisor"] = summarize_arch(recs)
        write_json("arch_comparison.json", out)
    print(json.dumps(out["results"], indent=1))


if __name__ == "__main__":
    main()
