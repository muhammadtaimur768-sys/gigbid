"""Fill the README results blocks from evals/results/*.json so every number traces to a file.

    python scripts/fill_readme.py          # rewrite README.md in place
    python scripts/fill_readme.py --check  # exit 1 if README is stale (used in CI)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "evals" / "results"
README = ROOT / "README.md"

LIVE_URL = "https://gigbid-gamma.vercel.app"


def j(name: str) -> dict:
    return json.loads((RES / name).read_text())


def f(v, nd=3):
    if v is None or isinstance(v, str):
        return "not measured"
    return f"{v:.{nd}f}"


def stamp(src: str) -> str:
    return f"<!-- written by scripts/fill_readme.py from evals/results/{src} -->"


def rag_block() -> str:
    res = j("rag_results.json")
    best = res["best"]
    rows = {o["variant"]: o for o in res["overall"]}
    dec = j("decision_eval.json")
    out = [stamp("rag_results.json, decision_eval.json"), "",
           f"Retrieval: macro-average over 3 personas, n = {res['meta']['n_jobs_per_persona']} dev jobs per persona. "
           "Proposal columns: Groq `gpt-oss-20b` profile (`groq_small`), n = 40 dev jobs.", "",
           "| Variant | Evidence Recall@5 | MRR | nDCG@10 | retrieval p95 (ms) |", "|---|---|---|---|---|"]
    for name, o in rows.items():
        mark = " **(shipped)**" if name == best else ""
        out.append(f"| `{name}`{mark} | {f(o['recall@5'])} | {f(o['mrr'])} | {f(o['ndcg@10'])} | {f(o['p95_ms'], 0)} |")
    g = dec["groq_small"]
    out += ["", "| Shipped pipeline, end to end | Unsupported claims per proposal (before → after verification) | GigSim reply rate | p95 latency per job (s) | Cost per job (USD) |",
            "|---|---|---|---|---|",
            f"| `{best}` + Groq gpt-oss-20b | {f(g['unsupported_before'], 2)} → {f(g['unsupported_after'], 2)} | {f(g['reply_rate'], 2)} | {f(g['latency_p95_s'], 1)} | {f(g['cost_usd_per_job'], 6)} |",
            "", "Full tables (per persona, per job type, ablation): [evals/results/rag_table.md](evals/results/rag_table.md). "
            "Decision on what ships: [evals/results/rag_decision.md](evals/results/rag_decision.md)."]
    return "\n".join(out)


def decisions_block() -> str:
    d = j("decision_eval.json")
    out = [stamp("decision_eval.json"), "",
           "| Profile | n jobs | Bid/skip macro-F1 | Scam P / R | Price in fair band | p50 / p95 latency (s) | Tokens per job | USD per job |",
           "|---|---|---|---|---|---|---|---|"]
    names = {"heuristic": "Rule-based fallback (no LLM)", "groq_small": "Open A: gpt-oss-20b (Groq)",
             "groq": "Open B: 20b + 120b writer/critic (Groq)", "ollama_qwen": "Local: qwen2.5 7B (Ollama, M4)",
             "ollama_mistral": "Local: mistral 7B (Ollama, M4)"}
    for k, label in names.items():
        if k not in d:
            continue
        r = d[k]
        out.append(f"| {label} | {r['n_jobs']} | {f(r['macro_f1_bid_skip'])} | {f(r['scam_precision'], 2)} / {f(r['scam_recall'], 2)} | "
                   f"{f(r['price_in_band'], 2)} | {f(r['latency_p50_s'], 1)} / {f(r['latency_p95_s'], 1)} | {f(r['tokens_per_job_mean'], 0)} | {f(r['cost_usd_per_job'], 6)} |")
    out += ["", "**Caveat:** the dev set and the rule-based thresholds come from the same generator and there is no held-out split, "
            "so the rule-based numbers are optimistic. Groq latencies include free-tier rate-limit waits."]
    return "\n".join(out)


def multiagent_block() -> str:
    a = j("arch_comparison.json")
    labels = {"a_react_single_agent": "(a) One ReAct agent, all tools", "b_langgraph_supervisor": "(b) Prebuilt supervisor",
              "c_hand_built_graph": "(c) Hand-built GigBid graph"}
    out = [stamp("arch_comparison.json"), "", f"n = {a['n_jobs']} dev jobs, model `{a['model']}` for every arm. Indicative only.", "",
           "| Architecture | Bid/skip accuracy | Unsupported claims per sent proposal | Compliance violations caught | GigSim reply rate | Tokens per job | p95 latency (s) |",
           "|---|---|---|---|---|---|---|"]
    for k, label in labels.items():
        r = a["results"][k]
        out.append(f"| {label} | {f(r['bid_skip_accuracy'], 2)} | {f(r['unsupported_claims_per_proposal_sent'], 2)} | {r['compliance_violations_caught']} | "
                   f"{f(r['gigsim_reply_rate'], 2)} (n={r['gigsim_n_scored']}) | {f(r['tokens_per_job_mean'], 0)} | {f(r['latency_s_p95'], 1)} |")
    out += ["", f"Note from the run: {a['notes']}"]
    return "\n".join(out)


def injection_block() -> str:
    d = j("decision_eval.json")
    out = [stamp("decision_eval_heuristic.json, evals/results/decision_eval_groq_small.json, evals/results/decision_eval_groq.json"), "", "| Profile | Injection detection precision | recall | n injected jobs detected |", "|---|---|---|---|"]
    for k in ("heuristic", "groq_small", "groq"):
        m = j(f"decision_eval_{k}.json")["metrics"]["injection"]
        out.append(f"| {k} | {f(m['precision'], 2)} | {f(m['recall'], 2)} | {m['tp']} |")
    out += ["", "Attack success rate *without* defences was not measured (no undefended ablation run); this is listed as a gap in the report."]
    _ = d
    return "\n".join(out)


def budgets_block() -> str:
    slo = yaml.safe_load((ROOT / "agent" / "config.yaml").read_text())["slo"]
    m = j("decision_eval_groq_small.json")["metrics"]
    pj, pp = slo["job_analysed"], slo["proposal"]
    lj, lp = m["latency_s"]["p95"], m["latency_s_proposals"]["p95"]
    cj, cp = m["cost_usd_per_job"], m.get("cost_usd_per_proposal")

    def ok(meas, lim):
        return "met" if meas is not None and meas <= lim else "**missed**"

    return "\n".join([
        stamp("decision_eval_groq_small.json; budgets from agent/config.yaml `slo`"), "",
        "| | Declared p95 (s) | Measured p95 (s) | | Declared cost (USD) | Measured cost (USD) | |", "|---|---|---|---|---|---|---|",
        f"| Per job analysed | {pj['p95_latency_s']} | {f(lj, 1)} | {ok(lj, pj['p95_latency_s'])} | {pj['cost_usd']} | {f(cj, 6)} | {ok(cj, pj['cost_usd'])} |",
        f"| Per proposal | {pp['p95_latency_s']} | {f(lp, 1)} | {ok(lp, pp['p95_latency_s'])} | {pp['cost_usd']} | {f(cp, 6)} | {ok(cp, pp['cost_usd'])} |",
        "", "Measured on the dev set with the deployed open profile (Groq free tier). The p95 misses are dominated by free-tier rate-limit waits; "
        "the hidden-test run is executed by the instructor against the live URL after submission."])


def ab_block() -> str:
    a = j("ab_experiment.json")
    z = a["two_proportion_z_test"]
    return "\n".join([stamp("ab_experiment.json"), "",
                      f"Strategy A vs B, n = {a['n_jobs_per_arm']} jobs per arm, metric: GigSim client replied.", "",
                      "| Arm | Replies | Reply rate | Mean length (chars) |", "|---|---|---|---|",
                      f"| A | {a['successes']['A']} | {f(z['p_A'], 3)} | {f(a['mean_chars']['A'], 0)} |",
                      f"| B | {a['successes']['B']} | {f(z['p_B'], 3)} | {f(a['mean_chars']['B'], 0)} |", "",
                      f"Two-proportion z = {f(z['z'], 2)}, p = {f(z['p_value'], 4)}; McNemar exact p = {f(a['mcnemar_exact']['p_value'], 4)}."])


BLOCKS = {"RESULTS:RAG": rag_block, "RESULTS:DECISIONS": decisions_block, "RESULTS:MULTIAGENT": multiagent_block,
          "RESULTS:INJECTION": injection_block, "RESULTS:BUDGETS": budgets_block, "RESULTS:AB": ab_block}


def render(text: str) -> str:
    for key, fn in BLOCKS.items():
        text = re.sub(rf"<!-- {key} -->.*?<!-- /{key} -->", lambda _m, k=key, g=fn: f"<!-- {k} -->\n{g()}\n<!-- /{k} -->",
                      text, flags=re.S)
    text = re.sub(r"<!-- LIVE_URL -->.*?<!-- /LIVE_URL -->", f"<!-- LIVE_URL -->[{LIVE_URL}]({LIVE_URL})<!-- /LIVE_URL -->", text, flags=re.S)
    return text


def main() -> int:
    old = README.read_text()
    new = render(old)
    if "--check" in sys.argv:
        if new != old:
            print("README results are stale: run python scripts/fill_readme.py")
            return 1
        return 0
    README.write_text(new)
    print("README updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
