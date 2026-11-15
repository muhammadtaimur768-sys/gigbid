"""Decision eval: bid/skip F1, scam P/R, price-in-band, unsupported claims, latency, tokens, cost (+ GigSim outcomes).

    python -m evals.runners.decision_eval --config heuristic            # all dev jobs
    python -m evals.runners.decision_eval --config groq_small --n 40    # fixed stratified subset
Configs: heuristic | groq_small (A: 20b everywhere) | groq (B: 20b cheap, 120b writer/critic) | ollama_qwen | ollama_mistral
"""
from __future__ import annotations

import argparse
import json
import os
import time

from evals.runners.agent_harness import (RESULTS, fixed_subset, hardware, load_dev, run_graph_on, score_outcomes,
                                         setup_env, summarize, write_json)

CONFIGS = {
    "heuristic": {"provider": "heuristic"},
    "groq_small": {"provider": "groq_small", "desc": "A: gpt-oss-20b cheap nodes + gpt-oss-20b writer/critic (Groq)"},
    "groq": {"provider": "groq", "desc": "B: gpt-oss-20b cheap nodes + gpt-oss-120b writer/critic (Groq)"},
    "ollama_qwen": {"provider": "ollama", "profile": "open", "desc": "local qwen2.5:7b-instruct-q4_K_M (Ollama)"},
    "ollama_mistral": {"provider": "ollama", "profile": "open_mistral", "desc": "local mistral:7b-instruct-v0.3-q4_K_M (Ollama)"},
}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="heuristic", choices=sorted(CONFIGS))
    ap.add_argument("--n", type=int, default=0, help="0 = all dev jobs")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args(argv)
    c = CONFIGS[args.config]
    if c.get("profile"):
        os.environ["GIGBID_PROFILE"] = c["profile"]
    setup_env(c["provider"])
    from agent.llm import USAGE_TOTALS, node_config, reset_usage

    rows = load_dev()
    if args.n:
        rows = fixed_subset(rows, args.n, args.seed)
    reset_usage()
    t0 = time.time()
    recs = run_graph_on(rows, label=args.config)
    wall = time.time() - t0
    summary = summarize(recs)
    outcomes, orows = score_outcomes(recs)
    usage = {k: dict(v) for k, v in USAGE_TOTALS.items()}
    tps = None
    tout = sum(v["tokens_out"] for v in usage.values())
    lat = sum(v["latency_ms"] for v in usage.values()) / 1000
    if tout and lat:
        tps = round(tout / lat, 2)
    res = {
        "config": args.config, "description": c.get("desc", "deterministic fallbacks, no LLM"),
        "models": {n: node_config(n).get("model") if c["provider"] != "heuristic" else None
                   for n in ("analyst", "risk", "writer", "critic")},
        "n_jobs": len(rows), "subset": bool(args.n), "seed": args.seed, "wall_s": round(wall, 1),
        "metrics": summary, "gigsim_outcomes": outcomes, "llm_usage_by_node": usage,
        "output_tokens_per_s": tps, "hardware": hardware() if c["provider"] == "ollama" else None,
    }
    write_json(f"decision_eval_{args.config}.json", res)
    with open(RESULTS / f"decision_records_{args.config}.jsonl", "w") as fh:
        for r in recs:
            fh.write(json.dumps(r, default=str) + "\n")
    # combined table of every config that has been run
    combined = {}
    for p in sorted(RESULTS.glob("decision_eval_*.json")):
        d = json.loads(p.read_text())
        m = d["metrics"]
        combined[d["config"]] = {"n_jobs": d["n_jobs"], "macro_f1_bid_skip": m["macro_f1_bid_skip"], "bid_f1": m["bid"]["f1"],
                                 "skip_f1": m["skip"]["f1"], "scam_precision": m["scam"]["precision"], "scam_recall": m["scam"]["recall"],
                                 "price_in_band": m["price_in_band"]["rate"],
                                 "unsupported_before": m["unsupported_claims_per_proposal_before"],
                                 "unsupported_after": m["unsupported_claims_per_proposal_after"],
                                 "latency_p50_s": m["latency_s"]["p50"], "latency_p95_s": m["latency_s"]["p95"],
                                 "tokens_per_job_mean": m["tokens_per_job"]["mean"], "cost_usd_per_job": m["cost_usd_per_job"],
                                 "reply_rate": d["gigsim_outcomes"]["reply_rate"], "hire_rate": d["gigsim_outcomes"]["hire_rate"],
                                 "output_tokens_per_s": d.get("output_tokens_per_s")}
    write_json("decision_eval.json", combined)
    print(json.dumps({k: res[k] for k in ("config", "n_jobs", "wall_s")}, indent=1))
    print(json.dumps(summary, indent=1)[:3000])
    print(json.dumps(outcomes))


if __name__ == "__main__":
    main()
