"""V2: BM25 + dense, fused with reciprocal rank fusion. Exact tool names ("Celery", "dbt") survive
here even when the embedding blurs them."""
from __future__ import annotations

import numpy as np

from rag.index.store import VectorStore

NAME = "v2"
FLAGS = {"retrieval": "hybrid"}


def rrf(lists: list[list], k: int = 60, weights: list[float] | None = None) -> list[tuple]:
    """Fuse ranked lists of keys (or (key, score) tuples). Returns [(key, fused_score)] best first."""
    weights = weights or [1.0] * len(lists)
    scores: dict = {}
    for lst, w in zip(lists, weights):
        for rank, entry in enumerate(lst):
            key = entry[0] if isinstance(entry, tuple) else entry
            scores[key] = scores.get(key, 0.0) + w / (k + rank + 1)
    return sorted(scores.items(), key=lambda kv: -kv[1])


def hybrid_candidates(store: VectorStore, query: str, qvec: np.ndarray, n: int, rrf_k: int,
                      weights: dict, mask=None) -> list[tuple[int, float]]:
    dense = store.dense(qvec, n, mask)
    lex = store.lexical(query, n, mask)
    return rrf([dense, lex], k=rrf_k, weights=[weights.get("dense", 1.0), weights.get("bm25", 1.0)])[:n]
