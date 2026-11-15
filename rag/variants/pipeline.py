"""Composable retrieval pipeline. Variant flags (rag/config.yaml `variants`) switch components on:

  query:      whole | decompose          (V1)
  retrieval:  dense | hybrid             (V2)
  rerank:     cross-encoder              (V3)
  outcome:    outcome-aware boost        (V4)
  multivector + project expansion        (V5)
  corrective: grade / re-query / refuse  (V8, see v8_corrective.py)
"""
from __future__ import annotations

from rag.index.embed import embed_queries
from rag.index.store import VectorStore
from rag.variants import v0_naive, v2_hybrid, v3_rerank, v4_outcome, v5_multivector


class Pipeline:
    def __init__(self, store: VectorStore, flags: dict, cfg: dict):
        self.store, self.flags, self.cfg = store, flags, cfg
        self.r = cfg["retrieval"]
        self._success = v4_outcome.skill_success(store) if flags.get("outcome") else {}

    # one query -> ranked chunk rows with optional rerank logits
    def _one(self, query: str, qvec, mask, n: int | None = None, retrieval: str | None = None,
             top_n: int | None = None) -> list[tuple]:
        n = n or self.r["candidates"]
        mode = retrieval or self.flags["retrieval"]
        if mode == "hybrid":
            cands = v2_hybrid.hybrid_candidates(self.store, query, qvec, n, self.r["rrf_k"], self.r["hybrid_weights"], mask)
        else:
            cands = v0_naive.dense_candidates(self.store, qvec, n, mask)
        if self.flags.get("rerank"):
            return v3_rerank.rerank(self.store, query, cands, top_n or self.r["rerank_top_n"])
        return [(row, s, None) for row, s in cands]

    def _to_items(self, ranked: list[tuple]) -> list[dict]:
        """Aggregate chunk rows to items (first = best chunk), or keep chunks for the naive baseline."""
        out, seen = [], set()
        for rank, (row, s, ce) in enumerate(ranked):
            c = self.store.chunks[row]
            key = c.item_id if self.flags.get("dedupe_items", True) else c.chunk_id
            if key in seen:
                if ce is not None:  # keep the max rerank logit per item
                    for d in out:
                        if d["key"] == key and (d["rerank"] is None or ce > d["rerank"]):
                            d["rerank"] = ce
                continue
            seen.add(key)
            out.append({"key": key, "item_id": c.item_id, "row": row, "raw": s, "rerank": ce, "rank": rank})
        return out

    def run_queries(self, queries: list[str], weights: list[float], mask, n: int | None = None,
                    retrieval: str | None = None) -> tuple[list[dict], dict[str, list[dict]]]:
        """Returns fused item list and per-query item lists (for grading)."""
        vecs = embed_queries(queries)
        per_query = {}
        lists = []
        for i, (q, v) in enumerate(zip(queries, vecs)):
            top_n = self.r["rerank_top_n"] if i == 0 else self.r["rerank_top_n_requirement"]
            items = self._to_items(self._one(q, v, mask, n, retrieval, top_n))
            per_query[q] = items
            lists.append(items)
        if len(lists) == 1:
            fused = [dict(d, score=1.0 / (self.r["rrf_k"] + i + 1)) for i, d in enumerate(lists[0])]
        else:
            info: dict[str, dict] = {}
            keyed = []
            for lst in lists:
                keyed.append([d["key"] for d in lst])
                for d in lst:
                    prev = info.get(d["key"])
                    if prev is None or (d["rerank"] is not None and (prev["rerank"] is None or d["rerank"] > prev["rerank"])):
                        info[d["key"]] = d
            fused = [dict(info[key], score=s) for key, s in v2_hybrid.rrf(keyed, self.r["rrf_k"], weights)]
        if self.flags.get("outcome"):
            fused = v4_outcome.boost(fused, self.store, self.cfg, self._success)
        if self.flags.get("multivector") and self.flags.get("project_expand", True):
            fused = v5_multivector.project_expand(fused, self.store, self.r["project_expand_decay"], limit=5)
        return fused, per_query

    def queries_for(self, query: str, requirements: list[str] | None) -> tuple[list[str], list[float]]:
        if self.flags.get("query") == "decompose" and requirements:
            reqs = [r for r in requirements if r.strip()][: self.r["max_requirements"]]
            return [query] + reqs, [self.r["decompose_whole_query_weight"]] + [1.0] * len(reqs)
        return [query], [1.0]

    def search(self, query: str, k: int, mask, requirements: list[str] | None = None) -> list[dict]:
        queries, weights = self.queries_for(query, requirements)
        fused, _ = self.run_queries(queries, weights, mask)
        return fused[:k]
