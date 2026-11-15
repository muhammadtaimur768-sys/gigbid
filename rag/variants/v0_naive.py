"""V0 baseline: fixed-size chunks, one dense cosine top-k over the whole job post, no item dedupe."""
from __future__ import annotations

import numpy as np

from rag.index.store import VectorStore

NAME = "v0"
FLAGS = {"chunking": "fixed", "query": "whole", "retrieval": "dense", "dedupe_items": False}


def dense_candidates(store: VectorStore, qvec: np.ndarray, n: int, mask=None) -> list[tuple[int, float]]:
    """(row, cosine) ranked by cosine similarity."""
    return store.dense(qvec, n, mask)
