"""Chunkers. Every chunk carries the full item metadata (persona, type, project, skills, date,
client industry, outcome) so filters and outcome-aware ranking work at chunk level."""
from __future__ import annotations

import re

from rag.types import Chunk, Item

CODE_BOUNDARY = re.compile(
    r"^(?=(?:async\s+def|def|class|export\s+|function|const\s+\w+\s*=|interface|type\s+\w+\s*=|"
    r"create\s+|with\s+|select\s+|insert\s+|--\s|@\w))",
    re.I | re.M,
)
IMPORT_RE = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+)|import .* from ['\"]([^'\"]+)['\"]|"
                       r"require\(['\"]([^'\"]+)['\"]\))", re.M)
DEF_RE = re.compile(r"^\s*(?:async\s+)?(?:def|class|function|export\s+(?:async\s+)?function|interface)\s+(\w+)", re.M)


def _meta(item: Item, type_: str | None = None, source: str | None = None) -> dict:
    return dict(item_id=item.item_id, persona=item.persona, type=type_ or item.type, project=item.project,
                skills=list(item.skills), date=item.date, client_industry=item.client_industry,
                outcome=item.outcome, source=source or item.source, title=item.title, parent_id=item.item_id)


def _sources(item: Item) -> list[tuple[str, str, str]]:
    """(type, source, text) for each text unit of an item."""
    out = []
    if item.text.strip():
        out.append((item.type, item.source or "", item.text))
    for f in item.files:
        out.append(("code", f"{item.source or item.item_id}::{f['path']}", f"# file: {f['path']}\n{f['text']}"))
    return out


def fixed_chunks(item: Item, size: int = 700, overlap: int = 100) -> list[Chunk]:
    chunks, n = [], 0
    step = max(1, size - overlap)
    for type_, src, text in _sources(item):
        for start in range(0, max(1, len(text)), step):
            piece = text[start:start + size]
            if not piece.strip():
                continue
            chunks.append(Chunk(chunk_id=f"{item.item_id}#c{n}", text=piece, **_meta(item, type_, src)))
            n += 1
            if start + size >= len(text):
                break
    return chunks


def _pack(parts: list[str], max_chars: int, min_chars: int) -> list[str]:
    out, buf = [], ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if buf and len(buf) + len(p) + 2 > max_chars and len(buf) >= min_chars:
            out.append(buf)
            buf = p
        else:
            buf = f"{buf}\n\n{p}" if buf else p
        while len(buf) > max_chars * 1.5:  # very long paragraph: hard split
            out.append(buf[:max_chars])
            buf = buf[max_chars:]
    if buf.strip():
        if out and len(buf) < min_chars:
            out[-1] = f"{out[-1]}\n\n{buf}"
        else:
            out.append(buf)
    return out


def split_prose(text: str, max_chars: int = 900, min_chars: int = 120) -> list[str]:
    sections = re.split(r"\n(?=#{1,6}\s)", text)
    parts = []
    for s in sections:
        parts += re.split(r"\n\s*\n", s) if len(s) > max_chars else [s]
    return _pack(parts, max_chars, min_chars)


def split_code(text: str, max_chars: int = 900, min_chars: int = 120) -> list[str]:
    parts = CODE_BOUNDARY.split(text)
    return _pack(parts, max_chars, min_chars)


def structured_chunks(item: Item, max_chars: int = 900, min_chars: int = 120) -> list[Chunk]:
    chunks, n = [], 0
    for type_, src, text in _sources(item):
        pieces = split_code(text, max_chars, min_chars) if type_ == "code" else split_prose(text, max_chars, min_chars)
        for piece in pieces:
            chunks.append(Chunk(chunk_id=f"{item.item_id}#c{n}", text=piece, **_meta(item, type_, src)))
            n += 1
    return chunks


def code_digest(item: Item) -> str:
    """Libraries imported and symbols defined: what the code proves even when the README is silent."""
    libs, defs = [], []
    for f in item.files:
        for m in IMPORT_RE.finditer(f["text"]):
            lib = next(g for g in m.groups() if g)
            libs.append(lib.split(".")[0])
        defs += DEF_RE.findall(f["text"])
    libs = list(dict.fromkeys(libs))
    defs = list(dict.fromkeys(defs))[:30]
    paths = [f["path"] for f in item.files]
    return (f"Code for {item.title or item.item_id}. Files: {', '.join(paths)}. "
            f"Libraries used: {', '.join(libs) or 'none'}. Defines: {', '.join(defs) or 'none'}.")


def summary_text(item: Item) -> str:
    head = re.sub(r"\s+", " ", item.text)[:400]
    bits = [item.title or "", f"Project: {item.project}" if item.project else "",
            f"Skills: {', '.join(item.skills)}" if item.skills else "",
            f"Client industry: {item.client_industry}" if item.client_industry else "", head]
    return ". ".join(b for b in bits if b)


def multivector_chunks(item: Item, max_chars: int = 900, min_chars: int = 120) -> list[Chunk]:
    """V5: structured chunks + an item summary vector + (repos) a code digest vector."""
    chunks = structured_chunks(item, max_chars, min_chars)
    n = len(chunks)
    chunks.append(Chunk(chunk_id=f"{item.item_id}#c{n}", text=summary_text(item), **_meta(item, "summary")))
    if item.files:
        chunks.append(Chunk(chunk_id=f"{item.item_id}#c{n + 1}", text=code_digest(item),
                            **_meta(item, "code_digest")))
    return chunks


def chunk_item(item: Item, chunking: str, cfg: dict) -> list[Chunk]:
    c = cfg["chunking"]
    if chunking == "fixed":
        return fixed_chunks(item, c["fixed"]["size_chars"], c["fixed"]["overlap_chars"])
    if chunking == "structured":
        return structured_chunks(item, c["structured"]["max_chars"], c["structured"]["min_chars"])
    if chunking == "multivector":
        return multivector_chunks(item, c["structured"]["max_chars"], c["structured"]["min_chars"])
    raise ValueError(f"unknown chunking {chunking}")
