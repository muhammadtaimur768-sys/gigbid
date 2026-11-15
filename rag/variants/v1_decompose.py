"""V1: requirement decomposition. One retrieval per requirement, then merge (weighted RRF with the
whole-post list). Requirements come from the job's structured fields and bullet lines, no LLM."""
from __future__ import annotations

import re

NAME = "v1"
FLAGS = {"query": "decompose"}

REQ_CUES = re.compile(r"\b(need|needs|must|should|require|required|requirements?|looking for|experience (?:with|in)|"
                      r"familiar(?:ity)? with|knowledge of|proficien\w+|deliver\w*|build|implement|set up|migrate)\b", re.I)
BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.*\S)")


def extract_requirements(job: dict, max_n: int = 8) -> list[str]:
    """Skills first (exact names matter), then bullet / cue sentences from the description."""
    reqs: list[str] = []
    for s in job.get("skills_required") or job.get("skills") or []:
        reqs.append(str(s))
    desc = job.get("description") or ""
    lines = []
    for line in desc.splitlines():
        m = BULLET.match(line)
        if m:
            lines.append(m.group(1))
    if not lines:
        for sent in re.split(r"(?<=[.!?])\s+", desc):
            if REQ_CUES.search(sent) and 4 <= len(sent.split()) <= 40:
                lines.append(sent.strip())
    seen = {r.lower() for r in reqs}
    for line in lines:
        if line.lower() not in seen:
            reqs.append(line)
            seen.add(line.lower())
    return reqs[:max_n]


def job_query(job: dict) -> str:
    return f"{job.get('title', '')}\n{job.get('description', '')}".strip()
