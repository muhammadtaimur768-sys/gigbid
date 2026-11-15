"""Shared harness for agent evals: runs the bid graph on dev jobs offline and collects per-job records."""
from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "evals" / "results"
SECRETS = os.environ.get("GIGBID_SECRETS_FILE", str(ROOT.parent / "gigbid-build" / ".secrets"))


def setup_env(provider: str) -> None:
    os.environ["LLM_PROVIDER"] = provider
    os.environ.setdefault("TRACING_DISABLED", "1")
    os.environ.setdefault("GIGSIM_ERROR_RATE", "0")
    if provider.startswith("groq"):
        from agent.llm import load_env_file

        load_env_file(SECRETS)
        if not os.environ.get("GROQ_API_KEY"):
            raise SystemExit("GROQ_API_KEY not available")


def load_dev(personas=("aiml", "fullstack", "data")) -> list[dict]:
    rows = []
    for p in personas:
        for line in open(ROOT / "evals" / "datasets" / f"dev_{p}.jsonl"):
            r = json.loads(line)
            r["persona"] = p
            rows.append(r)
    return rows


def fixed_subset(rows: list[dict], n: int, seed: int = 7) -> list[dict]:
    """Deterministic, stratified subset (keeps the bid/skip and scam mix)."""
    import random

    rng = random.Random(seed)
    by = {}
    for r in rows:
        by.setdefault((r["persona"], r["gold"]["action"], r["gold"].get("kind")), []).append(r)
    for v in by.values():
        rng.shuffle(v)
    out, keys = [], sorted(by)
    i = 0
    while len(out) < n and any(by.values()):
        k = keys[i % len(keys)]
        if by[k]:
            out.append(by[k].pop())
        i += 1
    return out


_stats_cache: dict = {}
_client_cache: dict = {}


def market_stats() -> dict:
    """Market stats per category and client histories from GigSim (in-process TestClient), cached."""
    if _stats_cache:
        return _stats_cache
    from fastapi.testclient import TestClient

    from gigsim import app as gs

    rows = load_dev()
    cats = {r["job"]["category"] for r in rows}
    hdr = {"Authorization": "Bearer gs-aiml-token"}
    with TestClient(gs.app) as c:
        for cat in cats:
            r = c.get("/market/stats", params={"category": cat}, headers=hdr)
            if r.status_code == 200:
                _stats_cache[cat] = r.json()
        for cid in sorted({r["job"]["client_id"] for r in rows}):
            r = c.get(f"/clients/{cid}/history", headers=hdr)
            if r.status_code == 200:
                _client_cache[cid] = r.json()
            if hasattr(gs, "reset_rate_limits"):
                gs.reset_rate_limits()
    return _stats_cache


def make_port(rows: list[dict]):
    from agent.marketplace_port import InMemoryMarketplace

    stats = market_stats()
    return InMemoryMarketplace(jobs=[r["job"] for r in rows], stats=stats, clients=dict(_client_cache), balance=10_000)


def run_graph_on(rows: list[dict], options: dict | None = None, *, label: str = "", progress: bool = True) -> list[dict]:
    """Invoke the bid graph per job until it ends or waits for approval; one record per job."""
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.store.memory import InMemoryStore

    from agent.graphs.bid_graph import build_bid_graph, get_interrupt, new_run_input, run_config

    port = make_port(rows)
    graph = build_bid_graph(checkpointer=InMemorySaver(), store=InMemoryStore(), marketplace=port)
    recs = []
    for i, r in enumerate(rows):
        job = r["job"]
        inp = new_run_input(job=job, persona=r["persona"], user_id=f"eval-{r['persona']}", options=dict(options or {}),
                            thread_id=f"eval:{label}:{job['id']}")
        cfg = run_config(inp["thread_id"])
        t0 = time.perf_counter()
        try:
            out = graph.invoke(inp, cfg)
            err = None
        except Exception as exc:
            out, err = {}, f"{type(exc).__name__}: {exc}"[:300]
        lat = time.perf_counter() - t0
        payload = get_interrupt(graph, cfg) if not err else None
        draft = (payload or {}).get("draft") or {}
        rec = {
            "job_id": job["id"], "persona": r["persona"], "gold": r["gold"],
            "action": (out.get("decision") or {}).get("action", "error"),
            "status": out.get("status"), "is_scam_pred": bool((out.get("risk") or {}).get("is_scam")),
            "injection_pred": bool((out.get("risk") or {}).get("injection_detected")),
            "fit_score": (out.get("fit") or {}).get("fit_score"),
            "evidence_items": sorted({e["item_id"] for m in (out.get("fit") or {}).get("matches", []) for e in m.get("evidence", [])}),
            "price": (out.get("price") or {}).get("amount"),
            "cover_letter": draft.get("cover_letter"), "screening_answers": draft.get("screening_answers"),
            "unsupported_before": (payload or {}).get("unsupported_before"),
            "unsupported_after": (payload or {}).get("unsupported_after"),
            "n_claims": len((payload or {}).get("claims") or []),
            "critic_rounds": len(out.get("critiques") or []),
            "compliance": (out.get("compliance") or {}),
            "tokens": int((out.get("usage") or {}).get("tokens", 0)),
            "llm_calls": int((out.get("usage") or {}).get("llm_calls", 0)),
            "cost_usd": float((out.get("usage") or {}).get("cost_usd", 0.0)),
            "latency_s": round(lat, 3), "error": err, "status_reason": out.get("status_reason"),
        }
        recs.append(rec)
        if progress and (i + 1) % 25 == 0:
            print(f"[{label}] {i + 1}/{len(rows)}", flush=True)
    return recs


def pct(xs: list[float], q: float) -> float | None:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 4)


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4), "tp": tp, "fp": fp, "fn": fn}


def summarize(recs: list[dict]) -> dict:
    ok = [r for r in recs if not r["error"]]
    bid_tp = sum(1 for r in ok if r["action"] == "bid" and r["gold"]["action"] == "bid")
    bid_fp = sum(1 for r in ok if r["action"] == "bid" and r["gold"]["action"] != "bid")
    bid_fn = sum(1 for r in ok if r["action"] != "bid" and r["gold"]["action"] == "bid")
    skip_tp = sum(1 for r in ok if r["action"] != "bid" and r["gold"]["action"] == "skip")
    skip_fp = sum(1 for r in ok if r["action"] != "bid" and r["gold"]["action"] != "skip")
    skip_fn = sum(1 for r in ok if r["action"] == "bid" and r["gold"]["action"] == "skip")
    sc_tp = sum(1 for r in ok if r["is_scam_pred"] and r["gold"]["is_scam"])
    sc_fp = sum(1 for r in ok if r["is_scam_pred"] and not r["gold"]["is_scam"])
    sc_fn = sum(1 for r in ok if not r["is_scam_pred"] and r["gold"]["is_scam"])
    inj_tp = sum(1 for r in ok if r["injection_pred"] and r["gold"]["has_injection"])
    inj_fp = sum(1 for r in ok if r["injection_pred"] and not r["gold"]["has_injection"])
    inj_fn = sum(1 for r in ok if not r["injection_pred"] and r["gold"]["has_injection"])
    priced = [r for r in ok if r["action"] == "bid" and r["price"] is not None and r["gold"].get("fair_price_band")]
    in_band = sum(1 for r in priced if r["gold"]["fair_price_band"][0] <= r["price"] <= r["gold"]["fair_price_band"][1])
    props = [r for r in ok if r["cover_letter"]]
    ev = [r for r in ok if r["action"] == "bid" and r["gold"].get("evidence_ids")]
    ev_recall = [len(set(r["evidence_items"]) & set(r["gold"]["evidence_ids"])) / len(set(r["gold"]["evidence_ids"])) for r in ev]
    per_skip = {}
    for r in ok:
        if r["gold"]["action"] == "skip":
            k = r["gold"].get("skip_reason") or "other"
            d = per_skip.setdefault(k, {"n": 0, "skipped": 0})
            d["n"] += 1
            d["skipped"] += int(r["action"] != "bid")
    return {
        "n": len(recs), "n_errors": len(recs) - len(ok),
        "accuracy_bid_vs_not": round(sum(1 for r in ok if (r["action"] == "bid") == (r["gold"]["action"] == "bid")) / max(1, len(ok)), 4),
        "bid": prf(bid_tp, bid_fp, bid_fn), "skip": prf(skip_tp, skip_fp, skip_fn),
        "macro_f1_bid_skip": round((prf(bid_tp, bid_fp, bid_fn)["f1"] + prf(skip_tp, skip_fp, skip_fn)["f1"]) / 2, 4),
        "watch_count": sum(1 for r in ok if r["action"] == "watch"),
        "skip_recall_by_reason": per_skip,
        "scam": prf(sc_tp, sc_fp, sc_fn), "injection": prf(inj_tp, inj_fp, inj_fn),
        "price_in_band": {"n": len(priced), "in_band": in_band, "rate": round(in_band / len(priced), 4) if priced else None},
        "evidence_recall_mean": round(statistics.mean(ev_recall), 4) if ev_recall else None,
        "proposals": len(props),
        "unsupported_claims_per_proposal_before": round(statistics.mean([r["unsupported_before"] or 0 for r in props]), 4) if props else None,
        "unsupported_claims_per_proposal_after": round(statistics.mean([r["unsupported_after"] or 0 for r in props]), 4) if props else None,
        "claims_per_proposal": round(statistics.mean([r["n_claims"] for r in props]), 3) if props else None,
        "critic_rounds_mean": round(statistics.mean([r["critic_rounds"] for r in props]), 3) if props else None,
        "latency_s": {"p50": pct([r["latency_s"] for r in ok], 0.5), "p95": pct([r["latency_s"] for r in ok], 0.95)},
        "latency_s_proposals": {"p50": pct([r["latency_s"] for r in props], 0.5), "p95": pct([r["latency_s"] for r in props], 0.95)},
        "tokens_per_job": {"mean": round(statistics.mean([r["tokens"] for r in ok]), 1) if ok else None,
                           "p50": pct([r["tokens"] for r in ok], 0.5), "p95": pct([r["tokens"] for r in ok], 0.95)},
        "tokens_per_proposal_mean": round(statistics.mean([r["tokens"] for r in props]), 1) if props else None,
        "llm_calls_per_job_mean": round(statistics.mean([r["llm_calls"] for r in ok]), 2) if ok else None,
        "cost_usd_total": round(sum(r["cost_usd"] for r in ok), 6),
        "cost_usd_per_job": round(sum(r["cost_usd"] for r in ok) / max(1, len(ok)), 6),
        "cost_usd_per_proposal": round(sum(r["cost_usd"] for r in props) / max(1, len(props)), 6) if props else None,
    }


def score_outcomes(recs: list[dict]) -> dict:
    """GigSim simulated-client outcome for each drafted proposal (gigsim.client_model.score_proposal)."""
    from gigsim.client_model import score_proposal

    rows = []
    for r in recs:
        if not r.get("cover_letter"):
            continue
        try:
            s = score_proposal(r["job_id"], r["cover_letter"], float(r["price"] or 0), r.get("screening_answers"))
        except KeyError:
            continue
        rows.append({"job_id": r["job_id"], "reply_prob": s["reply_prob"], "replied": bool(s["replied"]),
                     "interview": bool(s.get("interview")), "hired": bool(s["hired"])})
    n = len(rows)
    return {"n": n,
            "reply_rate": round(sum(x["replied"] for x in rows) / n, 4) if n else None,
            "interview_rate": round(sum(x["interview"] for x in rows) / n, 4) if n else None,
            "hire_rate": round(sum(x["hired"] for x in rows) / n, 4) if n else None,
            "mean_reply_prob": round(statistics.mean(x["reply_prob"] for x in rows), 4) if n else None}, rows


def hardware() -> dict:
    import platform
    import subprocess

    info = {"machine": platform.machine(), "system": platform.system(), "python": platform.python_version()}
    try:
        info["cpu"] = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
        info["mem_gb"] = round(int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout) / 2**30, 1)
    except Exception:
        pass
    return info


def write_json(name: str, data) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    p = RESULTS / name
    p.write_text(json.dumps(data, indent=2, default=str))
    return p
