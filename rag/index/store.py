"""Vector store (dense numpy matrix on disk) + BM25 index over the same chunk list.

Layout: data/processed/index/{persona}/{chunking}/
  chunks.jsonl     one Chunk per line (row i <-> matrix row i)
  vectors.npy      float32 [n_chunks, dim], L2-normalised (cosine = dot product)
  emb_cache.npz    sha1(text) -> vector, so re-indexing only embeds new or changed chunks
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from rag.index.embed import embed_passages
from rag.types import Chunk

TOKEN_RE = re.compile(r"[a-z0-9]+(?:[+#]+|(?:[._-][a-z0-9]+)+)?")
STOP = set("""a an the and or of to in on for with by at from as is are was were be been this that these those it its
i we you our your my me us they them their he she his her not no but if then so do does did have has had can could will
would should may might must into over under about via per than also just very more most such any all each other""".split())


def tokenize(text: str) -> list[str]:
    toks = TOKEN_RE.findall(text.lower())
    out = []
    for t in toks:
        if t in STOP:
            continue
        out.append(t)
        if any(c in t for c in "._-"):  # "node.js" also matches "node", "js"
            out += [p for p in re.split(r"[._-]", t) if p and p not in STOP]
    return out


def _h(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()


class VectorStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.chunks: list[Chunk] = []
        self.matrix = np.zeros((0, 384), dtype=np.float32)
        self._cache: dict[str, np.ndarray] = {}
        self.bm25: BM25Okapi | None = None
        self.item_rows: dict[str, list[int]] = {}

    # ---------- persistence ----------
    def load(self) -> bool:
        cp, vp = self.path / "chunks.jsonl", self.path / "vectors.npy"
        if not (cp.exists() and vp.exists()):
            return False
        self.chunks = [Chunk.model_validate_json(line) for line in cp.read_text().splitlines() if line.strip()]
        self.matrix = np.load(vp)
        self._load_cache()
        self._rebuild_aux()
        return len(self.chunks) == self.matrix.shape[0]

    def save(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / "chunks.jsonl").write_text("\n".join(c.model_dump_json() for c in self.chunks) + "\n")
        np.save(self.path / "vectors.npy", self.matrix)
        if self._cache:
            keys = list(self._cache)
            np.savez(self.path / "emb_cache.npz", keys=np.array(keys), vecs=np.stack([self._cache[k] for k in keys]))

    def _load_cache(self) -> None:
        p = self.path / "emb_cache.npz"
        if p.exists():
            d = np.load(p, allow_pickle=False)
            self._cache = {str(k): v for k, v in zip(d["keys"], d["vecs"])}

    # ---------- building ----------
    def _embed_with_cache(self, texts: list[str]) -> np.ndarray:
        missing = [t for t in dict.fromkeys(texts) if _h(t) not in self._cache]
        if missing:
            for t, v in zip(missing, embed_passages(missing)):
                self._cache[_h(t)] = v
        return np.stack([self._cache[_h(t)] for t in texts]) if texts else np.zeros((0, 384), np.float32)

    def build(self, chunks: list[Chunk]) -> None:
        self._load_cache()
        self.chunks = list(chunks)
        self.matrix = self._embed_with_cache([c.text for c in chunks]).astype(np.float32)
        self._rebuild_aux()

    def add(self, chunks: list[Chunk]) -> None:
        """Incremental add: replaces any existing chunks of the same items, embeds only new text."""
        ids = {c.item_id for c in chunks}
        keep = [i for i, c in enumerate(self.chunks) if c.item_id not in ids]
        new = self._embed_with_cache([c.text for c in chunks])
        self.chunks = [self.chunks[i] for i in keep] + list(chunks)
        self.matrix = np.vstack([self.matrix[keep], new]).astype(np.float32) if keep else new.astype(np.float32)
        self._rebuild_aux()

    def _rebuild_aux(self) -> None:
        self.item_rows = {}
        for i, c in enumerate(self.chunks):
            self.item_rows.setdefault(c.item_id, []).append(i)
        corpus = [tokenize(self._bm25_text(c)) or ["_"] for c in self.chunks]
        self.bm25 = BM25Okapi(corpus) if corpus else None

    @staticmethod
    def _bm25_text(c: Chunk) -> str:
        return c.text

    # ---------- search ----------
    def mask(self, filters: dict | None) -> np.ndarray:
        m = np.ones(len(self.chunks), dtype=bool)
        if not filters:
            return m
        for key, want in filters.items():
            if want is None:
                continue
            wants = set(want) if isinstance(want, (list, tuple, set)) else {want}
            wants = {str(w).lower() for w in wants}
            for i, c in enumerate(self.chunks):
                if not m[i]:
                    continue
                val = getattr(c, key, None)
                if key == "type" and val in {"summary", "code_digest"}:
                    val = "repo" if c.item_id.split("-")[1:2] == ["repo"] else val
                if isinstance(val, list):
                    ok = bool({str(v).lower() for v in val} & wants)
                else:
                    ok = val is not None and str(val).lower() in wants
                m[i] = ok
        return m

    def dense(self, qvec: np.ndarray, n: int, mask: np.ndarray | None = None) -> list[tuple[int, float]]:
        if not len(self.chunks):
            return []
        sims = self.matrix @ qvec
        if mask is not None:
            sims = np.where(mask, sims, -np.inf)
        n = min(n, len(sims))
        idx = np.argpartition(-sims, n - 1)[:n]
        idx = idx[np.argsort(-sims[idx])]
        return [(int(i), float(sims[i])) for i in idx if np.isfinite(sims[i])]

    def lexical(self, query: str, n: int, mask: np.ndarray | None = None) -> list[tuple[int, float]]:
        if self.bm25 is None:
            return []
        toks = tokenize(query)
        if not toks:
            return []
        scores = np.asarray(self.bm25.get_scores(toks))
        if mask is not None:
            scores = np.where(mask, scores, -np.inf)
        n = min(n, len(scores))
        idx = np.argpartition(-scores, n - 1)[:n]
        idx = idx[np.argsort(-scores[idx])]
        return [(int(i), float(scores[i])) for i in idx if np.isfinite(scores[i]) and scores[i] > 0]


def write_manifest(path: Path, info: dict) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "manifest.json").write_text(json.dumps(info, indent=2))
