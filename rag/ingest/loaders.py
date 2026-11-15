"""Local loaders for a persona corpus: CV (PDF or Markdown), case studies, repos, reviews, proposals.

Every loader returns `Item` objects carrying the metadata later copied onto every chunk.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from rag.types import Item

CODE_EXT = {".py", ".ts", ".tsx", ".js", ".sql", ".ipynb", ".r", ".R", ".sh", ".yaml", ".yml", ".toml"}
FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)


def split_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return (meta if isinstance(meta, dict) else {}), m.group(2)


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return None


def _as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [s.strip() for s in v.split(",") if s.strip()]
    return [str(s) for s in v]


def _str(v):
    return None if v is None else str(v)


def load_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def load_cv(persona_dir: Path, persona: str, profile: dict | None = None) -> list[Item]:
    """Prefers cv.pdf (the format users upload); falls back to cv.md."""
    pdf, md = persona_dir / "cv.pdf", persona_dir / "cv.md"
    text, source = "", None
    if pdf.exists():
        try:
            text, source = load_pdf_text(pdf), str(pdf)
        except Exception:  # unreadable PDF -> markdown fallback
            text = ""
    if not text.strip() and md.exists():
        text, source = md.read_text(), str(md)
    if not text.strip():
        return []
    profile = profile or {}
    return [Item(item_id=f"{persona}-cv", persona=persona, type="cv", title=profile.get("title") or "CV",
                 skills=_as_list(profile.get("skills")), text=text, source=source)]


def load_case_study(path: Path, persona: str) -> Item:
    meta, body = split_frontmatter(path.read_text())
    return Item(
        item_id=str(meta.get("id") or path.stem), persona=persona, type="case_study",
        title=_str(meta.get("title")) or _first_heading(body), project=_str(meta.get("project")),
        skills=_as_list(meta.get("skills")), date=_str(meta.get("date")),
        client_industry=_str(meta.get("client_industry")), outcome=_str(meta.get("outcome")),
        text=body.strip(), source=str(path),
        extra={k: v for k, v in meta.items() if k not in {"id", "title", "project", "skills", "date",
                                                         "client_industry", "outcome"}},
    )


def load_repo(repo_dir: Path, persona: str) -> Item:
    readme_path = next((p for p in repo_dir.iterdir() if p.name.lower() == "readme.md"), None)
    readme = readme_path.read_text() if readme_path else ""
    meta, body = split_frontmatter(readme)
    for meta_name in ("meta.json", "repo.json", ".meta.json"):
        mp = repo_dir / meta_name
        if mp.exists():
            meta = {**json.loads(mp.read_text()), **meta}
    files = []
    for p in sorted(repo_dir.rglob("*")):
        if p.is_file() and p.suffix in CODE_EXT and p.name not in {"meta.json", "repo.json", ".meta.json"}:
            files.append({"path": str(p.relative_to(repo_dir)), "text": p.read_text(errors="ignore")})
    return Item(
        item_id=str(meta.get("id") or repo_dir.name), persona=persona, type="repo",
        title=_str(meta.get("title")) or _first_heading(body) or repo_dir.name, project=_str(meta.get("project")),
        skills=_as_list(meta.get("skills")), date=_str(meta.get("date")),
        client_industry=_str(meta.get("client_industry")), outcome=_str(meta.get("outcome")),
        text=body.strip(), source=str(readme_path or repo_dir), files=files,
    )


def load_reviews(path: Path, persona: str) -> list[Item]:
    if not path.exists():
        return []
    out = []
    for r in json.loads(path.read_text()):
        out.append(Item(
            item_id=str(r["id"]), persona=persona, type="review", title=f"Review from {r.get('client', 'client')}",
            project=_str(r.get("project")), skills=_as_list(r.get("skills")), date=_str(r.get("date")),
            client_industry=_str(r.get("client_industry")), text=str(r.get("text", "")),
            source=str(path), extra={"rating": r.get("rating"), "client": r.get("client")},
        ))
    return out


def load_proposals(path: Path, persona: str) -> list[Item]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        p = json.loads(line)
        out.append(Item(
            item_id=str(p["id"]), persona=persona, type="proposal", title=_str(p.get("job_title")),
            project=_str(p.get("project")), skills=_as_list(p.get("skills")), date=_str(p.get("date")),
            client_industry=_str(p.get("client_industry")), outcome=_str(p.get("outcome")),
            text=str(p.get("text", "")), source=str(path), extra={"category": p.get("category")},
        ))
    return out


def load_persona(persona_dir: Path, persona: str) -> list[Item]:
    persona_dir = Path(persona_dir)
    profile = {}
    if (persona_dir / "profile.json").exists():
        profile = json.loads((persona_dir / "profile.json").read_text())
    items: list[Item] = []
    items += load_cv(persona_dir, persona, profile)
    cs_dir = persona_dir / "case_studies"
    if cs_dir.exists():
        items += [load_case_study(p, persona) for p in sorted(cs_dir.glob("*.md"))]
    repo_dir = persona_dir / "repos"
    if repo_dir.exists():
        items += [load_repo(p, persona) for p in sorted(repo_dir.iterdir()) if p.is_dir()]
    items += load_reviews(persona_dir / "reviews.json", persona)
    items += load_proposals(persona_dir / "proposals.jsonl", persona)
    return _overlay_manifest(items, persona_dir / "manifest.json")


def _overlay_manifest(items: list[Item], path: Path) -> list[Item]:
    """manifest.json (written by the corpus generator) fills metadata the files do not carry,
    e.g. project/skills/date/client industry for repos."""
    if not path.exists():
        return items
    meta = {str(m["id"]): m for m in json.loads(path.read_text())}
    for it in items:
        m = meta.get(it.item_id)
        if not m:
            continue
        for field in ("title", "project", "date", "client_industry", "outcome"):
            if getattr(it, field) in (None, "") and m.get(field) not in (None, ""):
                setattr(it, field, str(m[field]))
        if not it.skills and m.get("skills"):
            it.skills = [str(x) for x in m["skills"]]
    return items


def item_from_upload(persona: str, item_id: str, type: str, text: str, **meta) -> Item:
    """Build an Item from text the user adds in the UI (used by Retriever.add_document)."""
    if type == "case_study":
        fm, body = split_frontmatter(text)
        meta = {**fm, **meta}
        text = body
    return Item(item_id=item_id, persona=persona, type=type, text=text,
                title=_str(meta.get("title")) or _first_heading(text), project=_str(meta.get("project")),
                skills=_as_list(meta.get("skills")), date=_str(meta.get("date")),
                client_industry=_str(meta.get("client_industry")), outcome=_str(meta.get("outcome")),
                source=_str(meta.get("source")) or "upload", files=meta.get("files") or [])
