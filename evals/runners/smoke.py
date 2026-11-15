"""30-job smoke eval used by .github/workflows/eval.yml.

Runs the real decision and retrieval runners on a small fixed subset, then writes the two files the
CI gate reads (evals/results/smoke_decision.json, evals/results/smoke_rag.json). The full committed
results files are restored afterwards, so running this locally never overwrites reported numbers.

    python -m evals.runners.smoke --n 30
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "evals" / "results"
PROTECTED = ["decision_eval.json", "decision_eval_heuristic.json", "decision_records_heuristic.jsonl",
             "gigsim_outcomes.json", "rag_results.json", "rag_results.csv", "rag_table.md", "rag_corpus_stats.json"]


def run(args: list[str]) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run([sys.executable, "-m", *args], cwd=ROOT, check=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--variant", default="ev+v2+v5")
    a = ap.parse_args(argv)

    backup = Path(tempfile.mkdtemp(prefix="gigbid-smoke-"))
    parts = RES / "parts"
    for name in PROTECTED:
        if (RES / name).exists():
            shutil.copy2(RES / name, backup / name)
    if parts.exists():
        shutil.copytree(parts, backup / "parts")
    try:
        run(["evals.runners.decision_eval", "--config", "heuristic", "--n", str(a.n)])
        m = json.loads((RES / "decision_eval_heuristic.json").read_text())["metrics"]
        decision = {"n": m["n"], "bid_skip_f1": m["macro_f1_bid_skip"], "scam_recall": m["scam"]["recall"],
                    "unsupported_claims_per_proposal": m.get("unsupported_claims_per_proposal_after")}

        per_persona = max(1, a.n // 3)
        run(["evals.runners.rag_eval", "--variants", a.variant, "--max-jobs", str(per_persona), "--no-ablation", "--sequential"])
        r = json.loads((RES / "rag_results.json").read_text())
        row = next(o for o in r["overall"] if o["variant"] == a.variant)
        rag = {"variant": a.variant, "jobs_per_persona": per_persona, "recall_at_5": row["recall@5"], "ndcg_at_10": row["ndcg@10"]}
    finally:
        for name in PROTECTED:
            if (backup / name).exists():
                shutil.copy2(backup / name, RES / name)
        if (backup / "parts").exists():
            shutil.rmtree(parts, ignore_errors=True)
            shutil.copytree(backup / "parts", parts)
        shutil.rmtree(backup, ignore_errors=True)

    (RES / "smoke_decision.json").write_text(json.dumps(decision, indent=2) + "\n")
    (RES / "smoke_rag.json").write_text(json.dumps(rag, indent=2) + "\n")
    print(json.dumps({"decision": decision, "rag": rag}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
