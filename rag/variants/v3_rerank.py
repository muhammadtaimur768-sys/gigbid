"""V3: cross-encoder reranking (fastembed TextCrossEncoder) of the top-N chunk candidates."""
from __future__ import annotations

from rag.index.embed import rerank_scores
from rag.index.store import VectorStore

NAME = "v3"
FLAGS = {"rerank": True}


def rerank(store: VectorStore, query: str, candidates: list[tuple[int, float]], top_n: int) -> list[tuple[int, float, float]]:
    """Returns [(row, rerank_logit, rerank_logit)] for the top_n candidates, best first; the rest keep
    their order after them with no rerank score."""
    head = candidates[:top_n]
    scores = rerank_scores(query, [store.chunks[r].text for r, _ in head])
    ranked = sorted(((r, s, s) for (r, _), s in zip(head, scores)), key=lambda t: -t[1])
    return ranked + [(r, float("-inf"), None) for r, _ in candidates[top_n:]]
