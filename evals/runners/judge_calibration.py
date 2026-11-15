"""LLM-judge calibration set: 30 agent proposals + judge scores, and an EMPTY human label sheet.

Cohen's kappa (judge vs human, on pass/revise and on 3 score bins) is computed only when the author has
filled in evals/datasets/human_labels.csv. Labels are never generated.

    python -m evals.runners.judge_calibration --judge groq     # judge = Critic prompt on gpt-oss-120b
    python -m evals.runners.judge_calibration --judge heuristic
"""
from __future__ import annotations

import argparse
import csv
import json

from evals.runners.agent_harness import ROOT, RESULTS, fixed_subset, load_dev, run_graph_on, setup_env, write_json

LABELS = ROOT / "evals" / "datasets" / "human_labels.csv"
PROPOSALS = RESULTS / "judge_proposals.jsonl"
FIELDS = ["proposal_id", "job_id", "human_score_0_10", "human_verdict_pass_or_revise", "labeler", "notes"]


def _bin(score: float) -> str:
    return "low" if score < 5 else "mid" if score < 7.5 else "high"


def kappa(a: list[str], b: list[str]) -> float | None:
    from sklearn.metrics import cohen_kappa_score

    return round(float(cohen_kappa_score(a, b)), 4) if len(a) >= 2 and len(set(a) | set(b)) > 1 else None


def judge(state_like: dict) -> dict:
    from agent.nodes.critic import critic

    out = critic(state_like, None)
    return out["critiques"][-1], out.get("usage", {})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", default="groq")
    ap.add_argument("--n", type=int, default=30)
    args = ap.parse_args(argv)
    if not PROPOSALS.exists():
        setup_env("heuristic")  # drafts come from the deterministic writer so the set is reproducible
        rows = fixed_subset([r for r in load_dev() if r["gold"]["action"] == "bid"], args.n + 8, seed=23)
        recs = [r for r in run_graph_on(rows, label="judge") if r.get("cover_letter")]
        jobs = {r["job"]["id"]: r for r in rows}
        with open(PROPOSALS, "w") as fh:
            for i, r in enumerate(recs[: args.n]):
                fh.write(json.dumps({"proposal_id": f"jp-{i + 1:02d}", "job_id": r["job_id"], "persona": r["persona"],
                                     "job": jobs[r["job_id"]]["job"], "requirements": jobs[r["job_id"]]["gold"]["requirements"],
                                     "cover_letter": r["cover_letter"], "screening_answers": r["screening_answers"],
                                     "unsupported_after": r["unsupported_after"]}) + "\n")
    props = [json.loads(line) for line in open(PROPOSALS)]
    setup_env(args.judge)
    scores = []
    for p in props:
        st = {"job": p["job"], "draft": {"cover_letter": p["cover_letter"], "screening_answers": p["screening_answers"],
                                         "unsupported_after": p.get("unsupported_after") or 0},
              "job_spec": {"requirements": [{"text": t, "must_have": True} for t in p["requirements"]]}, "options": {}}
        c, usage = judge(st)
        scores.append({"proposal_id": p["proposal_id"], "job_id": p["job_id"], "judge_score": c["score"],
                       "judge_verdict": c["verdict"], "judge_reasons": c["reasons"], "tokens": usage.get("tokens", 0)})
    if not LABELS.exists():
        with open(LABELS, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FIELDS)
            for p in props:
                w.writerow([p["proposal_id"], p["job_id"], "", "", "", ""])
    labels = {}
    with open(LABELS) as fh:
        for row in csv.DictReader(fh):
            if (row.get("human_score_0_10") or "").strip() or (row.get("human_verdict_pass_or_revise") or "").strip():
                labels[row["proposal_id"]] = row
    result = {"judge": args.judge, "n_proposals": len(props), "n_human_labels": len(labels), "scores": scores,
              "kappa_verdict": None, "kappa_score_bins": None,
              "note": "kappa is computed only from author-provided labels in evals/datasets/human_labels.csv"}
    if labels:
        common = [s for s in scores if s["proposal_id"] in labels]
        hv = [labels[s["proposal_id"]]["human_verdict_pass_or_revise"].strip().lower() for s in common]
        jv = [s["judge_verdict"] for s in common]
        pairs = [(h, j) for h, j in zip(hv, jv) if h in ("pass", "revise")]
        result["kappa_verdict"] = kappa([h for h, _ in pairs], [j for _, j in pairs]) if pairs else None
        hb = [(labels[s["proposal_id"]]["human_score_0_10"], s["judge_score"]) for s in common if labels[s["proposal_id"]]["human_score_0_10"].strip()]
        result["kappa_score_bins"] = kappa([_bin(float(h)) for h, _ in hb], [_bin(float(j)) for _, j in hb]) if hb else None
    write_json(f"judge_calibration_{args.judge}.json", result)
    print({k: v for k, v in result.items() if k != "scores"})


if __name__ == "__main__":
    main()
