"""Critic: scores the draft; sends it back to the Writer at most `critic.max_rounds` times."""
from __future__ import annotations

from agent.handoffs import Critique
from agent.llm import call_llm, is_heuristic
from agent.nodes.base import Deps, usage_from
from agent.nodes.text_utils import coverage
from agent.policy import wrap_untrusted
from agent.settings import cfg, max_proposal_chars


def auto_checks(state: dict) -> tuple[float, list[str]]:
    draft, job, spec = state["draft"], state["job"], state.get("job_spec") or {}
    text = draft.get("cover_letter", "")
    low = text.lower()
    score, reasons = 10.0, []
    if any(low.startswith(b) or b in low[:80] for b in cfg("writer", "banned_openings", default=[])):
        score -= 3
        reasons.append("Replace the generic opening with the client's actual problem.")
    must = [r for r in spec.get("requirements") or [] if r.get("must_have")]
    missed = [r["text"] for r in must if coverage(r["text"], text) < 0.5]
    if must and missed:
        score -= min(3.0, 3.0 * len(missed) / len(must))
        reasons.append("Address these must-have requirements with evidence: " + "; ".join(missed[:3]))
    if draft.get("unsupported_after", 0) > 0:
        score -= 2
        reasons.append("Remove claims that the portfolio evidence does not support.")
    lim = max_proposal_chars() or 2500
    if len(text) > lim:
        score -= 3
        reasons.append(f"Cut the letter below {lim} characters.")
    if len(text) < int(cfg("writer", "min_chars", default=450)) * 0.6:
        score -= 1.5
        reasons.append("Add one concrete piece of evidence and a plan; the letter is too thin.")
    qs = job.get("screening_questions") or []
    if qs and len(draft.get("screening_answers") or []) < len(qs):
        score -= 1.5
        reasons.append("Answer every screening question.")
    if "[" not in text:
        score -= 1
        reasons.append("Cite at least one portfolio item as evidence.")
    return max(0.0, score), reasons


def critic(state: dict, deps: Deps) -> dict:
    rnd = int(state.get("critic_round") or 0)
    opts = state.get("options") or {}
    min_score = float(opts.get("critic_min_score", cfg("critic", "min_score", default=7.0)))
    score, reasons = auto_checks(state)
    res = None
    if not is_heuristic("critic"):
        spec = state.get("job_spec") or {}
        res = call_llm("critic", "critic", {
            "requirements": "; ".join(r["text"] for r in spec.get("requirements") or []),
            "screening": " | ".join(state["job"].get("screening_questions") or []) or "none",
            "checks": "; ".join(reasons) or "all automatic checks passed",
            "draft": wrap_untrusted(state["draft"].get("cover_letter", ""), "draft")}, json_mode=True)
        if res.ok and isinstance(res.data, dict):
            try:
                llm_score = float(res.data.get("score", score))
                score = round((score + max(0.0, min(10.0, llm_score))) / 2, 2)
                reasons += [str(r)[:200] for r in res.data.get("reasons") or []][:4]
            except (TypeError, ValueError):
                pass
    verdict = "pass" if score >= min_score else "revise"
    c = Critique(job_id=state["job"]["id"], verdict=verdict, score=round(score, 2), reasons=reasons, round=rnd + 1)
    return {"critiques": [c.model_dump()], "critic_round": rnd + 1, "usage": usage_from(res)}
