"""Proposal Writer: JobSpec + evidence + price + style/outcome memory → ProposalDraft."""
from __future__ import annotations

import re

from agent.handoffs import ProposalDraft
from agent.llm import call_llm, is_heuristic
from agent.nodes.base import Deps, usage_from
from agent.nodes.text_utils import first_sentence
from agent.policy import wrap_untrusted
from agent.retrieval import load_profile
from agent.settings import cfg


def _store():
    try:
        from langgraph.config import get_store

        return get_store()
    except Exception:
        return None


def style_rules(user_id: str) -> list[str]:
    store = _store()
    if store is None or not user_id:
        return []
    try:
        return [it.key for it in store.search(("style", user_id), limit=50)]
    except Exception:
        return []


def outcome_hints(user_id: str, category: str) -> list[str]:
    store = _store()
    if store is None or not user_id:
        return []
    try:
        it = store.get(("outcome", user_id, category or "general"), "summary")
    except Exception:
        return []
    return list((it.value or {}).get("hints", [])) if it else []


def apply_style(text: str, rules: list[str]) -> str:
    for r in rules:
        if r.startswith("never_say:"):
            word = r.split(":", 1)[1]
            text = re.sub(rf"\s*\b{re.escape(word)}\b", "", text, flags=re.I)
        elif r == "cut_first_sentence":
            parts = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
            if len(parts) == 2 and len(parts[1]) > 200:
                text = parts[1]
    return re.sub(r"[ \t]{2,}", " ", text).strip()


OUTCOME_RX = re.compile(r"\b(built|shipped|deployed|reduced|cut|improved|delivered|automated|trained|migrated|moved|"
                        r"designed|replaced|launched|increased|raised|dropped|saved)\b", re.I)
CODE_RX = re.compile(r"[=(){};]|^\s*(def|import|from|select|class|return)\b", re.I)


def _clean_snippet(s: str, requirement: str = "") -> str:
    """Pick the evidence sentence that best covers the requirement (verbatim, so it stays verifiable)."""
    from agent.nodes.text_utils import coverage, sentences

    s = re.sub(r"^---.*?---", "", s, flags=re.S)
    s = re.sub(r"[#*`>|]", "", s)
    cands = [re.sub(r"\s+", " ", x).strip() for x in sentences(s)]
    cands = [c for c in cands if 30 <= len(c) <= 260 and not CODE_RX.search(c)]
    if not cands:
        if requirement and coverage(requirement, s) > 0:
            return f"the code in this repository uses {requirement.lower()}"
        return first_sentence(re.sub(r"\s+", " ", s).strip(), 200)
    cands.sort(key=lambda c: -(coverage(requirement, c) + (0.6 if OUTCOME_RX.search(c) else 0.0)))
    return cands[0]


def _evidence_lines(fit: dict, n: int) -> list[tuple[str, str, str]]:
    """(requirement, snippet, item_id) for the strongest matches, one item per line."""
    out, used = [], set()
    for m in sorted(fit.get("matches") or [], key=lambda m: {"strong": 0, "partial": 1, "none": 2}[m["strength"]]):
        if m["strength"] == "none":
            continue
        for ev in m.get("evidence") or []:
            if ev["item_id"] in used:
                continue
            used.add(ev["item_id"])
            out.append((m["requirement"], _clean_snippet(ev.get("snippet", ""), m["requirement"]), ev["item_id"]))
            break
        if len(out) >= n:
            break
    return out


def _item_meta(persona: str) -> dict:
    """item_id -> portfolio metadata (title, client_industry, date) from the persona manifest."""
    import json
    from pathlib import Path

    p = Path(__file__).resolve().parents[2] / "data" / "personas" / persona / "manifest.json"
    try:
        return {m["id"]: m for m in json.loads(p.read_text())}
    except Exception:
        return {}


def _evidence_by_item(fit: dict, n: int) -> list[tuple[str, list[str], str]]:
    """(item_id, [requirements it proves], best verbatim snippet) for the strongest items."""
    order, reqs, snips = [], {}, {}
    for m in sorted(fit.get("matches") or [], key=lambda m: {"strong": 0, "partial": 1, "none": 2}[m["strength"]]):
        if m["strength"] == "none":
            continue
        for ev in (m.get("evidence") or [])[:2]:
            iid = ev["item_id"]
            if iid not in reqs:
                order.append(iid)
                reqs[iid], snips[iid] = [], _clean_snippet(ev.get("snippet", ""), m["requirement"])
            if m["requirement"] not in reqs[iid]:
                reqs[iid].append(m["requirement"])
    return [(i, reqs[i], snips[i]) for i in order[:n]]


def _short_req(r: str) -> str:
    r = re.sub(r"^(experience with|deliver(ing)?|knowledge of|strong|proven)\s+(a |an |the )?", "", r.strip().rstrip("."), flags=re.I)
    return r[:1].lower() + r[1:] if r else r


def _join(xs: list[str]) -> str:
    xs = [x for x in xs if x]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1] if xs else ""


def heuristic_letter(state: dict, strategy: dict, feedback: list[str], rules: list[str]) -> tuple[str, list[dict]]:
    """Deterministic fallback writer (no LLM). Plain sentences built from portfolio metadata; the one
    outcome sentence per item is quoted verbatim from the evidence so the verifier can check it."""
    job, spec, fit, price = state["job"], state.get("job_spec") or {}, state.get("fit") or {}, state.get("price") or {}
    meta = _item_meta(state.get("persona") or "aiml")
    n_ev = int(strategy.get("evidence_items", 3))
    if "prefer_shorter" in rules:
        n_ev = max(1, n_ev - 1)
    if any("evidence" in f.lower() or "requirement" in f.lower() for f in feedback):
        n_ev += 1
    items = _evidence_by_item(fit, n_ev)
    reqs = [r["text"] for r in spec.get("requirements") or []][:3] or list(job.get("skills_required") or [])[:3]
    title = job.get("title", "this project")
    main = _short_req(reqs[0]) if reqs else "getting the core of it right"
    if strategy.get("opening") == "question":
        opening = f"Is {main} the part of \"{title}\" you are most worried about? It is usually where projects like this slip."
    else:
        opening = (f"Reading your brief for \"{title}\", the part that will make or break it is {main}. "
                   "That is work I have shipped before, and here is the closest proof.")
    body = []
    for iid, covers, snip in items:
        m = meta.get(iid, {})
        name = m.get("title") or iid
        ind = m.get("client_industry") or ""
        who = (f"for {'an' if ind[:1].lower() in 'aeiou' else 'a'} {ind} client" if ind else "for a client")
        year = f" in {str(m['date'])[:4]}" if m.get("date") else ""
        kind = "built" if m.get("type") != "repo" else "wrote"
        line = f"I {kind} {name} {who}{year}, which involved {_join([_short_req(c) for c in covers[:3]])}"
        if snip and len(snip) <= 220 and not snip.lower().startswith(("the code in", "&&")):
            line += f". {snip.rstrip('.')}"
        body.append(line + f" [{iid}].")
    if not body:
        body.append("I would start by confirming the scope and what success looks like for you before writing any code.")
    plan = ("I would start with a short call to pin down scope and what \"done\" means, ship a first working version early, "
            "and iterate with you from there.")
    if strategy.get("length") == "short":
        plan = "I would start with a short scoping call and get a first working version to you early."
    hidden = spec.get("hidden_needs") or []
    if hidden and strategy.get("length") != "short":
        plan += f" I would also make sure we cover {hidden[0].rstrip('.').lower()}."
    unit = "/hr" if price.get("budget_type") == "hourly" else " for the fixed scope"
    price_line = f"My rate for this would be ${price.get('amount', 0):g}{unit}." if price else ""
    close = "What would a successful first milestone look like for you?"
    text = "\n\n".join([opening, " ".join(body), plan, (price_line + " " + close).strip()])
    answers = []
    for q in job.get("screening_questions") or []:
        if items:
            iid = items[0][0]
            ans = f"The most relevant example is {meta.get(iid, {}).get('title', iid)} [{iid}]; happy to walk you through it on a call."
        else:
            ans = "Happy to go through this in detail on a short call."
        answers.append({"question": q, "answer": ans[:600]})
    return apply_style(text, rules), answers


def writer(state: dict, deps: Deps) -> dict:
    job = state["job"]
    opts = state.get("options") or {}
    strategies = cfg("writer", "strategies", default={}) or {}
    skey = opts.get("strategy") or cfg("writer", "default_strategy", default="A")
    strategy = strategies.get(skey, {})
    crit = (state.get("critiques") or [])
    feedback = crit[-1]["reasons"] if crit and crit[-1].get("verdict") == "revise" else []
    user_id = state.get("user_id") or ""
    rules = style_rules(user_id)
    hints = outcome_hints(user_id, job.get("category", ""))
    version = len(state.get("drafts") or []) + 1
    max_chars = int(cfg("writer", "max_chars", default=2400))
    res = None
    text, answers = heuristic_letter(state, strategy, feedback, rules)
    if not is_heuristic("writer"):
        prof = load_profile(state.get("persona") or "aiml")
        fit = state.get("fit") or {}
        ev_txt = "\n".join(f"[{e['item_id']}] ({m['requirement']}) {e.get('snippet', '')[:400]}"
                           for m in fit.get("matches") or [] for e in (m.get("evidence") or [])[:2])
        res = call_llm("writer", "writer", {
            "strategy_desc": f"{strategy.get('name')}: opening={strategy.get('opening')}, evidence items={strategy.get('evidence_items')}, length={strategy.get('length')}",
            "name": prof.get("name", ""), "title_line": prof.get("title", ""), "title": job.get("title", ""),
            "job_text": wrap_untrusted(job.get("description", "")[:3000], "job"),
            "requirements": "; ".join(r["text"] for r in (state.get("job_spec") or {}).get("requirements", [])),
            "evidence": wrap_untrusted(ev_txt[:4000], "evidence") or "(none)",
            "price": (state.get("price") or {}).get("amount"), "style_rules": ", ".join(rules) or "none",
            "outcome_hints": "; ".join(hints) or "none", "feedback": "; ".join(feedback) or "none",
            "min_chars": cfg("writer", "min_chars", default=450), "max_chars": max_chars,
            "screening": " | ".join(job.get("screening_questions") or []) or "none"}, json_mode=True)
        if res.ok and isinstance(res.data, dict) and len(str(res.data.get("cover_letter", ""))) >= 100:
            text = apply_style(str(res.data["cover_letter"]), rules)
            got = [a for a in res.data.get("screening_answers") or [] if isinstance(a, dict) and a.get("answer")]
            if got:
                answers = [{"question": str(a.get("question", ""))[:500], "answer": str(a["answer"])[:1500]} for a in got]
    if len(text) > max_chars:
        cut = text[:max_chars]
        text = cut[: cut.rfind(".") + 1] if "." in cut else cut
    if opts.get("force_weak_draft") and version == 1:
        text = "Dear Sir, I am a passionate expert and can do this job. " + text[:200]
    draft = ProposalDraft(job_id=job["id"], version=version, cover_letter=text, screening_answers=answers)
    d = draft.model_dump()
    d["strategy"] = skey
    return {"draft": d, "drafts": [d], "usage": usage_from(res)}
