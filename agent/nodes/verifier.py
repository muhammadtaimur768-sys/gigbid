"""Claim verification: every experience claim in the draft must be backed by portfolio evidence (R5)."""
from __future__ import annotations

import re

from agent.handoffs import Claim
from agent.nodes.base import Deps
from agent.nodes.text_utils import coverage

CLAIM_RX = re.compile(r"\b(I|I've|I have|I built|I delivered|my|we built|years|shipped|led|reduced|increased|improved)\b|\d+%|\[[a-z]+-[a-z]+-?\d*\]", re.I)
CITE_RX = re.compile(r"\[([a-z]+-[a-z]+(?:-\d+)?)\]")


def local_verify(text: str, retriever, evidence: list[dict]) -> dict:
    """Fallback when rag.verify is unavailable: cited/lexical support from the matched evidence."""
    by_item: dict[str, str] = {}
    for e in evidence:
        by_item[e["item_id"]] = by_item.get(e["item_id"], "") + " " + e.get("snippet", "")
    paras = text.split("\n\n")
    claims, kept_paras, n = [], [], 0
    for para in paras:
        kept = []
        for s in re.split(r"(?<=[.!?])\s+", para):
            if not s.strip():
                continue
            if not CLAIM_RX.search(s):
                kept.append(s)
                continue
            n += 1
            cited = CITE_RX.findall(s)
            support = max([coverage(CITE_RX.sub("", s), by_item.get(c, "")) for c in cited] or [0.0])
            if not cited:
                support = max([coverage(s, t) for t in by_item.values()] or [0.0])
            status = "supported" if support >= 0.5 else "partly_supported" if support >= 0.3 else "unsupported"
            action = "removed" if status == "unsupported" else "kept"
            claims.append(Claim(id=f"cl{n}", text=s, status=status, evidence_ids=[c for c in cited], action=action))
            if action == "kept":
                kept.append(s)
        if kept:
            kept_paras.append(" ".join(kept))
    before = sum(c.status == "unsupported" for c in claims)
    return {"claims": claims, "unsupported_before": before, "unsupported_after": 0, "cleaned_text": "\n\n".join(kept_paras)}


def verifier(state: dict, deps: Deps) -> dict:
    draft = dict(state["draft"])
    persona = state.get("persona") or "aiml"
    retriever = deps.retriever(persona)
    try:
        from rag.verify import verify_proposal

        if not hasattr(retriever, "list_skills"):
            raise ImportError("retriever lacks list_skills")
        res = verify_proposal(draft["cover_letter"], retriever, persona)
    except ImportError:
        res = local_verify(draft["cover_letter"], retriever, state.get("evidence") or [])
    claims = [c.model_dump() if hasattr(c, "model_dump") else dict(c) for c in res.get("claims", [])]
    # attach evidence snippets so the approval payload shows the evidence behind every claim
    snip = {e["chunk_id"]: e for e in state.get("evidence") or []}
    for c in claims:
        c["evidence"] = [{"chunk_id": cid, "item_id": (snip.get(cid) or {}).get("item_id", cid.split("#")[0]),
                          "snippet": (snip.get(cid) or {}).get("snippet", "")[:300]} for cid in c.get("evidence_ids", [])]
    cleaned = res.get("cleaned_text") or draft["cover_letter"]
    draft.update({"cover_letter": cleaned, "claims": claims,
                  "unsupported_before": int(res.get("unsupported_before", 0)),
                  "unsupported_after": int(res.get("unsupported_after", 0)), "verified": True})
    return {"draft": draft}
