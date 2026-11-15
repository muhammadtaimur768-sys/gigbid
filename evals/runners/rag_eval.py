"""Retrieval evaluation (B4/B5): every variant x persona on the dev sets.

Metrics at item level against gold `evidence_ids`: Recall@5, MRR (within top 10), nDCG@10 (binary gain),
plus p50/p95 retrieval latency. Jobs whose gold evidence is empty (skip / off-profile) are excluded
from those metrics and instead scored for refusal (did the retriever return nothing?).
Breakdowns: by gold job_type and by number of gold requirements (>=4 vs <4).

    python -m evals.runners.rag_eval                     # all variants (60 seeded jobs/persona), ablation, table
    python -m evals.runners.rag_eval --variants v0,v2 --max-jobs 50 --no-ablation
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from rag.config import ROOT, load_config
from rag.variants.v1_decompose import extract_requirements, job_query

RESULTS = ROOT / "evals" / "results"
DATASETS = ROOT / "evals" / "datasets"
PERSONAS = ["aiml", "fullstack", "data"]
# "ev" = evidence-type routing (search proof items only); see rag/config.yaml `variants`
DEFAULT_VARIANTS = ["v0", "v1", "v2", "v0+ev", "ev", "ev+v1", "ev+v2", "ev+v3", "ev+v4", "ev+v5", "ev+v8",
                    "ev+v1+v2", "ev+v2+v4", "ev+v2+v5", "ev+v2+v3", "ev+v2+v5+v8"]
K = 10
SEED = 42


def load_dev(persona: str, max_jobs: int | None) -> list[dict]:
    rows = [json.loads(x) for x in (DATASETS / f"dev_{persona}.jsonl").read_text().splitlines() if x.strip()]
    if max_jobs and len(rows) > max_jobs:
        rows = random.Random(SEED).sample(rows, max_jobs)
    return rows


def ranking(evidence) -> list[str]:
    return list(dict.fromkeys(e.item_id for e in evidence))


def recall_at(rank: list[str], gold: set[str], k: int) -> float:
    return len(set(rank[:k]) & gold) / len(gold)


def mrr(rank: list[str], gold: set[str], k: int = K) -> float:
    for i, it in enumerate(rank[:k]):
        if it in gold:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at(rank: list[str], gold: set[str], k: int = K) -> float:
    dcg = sum(1.0 / math.log2(i + 2) for i, it in enumerate(rank[:k]) if it in gold)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(gold), k)))
    return dcg / idcg if idcg else 0.0


def pct(vals: list[float], q: float) -> float:
    if not vals:
        return float("nan")
    s = sorted(vals)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def _agg(rows: list[dict]) -> dict:
    scored = [r for r in rows if r["gold"]]
    out = {"n": len(scored)}
    if scored:
        for m in ("recall@5", "mrr", "ndcg@10"):
            out[m] = round(statistics.fmean(r[m] for r in scored), 4)
        out["false_refusal_rate"] = round(statistics.fmean(r["empty"] for r in scored), 4)
    return out


def eval_variant(persona: str, variant: str, jobs: list[dict]) -> dict:
    from rag.retriever import get_retriever

    r = get_retriever(persona, variant)
    max_req = load_config()["retrieval"]["max_requirements"]
    r.search("warm up", k=K, requirements=["warm up"])  # load models outside the timed loop
    rows = []
    for row in jobs:
        job, gold = row["job"], row["gold"]
        reqs = extract_requirements(job, max_req)
        t = time.perf_counter()
        ev = r.search(job_query(job), k=K, requirements=reqs)
        ms = (time.perf_counter() - t) * 1000
        rank = ranking(ev)
        g = set(gold.get("evidence_ids") or [])
        rec = {"job_id": job["id"], "ms": ms, "gold": bool(g), "empty": float(len(ev) == 0),
               "job_type": gold.get("job_type", "unknown"), "n_req": len(gold.get("requirements") or []),
               "n_skills": len(job.get("skills_required") or []),
               "action": gold.get("action")}
        if g:
            rec.update({"recall@5": recall_at(rank, g, 5), "mrr": mrr(rank, g), "ndcg@10": ndcg_at(rank, g)})
        rows.append(rec)
    res = {"variant": variant, "persona": persona, "n_jobs": len(rows), **_agg(rows)}
    lat = [x["ms"] for x in rows]
    res["p50_ms"] = round(pct(lat, 0.5), 2)
    res["p95_ms"] = round(pct(lat, 0.95), 2)
    nogold = [x for x in rows if not x["gold"]]
    res["n_no_gold"] = len(nogold)
    res["refusal_rate_no_gold"] = round(statistics.fmean(x["empty"] for x in nogold), 4) if nogold else None
    res["by_job_type"] = {jt: _agg([x for x in rows if x["job_type"] == jt]) for jt in sorted({x["job_type"] for x in rows})}
    res["by_n_requirements"] = {">=4": _agg([x for x in rows if x["n_req"] >= 4]),
                                "<4": _agg([x for x in rows if x["n_req"] < 4])}
    res["by_n_skills"] = {">=4": _agg([x for x in rows if x["n_skills"] >= 4]),
                          "<4": _agg([x for x in rows if x["n_skills"] < 4])}
    return res


def macro(results: list[dict], variant: str) -> dict:
    rs = [r for r in results if r["variant"] == variant and r.get("n")]
    out = {"variant": variant, "personas": len(rs)}
    for m in ("recall@5", "mrr", "ndcg@10", "p50_ms", "p95_ms", "false_refusal_rate"):
        vals = [r[m] for r in rs if r.get(m) is not None]
        out[m] = round(statistics.fmean(vals), 4) if vals else None
    vals = [r["refusal_rate_no_gold"] for r in rs if r.get("refusal_rate_no_gold") is not None]
    out["refusal_rate_no_gold"] = round(statistics.fmean(vals), 4) if vals else None
    for bucket in (">=4", "<4"):
        vals = [r["by_n_requirements"][bucket].get("recall@5") for r in rs if r["by_n_requirements"][bucket].get("n")]
        out[f"recall@5_nreq{bucket}"] = round(statistics.fmean(vals), 4) if vals else None
        vals = [r["by_n_skills"][bucket].get("recall@5") for r in rs if r["by_n_skills"][bucket].get("n")]
        out[f"recall@5_nskills{bucket}"] = round(statistics.fmean(vals), 4) if vals else None
    return out


def pick_best(overall: list[dict]) -> str:
    """Highest nDCG@10 (ties: Recall@5, then lower p95)."""
    cands = [o for o in overall if o.get("ndcg@10") is not None]
    return max(cands, key=lambda o: (o["ndcg@10"], o["recall@5"], -(o["p95_ms"] or 0)))["variant"]


def run(variants: list[str], personas: list[str], max_jobs: int | None, out_name: str = "rag_results") -> dict:
    cfg = load_config()
    results = []
    sizes = {}
    for p in personas:
        jobs = load_dev(p, max_jobs)
        sizes[p] = len(jobs)
        for v in variants:
            t = time.time()
            res = eval_variant(p, v, jobs)
            results.append(res)
            print(f"{p:10s} {v:24s} R@5={res.get('recall@5')} MRR={res.get('mrr')} nDCG={res.get('ndcg@10')} "
                  f"p95={res['p95_ms']}ms ({time.time() - t:.0f}s)", flush=True)
    overall = [macro(results, v) for v in variants]
    payload = {
        "meta": {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "command": "python -m evals.runners.rag_eval", "k": K, "seed": SEED,
                 "n_jobs_per_persona": sizes, "max_jobs": max_jobs,
                 "embedding": cfg["models"]["embedding"], "reranker": cfg["models"]["reranker"],
                 "query": "job title + description; requirements = skills_required + bullet/cue lines (no LLM)",
                 "level": "item (gold evidence_ids); jobs without gold evidence excluded from R@5/MRR/nDCG"},
        "overall": overall, "best": pick_best(overall), "results": results,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{out_name}.json").write_text(json.dumps(payload, indent=2))
    write_csv(results, RESULTS / f"{out_name}.csv")
    return payload


def write_csv(results: list[dict], path: Path) -> None:
    cols = ["variant", "persona", "slice", "n", "recall@5", "mrr", "ndcg@10", "false_refusal_rate", "p50_ms", "p95_ms",
            "refusal_rate_no_gold"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in results:
            w.writerow({**r, "slice": "all"})
            for jt, a in r["by_job_type"].items():
                w.writerow({"variant": r["variant"], "persona": r["persona"], "slice": f"job_type={jt}", **a})
            for b, a in r["by_n_requirements"].items():
                w.writerow({"variant": r["variant"], "persona": r["persona"], "slice": f"n_req{b}", **a})


def corpus_stats(personas: list[str]) -> dict:
    """Counts the DATA_CARD cites: items by type, chunks per chunking, dev-set label distribution."""
    from collections import Counter

    from rag.retriever import get_store, load_items

    out = {}
    for p in personas:
        items = load_items(p, refresh=True)
        dev = [json.loads(x) for x in (DATASETS / f"dev_{p}.jsonl").read_text().splitlines() if x.strip()]
        gold_sizes = [len(r["gold"].get("evidence_ids") or []) for r in dev]
        out[p] = {
            "items_by_type": dict(Counter(i.type for i in items.values())),
            "code_files": sum(len(i.files) for i in items.values()),
            "proposal_outcomes": dict(Counter(i.outcome for i in items.values() if i.type == "proposal")),
            "chunks": {c: len(get_store(p, c).chunks) for c in ("fixed", "structured", "multivector")},
            "dev_jobs": len(dev),
            "dev_actions": dict(Counter(r["gold"].get("action") for r in dev)),
            "dev_scam": sum(bool(r["gold"].get("is_scam")) for r in dev),
            "dev_injection": sum(bool(r["gold"].get("has_injection")) for r in dev),
            "dev_job_types": dict(Counter(r["gold"].get("job_type") for r in dev)),
            "dev_with_gold_evidence": sum(1 for g in gold_sizes if g),
            "gold_evidence_per_job_mean": round(statistics.fmean([g for g in gold_sizes if g]), 2) if any(gold_sizes) else 0,
            "dev_n_req_ge4": sum(1 for r in dev if len(r["gold"].get("requirements") or []) >= 4),
            "gold_evidence_types": dict(Counter(e.split("-")[1] if "-" in e else e
                                                for r in dev for e in (r["gold"].get("evidence_ids") or []))),
        }
    (RESULTS / "rag_corpus_stats.json").write_text(json.dumps(out, indent=2))
    return out


def merge(personas: list[str], variants: list[str], max_jobs: int | None, out_name: str = "rag_results") -> dict:
    """Combine per-persona part files (written with --part) into rag_results.json/.csv."""
    cfg = load_config()
    results, sizes = [], {}
    for p in personas:
        part = json.loads((RESULTS / "parts" / f"{out_name}_{p}.json").read_text())
        results += part["results"]
        sizes.update(part["meta"]["n_jobs_per_persona"])
    overall = [macro(results, v) for v in variants]
    payload = {
        "meta": {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "command": "python -m evals.runners.rag_eval", "k": K, "seed": SEED,
                 "n_jobs_per_persona": sizes, "max_jobs": max_jobs,
                 "embedding": cfg["models"]["embedding"], "reranker": cfg["models"]["reranker"],
                 "query": "job title + description; requirements = skills_required + bullet/cue lines (no LLM)",
                 "level": "item (gold evidence_ids); jobs without gold evidence excluded from R@5/MRR/nDCG",
                 "note": "personas run as parallel processes on a shared, heavily loaded laptop: latencies are inflated"},
        "overall": overall, "best": pick_best(overall), "results": results,
    }
    (RESULTS / f"{out_name}.json").write_text(json.dumps(payload, indent=2))
    write_csv(results, RESULTS / f"{out_name}.csv")
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default=",".join(DEFAULT_VARIANTS))
    ap.add_argument("--personas", default=",".join(PERSONAS))
    ap.add_argument("--max-jobs", type=int, default=60,
                    help="seeded subsample per persona (default 60, the size behind the committed results; 0 = all 200)")
    ap.add_argument("--no-ablation", action="store_true")
    ap.add_argument("--sequential", action="store_true", help="single process instead of one per persona")
    ap.add_argument("--part", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    args.max_jobs = args.max_jobs or None
    args.parallel = not args.sequential
    personas, variants = args.personas.split(","), args.variants.split(",")
    if args.part:  # child of --parallel: one persona, write a part file
        (RESULTS / "parts").mkdir(parents=True, exist_ok=True)
        run(variants, personas, args.max_jobs, out_name=f"parts/rag_results_{personas[0]}")
        return
    corpus_stats(personas)
    if args.parallel:
        import subprocess
        import sys

        procs = [subprocess.Popen([sys.executable, "-m", "evals.runners.rag_eval", "--part", "--personas", p,
                                   "--variants", args.variants] + (["--max-jobs", str(args.max_jobs)] if args.max_jobs else []))
                 for p in personas]
        if any(pr.wait() for pr in procs):
            raise SystemExit("a persona run failed")
        payload = merge(personas, variants, args.max_jobs)
    else:
        payload = run(variants, personas, args.max_jobs)
    print("best:", payload["best"])
    if not args.no_ablation:
        from evals.runners import ablation

        ablation.run(payload["best"], personas, args.max_jobs)
    from evals.runners import make_results_table

    print(make_results_table.render())


if __name__ == "__main__":
    main()
