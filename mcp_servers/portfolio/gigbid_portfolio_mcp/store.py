"""Portfolio backends.

* RagBackend: the GigBid hybrid retriever (`rag.retriever.get_retriever`), imported lazily.
* KeywordBackend: dependency-free TF-IDF keyword search over a portfolio folder, so the server
  works standalone (``uvx ... gigbid-portfolio-mcp``) or before the RAG index is built.

Portfolio folder layout (one folder per persona)::

    <data_dir>/<persona>/profile.json  cv.md  reviews.json  proposals.jsonl
    <data_dir>/<persona>/case_studies/<id>.md     (YAML-ish frontmatter + body)
    <data_dir>/<persona>/repos/<id>/README.md     (+ code files)
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Protocol

_TOKEN = re.compile(r"[a-z0-9][a-z0-9+#.\-]*")
_STOP = set("a an and are as at be by for from has have in is it of on or that the this to was were will with "
            "you your we our i my me".split())
CODE_EXT = {".py", ".ts", ".tsx", ".js", ".sql", ".ipynb", ".go", ".rs", ".java", ".yaml", ".yml", ".toml"}


def tokenize(text: str) -> list[str]:
    return [t.strip(".-") for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


def default_data_dir() -> Path:
    env = os.environ.get("PORTFOLIO_DATA_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "data" / "personas"
        if cand.is_dir():
            return cand
    return Path.cwd() / "portfolio"


def _frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    head, body = text[3:end], text[end + 4:]
    try:
        import yaml  # optional

        meta = yaml.safe_load(head) or {}
    except Exception:
        meta = {}
        for line in head.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                v = v.strip()
                if v.startswith("[") and v.endswith("]"):
                    v = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
                meta[k.strip()] = v
    return meta, body.lstrip("\n")


def _s(v: Any) -> str | None:
    return None if v is None else str(v)


class Backend(Protocol):
    name: str
    persona: str

    def search(self, query: str, k: int = 5, filters: dict | None = None) -> list[dict]: ...
    def get_item(self, item_id: str) -> dict: ...
    def list_skills(self) -> list[dict]: ...
    def list_items(self, type: str | None = None) -> list[dict]: ...


class KeywordBackend:
    name = "keyword"

    def __init__(self, persona: str, data_dir: str | Path | None = None):
        self.persona = persona
        self.root = Path(data_dir or default_data_dir()) / persona
        self.items: dict[str, dict] = {}
        self._load()
        self._index()

    # ---- loading ----
    def _add(self, **it: Any) -> None:
        it.setdefault("skills", [])
        it["skills"] = [str(s) for s in (it["skills"] or [])]
        for key in ("date", "outcome", "project", "client_industry", "title"):
            it[key] = _s(it.get(key))
        self.items[it["item_id"]] = it

    def _load(self) -> None:
        r, p = self.root, self.persona
        if not r.is_dir():
            return
        prof = r / "profile.json"
        profile = json.loads(prof.read_text()) if prof.exists() else {}
        if (r / "cv.md").exists():
            self._add(item_id=f"{p}-cv", type="cv", title=profile.get("title", "CV"), text=(r / "cv.md").read_text(),
                      skills=profile.get("skills", []), source="cv.md")
        for f in sorted((r / "case_studies").glob("*.md")) if (r / "case_studies").is_dir() else []:
            meta, body = _frontmatter(f.read_text())
            self._add(item_id=str(meta.get("id", f.stem)), type="case_study", title=meta.get("title"),
                      project=meta.get("project"), skills=meta.get("skills") or [], date=meta.get("date"),
                      client_industry=meta.get("client_industry"), outcome=meta.get("outcome"), text=body,
                      source=f"case_studies/{f.name}")
        for d in sorted((r / "repos").iterdir()) if (r / "repos").is_dir() else []:
            if not d.is_dir():
                continue
            readme = d / "README.md"
            meta, body = _frontmatter(readme.read_text()) if readme.exists() else ({}, "")
            files = [{"path": str(c.relative_to(d)), "text": c.read_text(errors="ignore")[:20000]}
                     for c in sorted(d.rglob("*")) if c.is_file() and c.suffix in CODE_EXT]
            title = meta.get("title") or (body.splitlines()[0].lstrip("# ").strip() if body else d.name)
            self._add(item_id=str(meta.get("id", d.name)), type="repo", title=title, project=meta.get("project"),
                      skills=meta.get("skills") or [], date=meta.get("date"), text=body, files=files,
                      source=f"repos/{d.name}")
        rv = r / "reviews.json"
        for x in json.loads(rv.read_text()) if rv.exists() else []:
            self._add(item_id=str(x.get("id")), type="review", title=f"Review from {x.get('client', 'client')}",
                      project=x.get("project"), date=x.get("date"), outcome=None, text=x.get("text", ""),
                      skills=x.get("skills", []), rating=x.get("rating"), source="reviews.json")
        pj = r / "proposals.jsonl"
        for line in pj.read_text().splitlines() if pj.exists() else []:
            if not line.strip():
                continue
            x = json.loads(line)
            self._add(item_id=str(x.get("id")), type="proposal", title=x.get("job_title"), project=x.get("project"),
                      skills=x.get("skills", []), date=x.get("date"), client_industry=x.get("client_industry"),
                      outcome=x.get("outcome"), text=x.get("text", ""), category=x.get("category"),
                      source="proposals.jsonl")

    def _doc_text(self, it: dict) -> str:
        code = "\n".join(f["text"] for f in it.get("files", []))
        return " ".join(filter(None, [it.get("title"), it.get("project"), " ".join(it["skills"]),
                                      it.get("text"), code]))

    def _index(self) -> None:
        self.tf: dict[str, Counter] = {i: Counter(tokenize(self._doc_text(it))) for i, it in self.items.items()}
        df: Counter = Counter()
        for c in self.tf.values():
            df.update(set(c))
        n = max(len(self.tf), 1)
        self.idf = {t: math.log(1 + n / (1 + d)) for t, d in df.items()}

    # ---- API ----
    @staticmethod
    def _passes(it: dict, filters: dict | None) -> bool:
        for key, want in (filters or {}).items():
            if want in (None, [], ""):
                continue
            wants = {str(w).lower() for w in (want if isinstance(want, (list, tuple, set)) else [want])}
            val = it.get(key)
            if isinstance(val, list):
                if not {str(v).lower() for v in val} & wants:
                    return False
            elif val is None or str(val).lower() not in wants:
                return False
        return True

    @staticmethod
    def _snippet(text: str, q: set[str], width: int = 600) -> str:
        paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()] or [text]
        best = max(paras, key=lambda p: len(q & set(tokenize(p))))
        return best[:width]

    def search(self, query: str, k: int = 5, filters: dict | None = None) -> list[dict]:
        q = tokenize(query)
        qs = set(q)
        scored = []
        for iid, tf in self.tf.items():
            it = self.items[iid]
            if not self._passes(it, filters):
                continue
            length = sum(tf.values()) or 1
            s = sum(self.idf.get(t, 0) * (tf[t] * 2.2) / (tf[t] + 1.2 * (0.25 + 0.75 * length / 300)) for t in qs)
            if s > 0:
                scored.append((s, iid))
        scored.sort(reverse=True)
        out = []
        for s, iid in scored[:k]:
            it = self.items[iid]
            body = it["text"] or "\n".join(f["text"] for f in it.get("files", []))
            out.append({"chunk_id": f"{iid}#c0", "item_id": iid, "type": it["type"], "source": it.get("source"),
                        "project": it.get("project"), "date": it.get("date"), "outcome": it.get("outcome"),
                        "text": self._snippet(body, qs), "score": round(float(s), 4), "skills": it["skills"]})
        return out

    def get_item(self, item_id: str) -> dict:
        it = self.items.get(item_id)
        if it is None:
            raise KeyError(item_id)
        d = dict(it)
        d["full_text"] = "\n\n".join([it["text"]] + [f"# file: {f['path']}\n{f['text']}" for f in it.get("files", [])])
        return d

    def list_items(self, type: str | None = None) -> list[dict]:
        return [{"item_id": i, "type": it["type"], "title": it.get("title"), "project": it.get("project"),
                 "date": it.get("date"), "outcome": it.get("outcome")}
                for i, it in self.items.items() if type is None or it["type"] == type]

    def list_skills(self) -> list[dict]:
        agg: dict[str, set] = {}
        for iid, it in self.items.items():
            for s in it["skills"]:
                agg.setdefault(s.strip().lower(), set()).add(iid)
        out = [{"skill": s, "count": len(ids), "items": sorted(ids)} for s, ids in agg.items()]
        return sorted(out, key=lambda d: (-d["count"], d["skill"]))


class RagBackend:
    name = "rag"

    def __init__(self, persona: str):
        from rag.retriever import get_retriever  # lazy: only inside the GigBid repo

        self.persona = persona
        self.r = get_retriever(persona)

    def search(self, query: str, k: int = 5, filters: dict | None = None) -> list[dict]:
        return [e.model_dump() for e in self.r.search(query, k=k, filters=filters)]

    def get_item(self, item_id: str) -> dict:
        d = self.r.get_item(item_id)
        d.setdefault("item_id", item_id)
        return d

    def list_items(self, type: str | None = None) -> list[dict]:
        return self.r.list_items(type)

    def list_skills(self) -> list[dict]:
        return self.r.list_skills()


_BACKENDS: dict[tuple[str, str], Any] = {}


def get_backend(persona: str) -> Any:
    mode = os.environ.get("PORTFOLIO_BACKEND", "auto")
    key = (persona, mode)
    if key in _BACKENDS:
        return _BACKENDS[key]
    backend = None
    if mode in ("auto", "rag"):
        try:
            backend = RagBackend(persona)
        except Exception:
            if mode == "rag":
                raise
    if backend is None:
        backend = KeywordBackend(persona)
    _BACKENDS[key] = backend
    return backend


def reset_backends() -> None:
    _BACKENDS.clear()
