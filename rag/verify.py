"""Claim verification (B3): split a proposal into sentences, detect factual claims about the
freelancer, check each against retrieved portfolio evidence, remove unsupported ones.

LLM-free by default: a claim is graded from the cross-encoder logit between claim and its best
evidence chunk, the share of the claim's content words found in that evidence, and whether every
number in the claim also appears in the evidence. Thresholds live in rag/config.yaml `verify`.
`mode="llm"` asks the `verifier` node (agent/prompts/verifier.md) and falls back to the heuristic.
"""
from __future__ import annotations

import re

from agent.handoffs import Claim
from rag.config import load_config
from rag.index.embed import rerank_scores
from rag.index.store import tokenize

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(•-])")
NUM_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:%|k\b|x\b|\+)?", re.I)
FIRST_PERSON = re.compile(r"\b(i|i've|i'm|my|we|our|me)\b", re.I)
GENERIC = set("""experience project projects client clients work worked years year built build team using used
help helped data system systems solution solutions previously recently including""".split())


def split_sentences(text: str) -> list[tuple[int, str]]:
    """[(paragraph_index, sentence)] keeping paragraph boundaries for reconstruction."""
    out = []
    for pi, para in enumerate(re.split(r"\n\s*\n", text.strip())):
        for line in para.splitlines():
            line = line.strip()
            if not line:
                continue
            for s in SENT_SPLIT.split(line):
                if s.strip():
                    out.append((pi, s.strip()))
    return out


def is_claim(sentence: str, skills: set[str], vcfg: dict) -> bool:
    s = sentence.lower().strip()
    if len(s.split()) < vcfg["min_claim_words"] or s.endswith("?"):
        return False
    head = " " + s[:40]
    if any(f" {m}" in head for m in vcfg["non_claim_markers"]):
        return False
    if any(m in s for m in vcfg["claim_markers"]):
        return True
    if not FIRST_PERSON.search(s):
        return False
    if NUM_RE.search(s):
        return True
    toks = set(tokenize(s))
    return any(sk in s if " " in sk else sk in toks for sk in skills)


def _numbers(text: str) -> set[str]:
    return {re.sub(r"\s+", "", m.group(0)).rstrip("+").lower() for m in NUM_RE.finditer(text)}


def _grade_heuristic(claim: str, evidence: list, vcfg: dict) -> dict:
    if not evidence:
        return {"status": "unsupported", "rerank": None, "overlap": 0.0, "numbers_ok": False, "chunk_ids": []}
    scores = rerank_scores(claim, [e.text for e in evidence])
    best_i = max(range(len(scores)), key=lambda i: scores[i])
    best = scores[best_i]
    ctoks = {t for t in tokenize(claim) if t not in GENERIC and len(t) > 2}
    etoks = set(tokenize(" ".join(e.text for e in evidence)))
    overlap = len(ctoks & etoks) / len(ctoks) if ctoks else 0.0
    nums = _numbers(claim)
    ev_text = " ".join(e.text for e in evidence).lower().replace(" ", "")
    numbers_ok = all(n in ev_text for n in nums)
    if best >= vcfg["supported_rerank"] and overlap >= vcfg["supported_overlap"] and numbers_ok:
        status = "supported"
    elif best >= vcfg["partly_rerank"] or overlap >= vcfg["partly_overlap"]:
        status = "partly_supported"
    else:
        status = "unsupported"
    if not numbers_ok and status == "supported":
        status = "partly_supported"
    supporting = [evidence[i].chunk_id for i in sorted(range(len(scores)), key=lambda i: -scores[i])
                  if scores[i] >= vcfg["partly_rerank"]][:3]
    return {"status": status, "rerank": round(best, 3), "overlap": round(overlap, 3), "numbers_ok": numbers_ok,
            "chunk_ids": supporting or [evidence[best_i].chunk_id]}


def _grade_llm(claim: str, evidence: list, vcfg: dict) -> dict | None:
    try:
        from agent.llm import call_llm
    except Exception:
        return None
    ev = "\n---\n".join(f"[{e.chunk_id}] {e.text[:800]}" for e in evidence[:3])
    res = call_llm(vcfg["llm_node"], vcfg["llm_prompt"], {"claim": claim, "evidence": ev}, json_mode=True)
    if not res.ok or not isinstance(res.data, dict):
        return None
    status = res.data.get("status")
    if status not in ("supported", "partly_supported", "unsupported"):
        return None
    return {"status": status, "chunk_ids": [e.chunk_id for e in evidence[:3]], "judge": "llm"}


def verify_proposal(text: str, retriever=None, persona: str | None = None, mode: str | None = None,
                    _recheck: bool = True) -> dict:
    """Returns {claims: [Claim], unsupported_before, unsupported_after, cleaned_text, details, n_claims}."""
    vcfg = load_config()["verify"]
    mode = mode or vcfg["mode"]
    if retriever is None:
        from rag.retriever import get_retriever

        retriever = get_retriever(persona or "aiml")
    skills = {d["skill"] for d in retriever.list_skills()}
    sents = split_sentences(text)
    claims, details, removed = [], [], set()
    for idx, (_, s) in enumerate(sents):
        if not is_claim(s, skills, vcfg):
            continue
        evidence = retriever.search(s, k=vcfg["evidence_k"], filters={"type": vcfg["evidence_types"]})
        g = _grade_llm(s, evidence, vcfg) if mode == "llm" else None
        g = g or _grade_heuristic(s, evidence, vcfg)
        action = "removed" if g["status"] == "unsupported" else "kept"
        if action == "removed":
            removed.add(idx)
        cid = f"cl{len(claims) + 1}"
        claims.append(Claim(id=cid, text=s, status=g["status"], evidence_ids=g["chunk_ids"], action=action))
        details.append({"claim_id": cid, **{k: v for k, v in g.items() if k != "chunk_ids"}})
    paras: dict[int, list[str]] = {}
    for idx, (pi, s) in enumerate(sents):
        if idx not in removed:
            paras.setdefault(pi, []).append(s)
    cleaned = "\n\n".join(" ".join(v) for _, v in sorted(paras.items()))
    before = sum(c.status == "unsupported" for c in claims)
    after = before
    if _recheck:
        after = verify_proposal(cleaned, retriever, persona, mode, _recheck=False)["unsupported_before"] if removed else before
    return {"claims": claims, "unsupported_before": before, "unsupported_after": after, "cleaned_text": cleaned,
            "n_claims": len(claims), "details": details}
