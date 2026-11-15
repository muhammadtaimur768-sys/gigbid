"""Fit Matcher: requirement → portfolio evidence (via the RAG retriever) → FitReport."""
from __future__ import annotations

from agent.handoffs import EvidenceRef, FitReport, RequirementMatch
from agent.llm import call_llm, is_heuristic
from agent.nodes.base import Deps, usage_from
from agent.nodes.text_utils import coverage, heuristic_requirements
from agent.retrieval import load_profile, tokens
from agent.settings import cfg


def _get(ev, k, default=None):
    v = ev.get(k, default) if isinstance(ev, dict) else getattr(ev, k, default)
    return default if v is None else v


def skill_overlap(job: dict, profile: dict) -> float:
    js = [s.lower() for s in job.get("skills_required") or []]
    if not js:
        return 0.5
    ps = {s.lower() for s in profile.get("skills") or []}
    ptoks = {t for s in ps for t in tokens(s)}
    hit = sum(1 for s in js if s in ps or (set(tokens(s)) and set(tokens(s)) <= ptoks))
    return hit / len(js)


def matcher(state: dict, deps: Deps) -> dict:
    job = state["job"]
    persona = state.get("persona") or "aiml"
    profile = load_profile(persona)
    k = int(cfg("rag", "k_per_requirement", default=3))
    strong_t = float(cfg("rag", "strong_coverage", default=0.75))
    partial_t = float(cfg("rag", "partial_coverage", default=0.4))
    reqs = heuristic_requirements(job, int(cfg("rag", "max_requirements", default=6)))
    retriever = deps.retriever(persona)
    query = f"{job.get('title', '')}. {job.get('description', '')[:600]}"
    proof = {"type": list(cfg("matcher", "proof_types", default=["case_study", "repo", "code", "review", "cv"]))}
    pool = list(retriever.search(query, k=max(8, k * 3), filters=proof, requirements=[r["text"] for r in reqs]) or [])
    matches, evidence, results = [], [], []
    for r in reqs:
        cands = [e for e in pool if _get(e, 'type', '') in proof['type'] or _get(e, 'type', '') not in ('proposal',)]
        if r["kind"] == "skill":
            try:
                cands += list(retriever.search(r["text"], k=k, filters=proof) or [])
            except Exception:
                pass
        scored = []
        for ev in cands:
            cov = coverage(r["text"], _get(ev, "text", ""), _get(ev, "skills", []) or [])
            scored.append((cov, float(_get(ev, "score", 0.0) or 0.0), ev))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        best, seen = [], set()
        for cov, sc, ev in scored:
            if cov <= 0 or _get(ev, "chunk_id") in seen:
                continue
            seen.add(_get(ev, "chunk_id"))
            best.append((cov, sc, ev))
            if len(best) >= k:
                break
        top = best[0][0] if best else 0.0
        strength = "strong" if top >= strong_t else "partial" if top >= partial_t else "none"
        if best and strength != "strong" and not is_heuristic("matcher") and cfg("matcher", "llm_judge", default=False):
            res = call_llm("matcher", "matcher", {"requirement": r["text"],
                                                  "evidence": "\n---\n".join(_get(e, "text", "")[:500] for _, _, e in best)},
                           json_mode=True)
            results.append(res)
            if res.ok and isinstance(res.data, dict) and res.data.get("strength") in ("strong", "partial", "none"):
                strength = res.data["strength"]
        refs = [EvidenceRef(item_id=_get(e, "item_id"), chunk_id=_get(e, "chunk_id"), type=str(_get(e, "type", "")),
                            snippet=str(_get(e, "text", ""))[:500], score=round(cov, 3), outcome=_get(e, "outcome"))
                for cov, sc, e in best]
        matches.append(RequirementMatch(requirement_id=r["id"], requirement=r["text"], evidence=refs, strength=strength))
        evidence += [x.model_dump() for x in refs]
    weights = [1.0 if r["must_have"] else 0.6 for r in reqs]
    val = {"strong": 1.0, "partial": 0.5, "none": 0.0}
    req_cov = (sum(w * val[m.strength] for w, m in zip(weights, matches)) / sum(weights)) if matches else 0.0
    so = skill_overlap(job, profile)
    w = float(cfg("matcher", "skill_overlap_weight", default=0.5))
    fit = round((1 - w) * req_cov + w * so, 3)
    reasons = [f"{m.requirement}: {m.strength} ({', '.join(e.item_id for e in m.evidence[:2]) or 'no evidence'})"
               for m in matches if m.strength != "none"]
    gaps = [m.requirement for m in matches if m.strength == "none"]
    report = FitReport(job_id=job["id"], fit_score=max(0.0, min(1.0, fit)), matches=matches,
                       reasons=reasons[:6] + [f"profile skill overlap {so:.2f}"], gaps=gaps,
                       skill_overlap=round(so, 3))
    return {"fit": report.model_dump(), "evidence": evidence, "usage": usage_from(*results)}
