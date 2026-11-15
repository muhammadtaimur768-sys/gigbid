"""V8: corrective RAG as a small LangGraph.

    retrieve -> grade --(weak and retries left)--> rewrite -> retrieve
                     \\--(ok or out of retries)----> finalize (keep relevant evidence, or refuse with [])

Grading uses cross-encoder logits (thresholds in rag/config.yaml `corrective`). The rewrite step is
LLM-free: it switches to hybrid retrieval, widens the candidate pool and re-asks each weak requirement
on its own and anchored on the job title.
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from rag.variants.pipeline import Pipeline

NAME = "v8"
FLAGS = {"corrective": True, "rerank": True}


class CState(TypedDict, total=False):
    query: str
    requirements: list[str]
    queries: list[str]
    weights: list[float]
    k: int
    mask: Any
    attempt: int
    retrieval: Optional[str]
    n: Optional[int]
    fused: list[dict]
    per_query: dict
    weak: list[str]
    best: float
    refused: bool
    result: list[dict]


def build_corrective_graph(pipe: Pipeline):
    cc = pipe.cfg["corrective"]

    def retrieve(s: CState) -> CState:
        fused, per_query = pipe.run_queries(s["queries"], s["weights"], s.get("mask"), s.get("n"), s.get("retrieval"))
        if s.get("fused"):  # merge with the previous attempt, keep the better entry per item
            merged = {d["key"]: d for d in s["fused"]}
            for d in fused:
                old = merged.get(d["key"])
                if old is None or (d.get("rerank") or -1e9) > (old.get("rerank") or -1e9):
                    merged[d["key"]] = d
            fused = list(merged.values())
        return {"fused": fused, "per_query": per_query}

    def grade(s: CState) -> CState:
        weak = []
        for q, items in s["per_query"].items():
            best = max((d["rerank"] for d in items if d.get("rerank") is not None), default=float("-inf"))
            if best < cc["weak_threshold"]:
                weak.append(q)
        best_all = max((d["rerank"] for d in s["fused"] if d.get("rerank") is not None), default=float("-inf"))
        return {"weak": weak, "best": best_all}

    def route(s: CState) -> str:
        if s["weak"] and s.get("attempt", 0) < cc["max_retries"]:
            return "rewrite"
        return "finalize"

    def rewrite(s: CState) -> CState:
        title = s["query"].splitlines()[0][:120]
        qs = []
        for q in s["weak"]:
            qs.append(q if q == s["query"] else f"{q} ({title})")
        return {"queries": qs, "weights": [1.0] * len(qs), "attempt": s.get("attempt", 0) + 1,
                "retrieval": "hybrid", "n": pipe.r["candidates"] * 2}

    def finalize(s: CState) -> CState:
        relevant = [d for d in s["fused"] if d.get("rerank") is not None and d["rerank"] >= cc["relevant_threshold"]]
        relevant.sort(key=lambda d: (-d["rerank"]))
        if len(relevant) < cc["min_relevant"] or s.get("best", float("-inf")) < cc["refuse_threshold"]:
            return {"result": [], "refused": True}
        # keep fused order among relevant items
        keep = {d["key"] for d in relevant}
        ordered = [d for d in sorted(s["fused"], key=lambda d: -d["score"]) if d["key"] in keep]
        return {"result": ordered[: s["k"]], "refused": False}

    g = StateGraph(CState)
    g.add_node("retrieve", retrieve)
    g.add_node("grade", grade)
    g.add_node("rewrite", rewrite)
    g.add_node("finalize", finalize)
    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", route, {"rewrite": "rewrite", "finalize": "finalize"})
    g.add_edge("rewrite", "retrieve")
    g.add_edge("finalize", END)
    return g.compile()


class CorrectivePipeline:
    def __init__(self, pipe: Pipeline):
        self.pipe = pipe
        self.graph = build_corrective_graph(pipe)
        self.last_state: dict = {}

    def search(self, query: str, k: int, mask, requirements: list[str] | None = None) -> list[dict]:
        queries, weights = self.pipe.queries_for(query, requirements)
        state = self.graph.invoke({"query": query, "requirements": requirements or [], "queries": queries,
                                   "weights": weights, "k": k, "mask": mask, "attempt": 0, "fused": []})
        self.last_state = {"refused": state.get("refused"), "attempts": state.get("attempt"), "best": state.get("best")}
        return state["result"]
