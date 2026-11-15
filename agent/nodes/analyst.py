"""Job Analyst: job post → JobSpec (requirements, deliverables, hidden needs)."""
from __future__ import annotations

import re

from agent.handoffs import JobSpec, Requirement
from agent.llm import call_llm, is_heuristic
from agent.nodes.base import Deps, usage_from
from agent.nodes.text_utils import DELIVERABLE_VERBS, bullets, heuristic_requirements, sentences
from agent.policy import wrap_untrusted
from agent.settings import cfg

HIDDEN_NEED_CUES = [
    (r"\b(asap|urgent|quickly|this week|tight deadline)\b", "fast turnaround"),
    (r"\b(maintain|hand ?over|our team|documentation|document)\b", "clear documentation and handover"),
    (r"\b(scale|scalable|production|reliab)", "production reliability"),
    (r"\b(non-technical|explain|stakeholders)\b", "communication with non-technical stakeholders"),
    (r"\b(long[- ]term|ongoing|future work)\b", "long-term availability"),
]


def analyst(state: dict, deps: Deps) -> dict:
    job = state["job"]
    max_n = int(cfg("rag", "max_requirements", default=6))
    reqs = heuristic_requirements(job, max_n)
    deliverables = bullets(job.get("description", "")) or [
        s.rstrip(".") for s in sentences(job.get("description", "")) if re.search(DELIVERABLE_VERBS, s, re.I)][:4]
    text = job.get("description", "")
    hidden = [need for rx, need in HIDDEN_NEED_CUES if re.search(rx, text, re.I)]
    timeline = job.get("duration")
    res = None
    if not is_heuristic("analyst"):
        res = call_llm("analyst", "analyst", {
            "title": job.get("title", ""), "job_text": wrap_untrusted(text[:3500], "job"),
            "screening": "; ".join(job.get("screening_questions") or []),
            "skills": ", ".join(job.get("skills_required") or []), "max_requirements": max_n}, json_mode=True)
        if res.ok and isinstance(res.data, dict):
            llm_reqs = [r for r in res.data.get("requirements") or [] if isinstance(r, dict) and r.get("text")]
            skill_reqs = [r for r in reqs if r["kind"] == "skill"]
            merged = skill_reqs + [{"text": str(r["text"])[:200],
                                    "kind": r.get("kind") if r.get("kind") in ("skill", "deliverable", "experience", "domain", "other") else "other",
                                    "must_have": bool(r.get("must_have", True))} for r in llm_reqs]
            seen, reqs = set(), []
            for r in merged:
                if r["text"].lower() not in seen:
                    seen.add(r["text"].lower())
                    reqs.append({"id": f"r{len(reqs) + 1}", "text": r["text"], "kind": r["kind"], "must_have": r["must_have"]})
            reqs = reqs[:max_n + 2]
            deliverables = [str(d)[:200] for d in res.data.get("deliverables") or deliverables][:6]
            hidden = list(dict.fromkeys(hidden + [str(h)[:120] for h in res.data.get("hidden_needs") or []]))[:5]
            timeline = res.data.get("timeline") or timeline
    spec = JobSpec(job_id=job["id"], title=job.get("title", ""), category=job.get("category", ""),
                   deliverables=deliverables, skills=list(job.get("skills_required") or []),
                   requirements=[Requirement(**r) for r in reqs], budget_type=job.get("budget_type", "fixed"),
                   budget_min=job.get("budget_min"), budget_max=job.get("budget_max"), timeline=timeline,
                   screening_questions=list(job.get("screening_questions") or []), hidden_needs=hidden)
    return {"job_spec": spec.model_dump(), "usage": usage_from(res)}
