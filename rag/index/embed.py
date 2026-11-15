"""Lazy singletons for the fastembed embedding model and cross-encoder."""
from __future__ import annotations

import threading

import numpy as np

from rag.config import load_config, resolve_path

_lock = threading.Lock()
_embedder = None
_reranker = None


def get_embedder():
    global _embedder
    with _lock:
        if _embedder is None:
            from fastembed import TextEmbedding

            cfg = load_config()
            _embedder = TextEmbedding(cfg["models"]["embedding"], cache_dir=str(resolve_path(cfg["paths"]["model_cache"])))
    return _embedder


def get_reranker():
    global _reranker
    with _lock:
        if _reranker is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            cfg = load_config()
            _reranker = TextCrossEncoder(cfg["models"]["reranker"], cache_dir=str(resolve_path(cfg["paths"]["model_cache"])))
    return _reranker


def embed_passages(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    vecs = np.array(list(get_embedder().embed(texts, batch_size=64)), dtype=np.float32)
    return vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)


def embed_query(text: str) -> np.ndarray:
    prefix = load_config()["models"].get("query_prefix", "")
    v = np.array(next(iter(get_embedder().embed([prefix + text]))), dtype=np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


def embed_queries(texts: list[str]) -> np.ndarray:
    prefix = load_config()["models"].get("query_prefix", "")
    vecs = np.array(list(get_embedder().embed([prefix + t for t in texts])), dtype=np.float32)
    return vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)


def rerank_scores(query: str, docs: list[str]) -> list[float]:
    if not docs:
        return []
    return [float(s) for s in get_reranker().rerank(query, docs, batch_size=32)]
