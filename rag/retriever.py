"""Retriever factory. The variant comes from config (agent/config.yaml `rag.variant`, else
rag/shipped_variant.yaml) unless passed explicitly; compositions like "v1+v2+v3+v4" are allowed.

    r = get_retriever("aiml")                       # shipped variant
    r = get_retriever("aiml", "v1+v2+v3")
    ev = r.search("RAG chatbot with Pinecone", k=5, filters={"type": ["case_study", "repo"]},
                  requirements=["Pinecone", "LangChain"])
    r.get_item("aiml-case-03"); r.list_skills()
    r.add_document("aiml-case-99", "case_study", text, project="...", skills=[...])
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from rag.config import load_config, resolve_path, variant_flags
from rag.index.store import VectorStore, write_manifest
from rag.ingest.chunkers import chunk_item
from rag.ingest.loaders import item_from_upload, load_persona
from rag.types import Evidence, Item
from rag.variants.pipeline import Pipeline
from rag.variants.v8_corrective import CorrectivePipeline

_STORES: dict[tuple[str, str], VectorStore] = {}
_ITEMS: dict[str, dict[str, Item]] = {}
_LOCK = threading.RLock()
SYNTHETIC = {"summary", "code_digest"}


def _persona_dir(persona: str) -> Path:
    return resolve_path(load_config()["paths"]["personas_dir"]) / persona


def _index_dir(persona: str, chunking: str) -> Path:
    return resolve_path(load_config()["paths"]["index_dir"]) / persona / chunking


def _corpus_signature(persona: str) -> str:
    """Cheap fingerprint of the corpus files (mtime + size) to know when the cached index is stale."""
    root = _persona_dir(persona)
    parts = []
    for p in sorted(root.rglob("*")) if root.exists() else []:
        if p.is_file():
            st = p.stat()
            parts.append(f"{p.relative_to(root)}:{st.st_size}:{int(st.st_mtime)}")
    import hashlib

    return hashlib.sha1("|".join(parts).encode()).hexdigest()


def load_items(persona: str, refresh: bool = False) -> dict[str, Item]:
    with _LOCK:
        if refresh or persona not in _ITEMS:
            items = load_persona(_persona_dir(persona), persona)
            uploads = _index_dir(persona, "uploads") / "items.jsonl"
            if uploads.exists():
                for line in uploads.read_text().splitlines():
                    if line.strip():
                        it = Item.model_validate_json(line)
                        items = [i for i in items if i.item_id != it.item_id] + [it]
            _ITEMS[persona] = {i.item_id: i for i in items}
        return _ITEMS[persona]


def get_store(persona: str, chunking: str, rebuild: bool = False) -> VectorStore:
    key = (persona, chunking)
    with _LOCK:
        if key in _STORES and not rebuild:
            return _STORES[key]
        cfg = load_config()
        path = _index_dir(persona, chunking)
        store = VectorStore(path)
        sig = _corpus_signature(persona)
        manifest = path / "manifest.json"
        fresh = False
        if not rebuild and manifest.exists() and store.load():
            import json

            fresh = json.loads(manifest.read_text()).get("signature") == sig
        if not fresh:
            items = load_items(persona, refresh=True)
            chunks = [c for it in items.values() for c in chunk_item(it, chunking, cfg)]
            t = time.time()
            store.build(chunks)
            store.save()
            write_manifest(path, {"persona": persona, "chunking": chunking, "signature": sig,
                                  "n_items": len(items), "n_chunks": len(chunks),
                                  "embedding": cfg["models"]["embedding"], "build_s": round(time.time() - t, 2)})
        _STORES[key] = store
        return store


class Retriever:
    def __init__(self, persona: str, variant: str | None = None):
        cfg = load_config()
        self.persona = persona
        self.variant = variant or cfg["active_variant"]
        self.flags = variant_flags(self.variant)
        self.chunking = "multivector" if self.flags.get("multivector") else self.flags["chunking"]
        self.cfg = cfg
        self.store = get_store(persona, self.chunking)
        self._build_pipeline()
        self.last_info: dict = {}

    def _proof_mask(self):
        import numpy as np

        items = load_items(self.persona)
        proof = set(self.cfg["proof_types"])
        return np.array([getattr(items.get(c.item_id), "type", c.type) in proof for c in self.store.chunks], dtype=bool)

    def _build_pipeline(self) -> None:
        pipe = Pipeline(self.store, self.flags, self.cfg)
        self.pipeline = CorrectivePipeline(pipe) if self.flags.get("corrective") else pipe

    # ---------------- public API ----------------
    def search(self, query: str, k: int = 5, filters: dict | None = None,
               requirements: list[str] | None = None) -> list[Evidence]:
        mask = self.store.mask(filters) if filters else None
        if self.flags.get("proof_only") and not (filters and "type" in filters):
            pm = self._proof_mask()
            mask = pm if mask is None else (mask & pm)
        hits = self.pipeline.search(query, k, mask, requirements)
        self.last_info = getattr(self.pipeline, "last_state", {}) or {}
        return [self._evidence(h) for h in hits]

    def _evidence(self, h: dict) -> Evidence:
        c = self.store.chunks[h["row"]]
        if c.type in SYNTHETIC:  # show a real chunk of the item, keep the multi-vector score
            real = [r for r in self.store.item_rows[c.item_id] if self.store.chunks[r].type not in SYNTHETIC]
            if real:
                c = self.store.chunks[real[0]]
        return Evidence(chunk_id=c.chunk_id, item_id=c.item_id, type=c.type, source=c.source, project=c.project,
                        date=c.date, outcome=c.outcome, text=c.text, score=float(h["score"]), skills=c.skills,
                        rerank_score=h.get("rerank"))

    def get_item(self, item_id: str) -> dict:
        items = load_items(self.persona)
        it = items.get(item_id)
        if it is None:
            raise KeyError(item_id)
        d = it.model_dump()
        d["full_text"] = "\n\n".join([it.text] + [f"# file: {f['path']}\n{f['text']}" for f in it.files])
        d["chunk_ids"] = [self.store.chunks[r].chunk_id for r in self.store.item_rows.get(item_id, [])]
        return d

    def list_items(self, type: str | None = None) -> list[dict]:
        return [{"item_id": i.item_id, "type": i.type, "title": i.title, "project": i.project, "date": i.date,
                 "outcome": i.outcome} for i in load_items(self.persona).values() if type is None or i.type == type]

    def list_skills(self) -> list[dict]:
        agg: dict[str, set] = {}
        for it in load_items(self.persona).values():
            for s in it.skills:
                agg.setdefault(s.strip().lower(), set()).add(it.item_id)
        out = [{"skill": s, "count": len(ids), "items": sorted(ids)} for s, ids in agg.items()]
        return sorted(out, key=lambda d: (-d["count"], d["skill"]))

    def add_document(self, item_id: str, type: str, text: str, **meta) -> dict:
        """Incremental indexing of one new or edited item (UI upload). Only new text is embedded;
        every chunking of this persona that is already loaded is updated and persisted."""
        it = item_from_upload(self.persona, item_id, type, text, **meta)
        with _LOCK:
            items = load_items(self.persona)
            items[item_id] = it
            up = _index_dir(self.persona, "uploads")
            up.mkdir(parents=True, exist_ok=True)
            upath = up / "items.jsonl"
            prev = [Item.model_validate_json(x) for x in upath.read_text().splitlines() if x.strip()] if upath.exists() else []
            uploaded = [i for i in prev if i.item_id != item_id] + [it]
            upath.write_text("\n".join(i.model_dump_json() for i in uploaded) + "\n")
            n = 0
            for (persona, chunking), store in list(_STORES.items()):
                if persona != self.persona:
                    continue
                chunks = chunk_item(it, chunking, self.cfg)
                store.add(chunks)
                store.save()
                n = len(chunks) if store is self.store else n
                mpath = store.path / "manifest.json"
                write_manifest(store.path, {"persona": persona, "chunking": chunking,
                                            "signature": _corpus_signature(persona), "n_items": len(items),
                                            "n_chunks": len(store.chunks), "embedding": self.cfg["models"]["embedding"],
                                            "incremental": True}) if mpath.exists() else None
            self._build_pipeline()
        return {"item_id": item_id, "chunks": n, "total_chunks": len(self.store.chunks)}


_RETRIEVERS: dict[tuple[str, str], Retriever] = {}


def get_retriever(persona: str, variant: str | None = None) -> Retriever:
    variant = variant or load_config()["active_variant"]
    key = (persona, variant)
    with _LOCK:
        if key not in _RETRIEVERS:
            _RETRIEVERS[key] = Retriever(persona, variant)
        return _RETRIEVERS[key]
