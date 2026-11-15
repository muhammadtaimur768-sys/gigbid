"""Extension X2: A/B test of two proposal strategies on GigSim simulated clients.

Both strategies (agent/config.yaml writer.strategies A and B) draft proposals for the same gold-bid dev jobs
through the full bid graph; each proposal is scored by GigSim's client model
(gigsim.client_model.score_proposal). Reply rates are compared with a two-proportion z-test (plus an exact
McNemar test, since arms are paired on the same jobs).

    python -m evals.runners.ab_experiment --config heuristic --n 150
"""
from __future__ import annotations

import argparse
import math

from scipy import stats

from evals.runners.agent_harness import fixed_subset, load_dev, run_graph_on, score_outcomes, setup_env, write_json


def two_proportion_z(x1: int, n1: int, x2: int, n2: int) -> dict:
    p1, p2 = x1 / n1, x2 / n2
    p = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) if 0 < p < 1 else float("nan")
    z = (p1 - p2) / se if se and not math.isnan(se) else float("nan")
    pval = float(2 * (1 - stats.norm.cdf(abs(z)))) if not math.isnan(z) else float("nan")
    se_d = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return {"p_A": round(p1, 4), "p_B": round(p2, 4), "diff_A_minus_B": round(p1 - p2, 4), "z": round(z, 4),
            "p_value": round(pval, 6), "ci95_diff": [round(p1 - p2 - 1.96 * se_d, 4), round(p1 - p2 + 1.96 * se_d, 4)]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="heuristic")
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--metric", default="replied", choices=["replied", "interview", "hired"])
    args = ap.parse_args(argv)
    setup_env(args.config)
    rows = [r for r in load_dev() if r["gold"]["action"] == "bid"]
    rows = fixed_subset(rows, args.n, seed=11) if args.n else rows
    arms = {}
    for arm in ("A", "B"):
        recs = run_graph_on(rows, {"strategy": arm}, label=f"ab-{arm}")
        summary, orows = score_outcomes(recs)
        lens = [len(r["cover_letter"]) for r in recs if r.get("cover_letter")]
        arms[arm] = {"summary": summary, "rows": {o["job_id"]: o for o in orows},
                     "mean_chars": round(sum(lens) / len(lens), 1) if lens else None}
    common = sorted(set(arms["A"]["rows"]) & set(arms["B"]["rows"]))
    xa = sum(arms["A"]["rows"][j][args.metric] for j in common)
    xb = sum(arms["B"]["rows"][j][args.metric] for j in common)
    n = len(common)
    test = two_proportion_z(xa, n, xb, n) if n else {}
    b = sum(1 for j in common if arms["A"]["rows"][j][args.metric] and not arms["B"]["rows"][j][args.metric])
    c = sum(1 for j in common if arms["B"]["rows"][j][args.metric] and not arms["A"]["rows"][j][args.metric])
    mcnemar_p = float(stats.binomtest(b, b + c, 0.5).pvalue) if b + c else None
    mean_prob = {a: round(sum(arms[a]["rows"][j]["reply_prob"] for j in common) / n, 4) if n else None for a in ("A", "B")}
    res = {
        "experiment": "proposal strategy A vs B", "config": args.config, "metric": args.metric,
        "strategies": __import__("agent.settings", fromlist=["cfg"]).cfg("writer", "strategies"),
        "n_jobs_per_arm": n, "successes": {"A": xa, "B": xb}, "two_proportion_z_test": test,
        "mcnemar_exact": {"A_only": b, "B_only": c, "p_value": round(mcnemar_p, 6) if mcnemar_p is not None else None},
        "mean_reply_prob": mean_prob, "mean_chars": {a: arms[a]["mean_chars"] for a in ("A", "B")},
        "arm_summaries": {a: arms[a]["summary"] for a in ("A", "B")},
        "alpha": 0.05, "significant": bool(test and test["p_value"] < 0.05),
    }
    write_json("ab_experiment.json", res)
    print({k: res[k] for k in ("n_jobs_per_arm", "successes", "two_proportion_z_test", "mcnemar_exact", "mean_reply_prob", "significant")})


if __name__ == "__main__":
    main()
