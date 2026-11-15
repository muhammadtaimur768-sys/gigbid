"""V5: multi-vector items. Each item gets an extra summary vector and (repos) a code-digest vector
(imported libraries + defined symbols) next to its README and code chunks; results are aggregated per
item and siblings of the same project are pulled in, so a repo whose README looks irrelevant is still
returned when its code (or its case study) matches."""
from __future__ import annotations

from rag.index.store import VectorStore

NAME = "v5"
FLAGS = {"multivector": True}
CHUNKING = "multivector"  # see rag.ingest.chunkers.multivector_chunks


def project_expand(scored_items: list[dict], store: VectorStore, decay: float, limit: int) -> list[dict]:
    by_id = {d["item_id"]: d for d in scored_items}
    projects: dict[str, list[str]] = {}
    for item_id, rows in store.item_rows.items():
        p = store.chunks[rows[0]].project
        if p:
            projects.setdefault(p, []).append(item_id)
    for d in list(scored_items[:limit]):
        p = store.chunks[d["row"]].project
        for sib in projects.get(p, []):
            if sib == d["item_id"] or store.chunks[store.item_rows[sib][0]].type in ("proposal", "review"):
                continue
            s = d["score"] * decay
            if sib not in by_id or by_id[sib]["score"] < s:
                row = store.item_rows[sib][0]
                by_id[sib] = {"item_id": sib, "row": row, "score": s, "rerank": None, "via": d["item_id"]}
    return sorted(by_id.values(), key=lambda d: -d["score"])
