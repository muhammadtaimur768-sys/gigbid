"""V4: outcome-aware ranking. Past proposals that won or got replies are boosted and ignored ones
demoted; other evidence is boosted by the success rate of past proposals that used the same skills
(past proposals carry skills and an outcome but no project link)."""
from __future__ import annotations

from collections import Counter

from rag.index.store import VectorStore

NAME = "v4"
FLAGS = {"outcome": True}


def skill_success(store: VectorStore) -> dict[str, float]:
    """(won + replied) / total for proposals tagged with each skill, centred on the overall rate."""
    total, good, seen = Counter(), Counter(), set()
    n_all = n_good = 0
    for c in store.chunks:
        if c.type != "proposal" or c.item_id in seen:
            continue
        seen.add(c.item_id)
        ok = c.outcome in ("won", "replied")
        n_all += 1
        n_good += ok
        for s in c.skills:
            s = s.lower()
            total[s] += 1
            good[s] += ok
    if not n_all:
        return {}
    base = n_good / n_all
    return {s: good[s] / total[s] - base for s in total if total[s] >= 3}


def boost(scored_items: list[dict], store: VectorStore, cfg: dict, success: dict[str, float]) -> list[dict]:
    ob = cfg["retrieval"]["outcome_boost"]
    pb = cfg["retrieval"]["outcome_project_boost"]
    for it in scored_items:
        c = store.chunks[it["row"]]
        mult = 1.0
        if c.type == "proposal" and c.outcome in ob:
            mult += ob[c.outcome]
        elif c.skills and success:
            rates = [success[s.lower()] for s in c.skills if s.lower() in success]
            if rates:
                mult += pb * sum(rates) / len(rates)
        it["score"] *= mult
    return sorted(scored_items, key=lambda d: -d["score"])
