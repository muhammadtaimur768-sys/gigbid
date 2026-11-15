"""Compliance Guard: policy-pack rules on outbound text → ComplianceVerdict (block → needs attention)."""
from __future__ import annotations

from agent.handoffs import ComplianceVerdict
from agent.llm import call_llm, is_heuristic
from agent.nodes.base import Deps, usage_from
from agent.policy import check_outbound, outbound_rules, wrap_untrusted


def check_text(job_id: str, text: str, kind: str = "proposal", unsupported_after: int = 0) -> tuple[dict, object]:
    r = check_outbound(text, kind)
    violations, reasons = list(r["violations"]), list(r["reasons"])
    llm_rules = [x for x in outbound_rules() if x.get("kind") == "llm"]
    res = None
    for rule in llm_rules:  # LLM-kind rules: deterministic proxy first (verifier output), LLM when available
        if "fabricat" in rule.get("id", "") and unsupported_after > 0:
            violations.append(rule["id"])
            reasons.append(f"{rule['id']}: {unsupported_after} unsupported claims remain")
    if llm_rules and not is_heuristic("compliance"):
        res = call_llm("compliance", "compliance", {
            "rules": "\n".join(f"- {x['id']}: {x.get('description', '')}" for x in llm_rules),
            "draft": wrap_untrusted(r["cleaned_text"], "draft")}, json_mode=True)
        # the model may only flag rule ids that exist; LLM verdicts on fabrication are advisory (verifier is authoritative)
        if res.ok and isinstance(res.data, dict):
            ids = {x["id"] for x in llm_rules}
            for v in res.data.get("violations") or []:
                if v in ids and v not in violations and "fabricat" not in v:
                    violations.append(v)
                    reasons.append(f"{v}: {str(res.data.get('reason', ''))[:200]}")
    verdict = ComplianceVerdict(job_id=job_id, allowed=not violations, violations=violations,
                                redactions=r["redactions"], cleaned_text=r["cleaned_text"],
                                reason="; ".join(reasons) or ("redacted: " + ", ".join(r["redactions"]) if r["redactions"] else "ok"))
    return verdict.model_dump(), res


def compliance(state: dict, deps: Deps) -> dict:
    draft = dict(state["draft"])
    v, res = check_text(state["job"]["id"], draft.get("cover_letter", ""), "proposal", int(draft.get("unsupported_after", 0)))
    answers = []
    for a in draft.get("screening_answers") or []:
        va, _ = check_text(state["job"]["id"], a.get("answer", ""), "proposal")
        if not va["allowed"]:
            v["allowed"] = False
            v["violations"] = list(dict.fromkeys(v["violations"] + va["violations"]))
            v["reason"] += "; screening answer: " + va["reason"]
        answers.append({**a, "answer": va["cleaned_text"]})
    draft["cover_letter"] = v["cleaned_text"]
    draft["screening_answers"] = answers
    out = {"compliance": v, "draft": draft, "usage": usage_from(res)}
    if not v["allowed"]:
        out["status"] = "needs_attention"
        out["status_reason"] = f"compliance blocked: {v['reason']}"[:400]
    return out
