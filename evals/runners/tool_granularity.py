"""R&D question A: does tool granularity change agent behaviour?

Compares three tool sets on evals/datasets/tool_tasks.jsonl (tasks with known correct calls):
  fine   - many narrow tools            (evals/runners/tool_sets.yaml: fine)
  coarse - four multiplexed tools        (tool_sets.yaml: coarse)
  best   - the real MCP server tools, schemas read live, descriptions rewritten (tool_sets.yaml: best)
Each predicted call is mapped back to its canonical server tool, then scored for tool selection and
argument accuracy. Tokens per task come from the provider's usage metadata. Tool results are
simulated (fixed canned payloads) so the comparison isolates tool choice, not data.

Usage:
  .venv/bin/python -m evals.runners.tool_granularity [--limit N] [--sets fine,coarse,best]
        [--provider ollama|groq]          (groq reads the key from env GROQ_API_KEY)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from mcp_servers.common.settings import REPO_ROOT, settings

WRITE_TOOLS = {"create_proposal_draft", "submit_proposal", "send_message", "create_interview_hold",
               "create_email_draft"}


# ---------------- tool sets ----------------
def _fn(name: str, description: str, parameters: dict) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": parameters}}


async def _live_schemas() -> dict[str, dict]:
    from mcp.shared.memory import create_connected_server_and_client_session as connect

    from mcp_servers.marketplace.server import mcp as mk
    from mcp_servers.portfolio.server import mcp as pf
    from mcp_servers.workspace.server import mcp as ws

    out = {}
    for srv in (mk, pf, ws):
        async with connect(srv._mcp_server) as c:
            for t in (await c.list_tools()).tools:
                out[t.name] = t.inputSchema
    return out


def build_tool_sets(cfg_path: Path) -> dict[str, dict]:
    spec = yaml.safe_load(cfg_path.read_text())
    sets: dict[str, dict] = {}
    for name in ("fine", "coarse"):
        sets[name] = {"tools": [_fn(t["name"], t["description"], t["parameters"]) for t in spec[name]],
                      "map": {t["name"]: t for t in spec[name]}}
    live = asyncio.run(_live_schemas())
    sets["best"] = {"tools": [_fn(n, spec["best"].get(n, ""), s) for n, s in live.items()],
                    "map": {n: {"maps_to": n} for n in live}}
    return sets


def to_canonical(set_name: str, tset: dict, name: str, args: dict) -> dict:
    m = tset["map"].get(name)
    if m is None:
        return {"tool": f"<unknown:{name}>", "args": args}
    if set_name == "coarse":
        target = m["dispatch"].get(args.get("action"), f"<bad-action:{args.get('action')}>")
        params = args.get("params") or {}
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {}
        extra = {k: v for k, v in args.items() if k in ("dry_run", "idempotency_key")}
        return {"tool": target, "args": {**params, **extra}}
    return {"tool": m["maps_to"], "args": {**args, **(m.get("fixed_args") or {})}}


# ---------------- simulated results ----------------
def simulate(tool: str, args: dict, task: dict) -> dict:
    exp_client = next((c["args"].get("client_id") for c in task["expected_calls"]
                       if c["tool"] == "get_client_history"), "c-0001")
    canned = {
        "search_jobs": {"jobs": [{"id": "j-00001", "title": "RAG chatbot over PDFs", "category": "AI & Machine Learning",
                                  "client_id": "c-0001", "budget_type": "fixed", "budget_max": 1200}], "total": 1},
        "get_job": {"id": args.get("job_id", "j-00001"), "title": "Build a dashboard", "client_id": exp_client,
                    "budget_type": "fixed", "budget_min": 500, "budget_max": 1500, "connects_cost": 12,
                    "screening_questions": ["Describe a similar project."]},
        "get_client_history": {"client_id": args.get("client_id"), "hires": 4, "avg_rating": 4.7,
                               "payment_verified": True, "total_spent": 12000},
        "get_connects_balance": {"balance": 64, "weekly_spent": 12},
        "list_threads": {"threads": [{"thread_id": "t-seed-aiml-1", "unread": 1}]},
        "list_messages": {"messages": [{"id": "m1", "sender": "client", "body": "Are you available this week?"}]},
        "get_market_stats": {"category": args.get("category"), "n": 400, "hourly": {"p25": 30, "p50": 45, "p75": 70},
                             "fixed": {"p25": 300, "p50": 800, "p75": 2000}},
        "list_proposals": {"proposals": [{"proposal_id": "p1", "status": "viewed"}]},
        "search_evidence": {"items": [{"item_id": "aiml-case-01", "type": "case_study", "score": 0.8}]},
        "get_case_study": {"item_id": args.get("id"), "type": "case_study", "text": "..."},
        "list_skills": {"skills": [{"skill": "python", "count": 9}]},
        "free_slots": {"slots": [{"start": "2026-11-17T10:00:00Z", "end": "2026-11-17T10:30:00Z"}]},
    }
    if tool in canned:
        return canned[tool]
    if tool in WRITE_TOOLS:
        return {"status": "preview" if args.get("dry_run") else "ok", "connects_cost": 12}
    return {"error": f"unknown tool {tool}"}


# ---------------- scoring ----------------
def _norm(v: Any) -> Any:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    if isinstance(v, str):
        if v.strip().lower() in ("true", "false"):
            return v.strip().lower() == "true"
        try:
            return round(float(v), 2)
        except ValueError:
            pass
        return frozenset(p.strip().lower() for p in v.split(",") if p.strip())
    if isinstance(v, (list, tuple)):
        return frozenset(str(x).strip().lower() for x in v)
    return v


def score_task(expected: list[dict], predicted: list[dict]) -> dict:
    exp_tools = {c["tool"] for c in expected}
    pred_tools = {c["tool"] for c in predicted}
    keys_total = keys_ok = 0
    for e in expected:
        cands = [p for p in predicted if p["tool"] == e["tool"]]
        n = len(e["args"])
        keys_total += n
        if cands and n:
            keys_ok += max(sum(1 for k, v in e["args"].items() if k in p["args"] and _norm(p["args"][k]) == _norm(v))
                           for p in cands)
    unexpected_writes = sorted((pred_tools & WRITE_TOOLS) - exp_tools)
    wants_real_submit = any(e["tool"] == "submit_proposal" and not e["args"].get("dry_run", False) for e in expected)
    unsafe_submit = (not wants_real_submit) and any(
        p["tool"] == "submit_proposal" and _norm(p["args"].get("dry_run", False)) is not True for p in predicted)
    return {"selection_exact": exp_tools == pred_tools, "selection_recall": exp_tools <= pred_tools,
            "arg_keys_total": keys_total, "arg_keys_ok": keys_ok, "unexpected_writes": unexpected_writes,
            "unsafe_submit": unsafe_submit}


# ---------------- LLM ----------------
def make_llm(provider: str, cfg: dict):
    if provider == "groq":
        from langchain_openai import ChatOpenAI

        key = os.environ.get(cfg["api_key_env"])
        if not key:
            raise SystemExit(f"{cfg['api_key_env']} not set")
        return ChatOpenAI(model=cfg["model"], base_url=cfg["base_url"], api_key=key, temperature=cfg["temperature"],
                          max_retries=2, timeout=60), cfg["model"]
    from langchain_ollama import ChatOllama

    return ChatOllama(model=cfg["ollama_model"], temperature=cfg["temperature"],
                      num_ctx=int(cfg["ollama_num_ctx"])), cfg["ollama_model"]


def invoke_with_retry(llm, messages, cfg) -> Any:
    delay = 5.0
    for attempt in range(int(cfg["max_retries"]) + 1):
        try:
            return llm.invoke(messages)
        except Exception as e:  # 429 / transient
            msg = str(e)
            retryable = "429" in msg or "rate" in msg.lower() or "timeout" in msg.lower() or "503" in msg
            if not retryable or attempt == int(cfg["max_retries"]):
                raise
            time.sleep(delay)
            delay = min(delay * 2, 60)


def run_task(llm_tools, set_name: str, tset: dict, task: dict, system: str, cfg: dict) -> dict:
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

    messages: list = [SystemMessage(system), HumanMessage(task["task"])]
    predicted, raw_calls, tokens_in, tokens_out, error = [], [], 0, 0, None
    t0 = time.time()
    try:
        for _ in range(int(cfg["max_turns"])):
            resp = invoke_with_retry(llm_tools, messages, cfg)
            um = getattr(resp, "usage_metadata", None) or {}
            tokens_in += um.get("input_tokens", 0)
            tokens_out += um.get("output_tokens", 0)
            calls = getattr(resp, "tool_calls", []) or []
            if not calls:
                break
            messages.append(resp)
            for c in calls:
                canon = to_canonical(set_name, tset, c["name"], c.get("args") or {})
                raw_calls.append({"name": c["name"], "args": c.get("args")})
                predicted.append(canon)
                messages.append(ToolMessage(json.dumps(simulate(canon["tool"], canon["args"], task)),
                                            tool_call_id=c.get("id") or c["name"]))
            if float(cfg["sleep_s"]):
                time.sleep(float(cfg["sleep_s"]))
    except Exception as e:
        error = f"{type(e).__name__}: {str(e)[:200]}"
    s = score_task(task["expected_calls"], predicted)
    return {"id": task.get("id"), "set": set_name, "expected": task["expected_calls"], "predicted": predicted,
            "raw_calls": raw_calls, "tokens_in": tokens_in, "tokens_out": tokens_out,
            "latency_s": round(time.time() - t0, 2), "error": error, **s}


def summarize(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["error"] is None]
    n = len(ok)
    if not n:
        return {"n": 0, "errors": len(rows)}
    kt = sum(r["arg_keys_total"] for r in ok)
    kt_sel = sum(r["arg_keys_total"] for r in ok if r["selection_recall"])
    return {
        "n": n,
        "errors": len(rows) - n,
        "tool_selection_accuracy": round(sum(r["selection_exact"] for r in ok) / n, 3),
        "tool_selection_recall": round(sum(r["selection_recall"] for r in ok) / n, 3),
        "argument_accuracy": round(sum(r["arg_keys_ok"] for r in ok) / kt, 3) if kt else None,
        "argument_accuracy_when_tool_correct": round(
            sum(r["arg_keys_ok"] for r in ok if r["selection_recall"]) / kt_sel, 3) if kt_sel else None,
        "tokens_per_task": round(sum(r["tokens_in"] + r["tokens_out"] for r in ok) / n, 1),
        "input_tokens_per_task": round(sum(r["tokens_in"] for r in ok) / n, 1),
        "output_tokens_per_task": round(sum(r["tokens_out"] for r in ok) / n, 1),
        "calls_per_task": round(sum(len(r["predicted"]) for r in ok) / n, 2),
        "unexpected_write_rate": round(sum(bool(r["unexpected_writes"]) for r in ok) / n, 3),
        "unsafe_submit_count": sum(r["unsafe_submit"] for r in ok),
        "latency_s_per_task": round(sum(r["latency_s"] for r in ok) / n, 2),
    }


def main(argv: list[str] | None = None) -> None:
    cfg = settings()["eval"]["tool_granularity"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sets", default="fine,coarse,best")
    ap.add_argument("--provider", default=cfg["provider"])
    ap.add_argument("--out", default=None)
    ap.add_argument("--stride", type=int, default=1, help="use every Nth task (stratified subset)")
    ap.add_argument("--order", choices=["interleave", "set-major"], default="set-major",
                    help="set-major keeps the tool prefix identical between calls (local KV-cache reuse)")
    args = ap.parse_args(argv)

    tasks = [json.loads(x) for x in (REPO_ROOT / "evals/datasets/tool_tasks.jsonl").read_text().splitlines()
             if x.strip()][:: args.stride][: args.limit]
    system = (REPO_ROOT / cfg["prompt"]).read_text().split("-->", 1)[-1].strip()
    sets = build_tool_sets(REPO_ROOT / cfg["tool_sets"])
    chosen = [s for s in args.sets.split(",") if s]
    llm, model_name = make_llm(args.provider, cfg)
    if args.provider == "ollama":
        cfg = {**cfg, "sleep_s": 0}
    bound = {s: llm.bind_tools(sets[s]["tools"]) for s in chosen}

    out = REPO_ROOT / (args.out or cfg["output"])
    out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    def write(partial: bool) -> dict:
        result = {
            "question": "R&D A: does tool granularity change agent behaviour?",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "provider": args.provider,
            "model": model_name,
            "temperature": cfg["temperature"],
            "dataset": "evals/datasets/tool_tasks.jsonl",
            "n_tasks_planned": len(tasks),
            "task_ids": [t.get("id") for t in tasks],
            "stride": args.stride,
            "partial": partial,
            "tool_counts": {s: len(sets[s]["tools"]) for s in chosen},
            "metrics": {s: summarize([r for r in rows if r["set"] == s]) for s in chosen},
            "method": ("Up to max_turns model turns per task; tool results simulated with fixed payloads; predicted "
                       "calls mapped to canonical server tools. tool_selection_accuracy = predicted tool set equals "
                       "expected set; argument_accuracy = expected (key,value) pairs matched after normalisation, "
                       "over all expected keys; tokens = provider-reported input+output tokens summed over turns."),
            "per_task": rows,
        }
        out.write_text(json.dumps(result, indent=2, default=str))
        return result

    if args.order == "interleave":
        plan = [(i, t, s) for i, t in enumerate(tasks) for s in chosen]
    else:
        plan = [(i, t, s) for s in chosen for i, t in enumerate(tasks)]
    for i, task, s in plan:
        r = run_task(bound[s], s, sets[s], task, system, cfg)
        rows.append(r)
        print(f"[{i + 1}/{len(tasks)}] {s:6s} {task.get('id')} sel={r['selection_exact']} "
              f"args={r['arg_keys_ok']}/{r['arg_keys_total']} tok={r['tokens_in'] + r['tokens_out']} "
              f"{r['latency_s']}s{' ERR ' + r['error'] if r['error'] else ''}", flush=True)
        write(partial=True)
    print(json.dumps(write(partial=False)["metrics"], indent=2))


if __name__ == "__main__":
    main()
