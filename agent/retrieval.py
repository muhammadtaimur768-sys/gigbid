"""Evidence retrieval adapter: the RAG package retriever, with a lexical fallback (degraded mode)."""
from __future__ import annotations

import functools
import re
import threading

from agent.settings import ROOT, cfg

_STOP = set("a an the and or of to in for on with by from at as is are be this that we you our your i my me "
            "need needs looking want wants will can must have has it its into using use build experience "
            "strong good great expert years project projects work".split())


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9][a-z0-9+#.\-]*[a-z0-9+#]|[a-z0-9]", (text or "").lower()) if t not in _STOP]


class LexicalRetriever:
    """Token-overlap retriever over data/personas/<persona> (used only when rag/ is unavailable)."""

    def __init__(self, persona: str):
        self.persona = persona
        self.items: dict[str, dict] = {}
        base = ROOT / "data" / "personas" / persona
        for p in list(base.rglob("*.md")) + list(base.rglob("*.py")) + list(base.rglob("*.ts")) + list(base.rglob("*.sql")):
            if p.name == "cv.md":
                iid, typ = f"{persona}-cv", "cv"
            elif "case_studies" in p.parts:
                iid, typ = p.stem, "case_study"
            elif "repos" in p.parts:
                iid, typ = p.parent.name if p.name == "README.md" else p.parts[p.parts.index("repos") + 1], "repo"
            else:
                continue
            txt = p.read_text(errors="ignore")
            it = self.items.setdefault(iid, {"item_id": iid, "type": typ, "text": ""})
            it["text"] += "\n" + txt
        self.chunks = []
        for iid, it in self.items.items():
            paras = [x.strip() for x in re.split(r"\n\s*\n", it["text"]) if len(x.strip()) > 60]
            for n, para in enumerate(paras):
                self.chunks.append({"chunk_id": f"{iid}#c{n}", "item_id": iid, "type": it["type"], "text": para,
                                    "tok": set(tokens(para))})

    def search(self, query, k=5, filters=None, requirements=None):
        q = set(tokens(query))
        scored = []
        for c in self.chunks:
            ov = len(q & c["tok"]) / (len(q) or 1)
            if ov > 0:
                scored.append((ov, c))
        scored.sort(key=lambda x: -x[0])
        seen, out = set(), []
        for ov, c in scored:
            if c["item_id"] in seen:
                continue
            seen.add(c["item_id"])
            out.append(_Ev(chunk_id=c["chunk_id"], item_id=c["item_id"], type=c["type"], text=c["text"][:600],
                           score=round(ov, 3), skills=[], outcome=None, project=None))
            if len(out) >= k:
                break
        return out

    def get_item(self, item_id):
        return self.items.get(item_id, {})


class _Ev(dict):
    def __getattr__(self, k):
        return self.get(k)


_cache: dict[str, object] = {}
_lock = threading.Lock()


def get_evidence_retriever(persona: str):
    """rag.retriever.get_retriever(persona) if available, else the lexical fallback."""
    with _lock:
        if persona in _cache:
            return _cache[persona]
        try:
            from rag.retriever import get_retriever

            r = get_retriever(persona, cfg("rag", "variant", default=None))
        except Exception:
            r = LexicalRetriever(persona)
        _cache[persona] = r
        return r


def evidence_to_dict(ev) -> dict:
    if hasattr(ev, "model_dump"):
        return ev.model_dump()
    return dict(ev)


@functools.lru_cache(maxsize=8)
def load_profile(persona: str) -> dict:
    import json

    p = ROOT / "data" / "personas" / persona / "profile.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"persona": persona, "name": "Freelancer", "title": persona, "hourly_floor": 30, "hourly_target": 60,
            "skills": [], "bio": ""}

