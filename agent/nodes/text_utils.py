"""Shared deterministic text helpers for the heuristic paths of the nodes."""
from __future__ import annotations

import hashlib
import re

from agent.retrieval import tokens

DELIVERABLE_VERBS = r"(build|create|develop|design|implement|migrate|integrate|deploy|set up|automate|analy[sz]e|clean|train|fine-tune|scrape|optimi[sz]e|fix|refactor|write|dashboard|pipeline|model)"


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [p.strip(" -*•\t") for p in parts if len(p.strip()) > 3]


def job_text(job: dict) -> str:
    return f"{job.get('title', '')}\n{job.get('description', '')}"


def bullets(text: str) -> list[str]:
    return [m.strip().rstrip(".") for m in re.findall(r"^\s*[-*•]\s+(.{3,160})$", text or "", re.M)
            if not re.search(r"ignore|disregard|telegram|whatsapp", m, re.I)]


def text_hash(job: dict) -> str:
    norm = re.sub(r"\s+", " ", (job.get("title", "") + " " + job.get("description", "")).lower()).strip()
    return hashlib.sha1(norm.encode()).hexdigest()[:16]


def heuristic_requirements(job: dict, max_n: int = 8) -> list[dict]:
    """Skills listed on the job + deliverable sentences from the description."""
    reqs: list[dict] = []
    for s in job.get("skills_required") or []:
        reqs.append({"text": str(s), "kind": "skill", "must_have": True})
    for b in bullets(job.get("description", "")):
        reqs.append({"text": f"Deliver {b}", "kind": "deliverable", "must_have": True})
    for sent in ([] if bullets(job.get("description", "")) else sentences(job.get("description", ""))):
        if len(reqs) >= max_n:
            break
        if re.search(DELIVERABLE_VERBS, sent, re.I) and 20 <= len(sent) <= 220:
            if not any(tok in sent.lower() for tok in ("ignore previous", "telegram", "whatsapp")):
                reqs.append({"text": sent.rstrip("."), "kind": "deliverable", "must_have": False})
    out, seen = [], set()
    for r in reqs:
        k = r["text"].lower()
        if k not in seen:
            seen.add(k)
            out.append(r)
    return [{"id": f"r{i + 1}", **r} for i, r in enumerate(out[:max_n])]


def coverage(requirement: str, text: str, skills: list[str] | None = None) -> float:
    """Share of the requirement's content tokens present in the evidence text or skill tags."""
    req = set(tokens(requirement))
    if not req:
        return 0.0
    ev = set(tokens(text)) | {t for s in (skills or []) for t in tokens(s)}
    ev_low = (text or "").lower() + " " + " ".join(skills or []).lower()
    hit = sum(1 for t in req if t in ev or (len(t) > 3 and t in ev_low))
    return hit / len(req)


def first_sentence(text: str, max_len: int = 220) -> str:
    s = sentences(text)
    out = s[0] if s else (text or "")
    out = re.sub(r"^#+\s*", "", out).strip()
    return out[:max_len].rstrip(" ,;:") + ("" if len(out) <= max_len else "…")
