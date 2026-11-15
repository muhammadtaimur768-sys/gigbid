"""Prints (and writes evals/results/rag_table.md) markdown tables from the RAG result files.

    python -m evals.runners.make_results_table
"""
from __future__ import annotations

import json

from evals.runners.rag_eval import RESULTS


def _f(v, ms=False):
    if v is None:
        return "not measured"
    return f"{v:.0f}" if ms else f"{v:.3f}"


def render(write: bool = True) -> str:
    res = json.loads((RESULTS / "rag_results.json").read_text())
    meta = res["meta"]
    out = [f"### Retrieval results (macro-average over personas; n jobs per persona = {meta['n_jobs_per_persona']})", "",
           "| Variant | Recall@5 | MRR | nDCG@10 | Recall@5 (>=4 req) | Recall@5 (<4 req) | Recall@5 (>=4 skills) | Recall@5 (<4 skills) | p50 ms | p95 ms | refusal on no-gold jobs | false refusal |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for o in res["overall"]:
        mark = " **(best)**" if o["variant"] == res["best"] else ""
        out.append(f"| {o['variant']}{mark} | {_f(o['recall@5'])} | {_f(o['mrr'])} | {_f(o['ndcg@10'])} | "
                   f"{_f(o.get('recall@5_nreq>=4'))} | {_f(o.get('recall@5_nreq<4'))} | "
                   f"{_f(o.get('recall@5_nskills>=4'))} | {_f(o.get('recall@5_nskills<4'))} | {_f(o['p50_ms'], True)} | "
                   f"{_f(o['p95_ms'], True)} | {_f(o.get('refusal_rate_no_gold'))} | {_f(o.get('false_refusal_rate'))} |")
    out += ["", "### Per persona (Recall@5 / nDCG@10)", ""]
    personas = sorted({r["persona"] for r in res["results"]})
    out.append("| Variant | " + " | ".join(personas) + " |")
    out.append("|---|" + "---|" * len(personas))
    for o in res["overall"]:
        cells = []
        for p in personas:
            r = next((x for x in res["results"] if x["variant"] == o["variant"] and x["persona"] == p), None)
            cells.append(f"{_f(r.get('recall@5'))} / {_f(r.get('ndcg@10'))}" if r and r.get("n") else "not measured")
        out.append(f"| {o['variant']} | " + " | ".join(cells) + " |")
    best = res["best"]
    v0 = "v0"
    out += ["", f"### By job type (Recall@5): v0 vs {best}", "", "| Persona | Job type | n | v0 | best |", "|---|---|---|---|---|"]
    for p in personas:
        r0 = next((x for x in res["results"] if x["variant"] == v0 and x["persona"] == p), None)
        rb = next((x for x in res["results"] if x["variant"] == best and x["persona"] == p), None)
        if not (r0 and rb):
            continue
        for jt, a in rb["by_job_type"].items():
            if not a.get("n"):
                continue
            out.append(f"| {p} | {jt} | {a['n']} | {_f(r0['by_job_type'].get(jt, {}).get('recall@5'))} | {_f(a.get('recall@5'))} |")
    abl = RESULTS / "rag_ablation.json"
    if abl.exists():
        a = json.loads(abl.read_text())
        out += ["", f"### Ablation of {a['meta']['best']} (macro over personas)", "",
                "| Removed | Variant | Recall@5 | nDCG@10 | delta Recall@5 | delta nDCG@10 | p95 ms |", "|---|---|---|---|---|---|---|"]
        for r in a["ablation"]:
            out.append(f"| {r['ablation']} | {r['variant']} | {_f(r['recall@5'])} | {_f(r['ndcg@10'])} | "
                       f"{_f(r.get('delta_recall@5'))} | {_f(r.get('delta_ndcg@10'))} | {_f(r['p95_ms'], True)} |")
    text = "\n".join(out) + "\n"
    if write:
        (RESULTS / "rag_table.md").write_text(text)
    return text


if __name__ == "__main__":
    print(render())
