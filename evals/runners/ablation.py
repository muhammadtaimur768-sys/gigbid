"""Ablation: remove one component at a time from the best pipeline and re-measure.

    python -m evals.runners.ablation --best v1+v2+v3+v4
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from evals.runners.rag_eval import PERSONAS, RESULTS, eval_variant, load_dev, macro

NAMES = {"v1": "requirement decomposition", "v2": "hybrid BM25+dense (RRF)", "v3": "cross-encoder rerank",
         "v4": "outcome-aware boost", "v5": "multi-vector items", "v8": "corrective loop", "base": "structured chunks", "ev": "evidence-type routing (proof items only)"}


def variants_for(best: str) -> list[tuple[str, str]]:
    parts = [p for p in best.split("+") if p]
    out = [("full", best)]
    for p in parts:
        rest = [q for q in parts if q != p]
        out.append((f"-{p} ({NAMES.get(p, p)})", "+".join(rest) if rest else "base"))
    out.append(("baseline v0", "v0"))
    return out


def run(best: str, personas: list[str] | None = None, max_jobs: int | None = None) -> dict:
    personas = personas or PERSONAS
    rows, results = [], []
    variants = variants_for(best)
    cached = {}
    main_path = RESULTS / "rag_results.json"
    if main_path.exists():  # reuse runs already measured on the same seeded sample
        prev = json.loads(main_path.read_text())
        if prev["meta"].get("max_jobs") == max_jobs:
            cached = {(r["persona"], r["variant"]): r for r in prev["results"]}
    for p in personas:
        jobs = load_dev(p, max_jobs)
        for label, v in variants:
            res = dict(cached[(p, v)]) if (p, v) in cached else eval_variant(p, v, jobs)
            res["ablation"] = label
            results.append(res)
    full = macro(results, best)
    for label, v in variants:
        m = macro(results, v)
        m["ablation"] = label
        for k in ("recall@5", "mrr", "ndcg@10"):
            if m.get(k) is not None and full.get(k) is not None:
                m[f"delta_{k}"] = round(m[k] - full[k], 4)
        rows.append(m)
        print(f"{label:40s} {v:22s} R@5={m['recall@5']} nDCG={m['ndcg@10']} dR@5={m.get('delta_recall@5')}")
    payload = {"meta": {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "best": best,
                        "max_jobs": max_jobs, "personas": personas,
                        "command": f"python -m evals.runners.ablation --best {best}"},
               "ablation": rows,
               "per_persona": [{k: r[k] for k in ("ablation", "variant", "persona", "recall@5", "mrr", "ndcg@10", "p95_ms")
                                if k in r} for r in results]}
    (RESULTS / "rag_ablation.json").write_text(json.dumps(payload, indent=2))
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--best", default=None, help="defaults to `best` in evals/results/rag_results.json")
    ap.add_argument("--personas", default=",".join(PERSONAS))
    ap.add_argument("--max-jobs", type=int, default=None)
    a = ap.parse_args()
    best = a.best or json.loads((RESULTS / "rag_results.json").read_text())["best"]
    run(best, a.personas.split(","), a.max_jobs)


if __name__ == "__main__":
    main()
