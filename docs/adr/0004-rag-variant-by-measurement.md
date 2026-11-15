# ADR 0004: The shipped RAG variant is chosen by measurement

- Status: accepted
- Date: 2026-11-15

## Context
Portfolio evidence is messy: the same project is described three ways across a case study, a repo
and an old proposal, and skills are often implied rather than named. Several retrieval designs are
plausible: naive dense, hybrid BM25 + dense, requirement decomposition, reranking, contextual chunks,
parent-child chunks, and a skill graph. Picking one by intuition would be unfalsifiable.

## Decision
- All variants live in `rag/variants/` behind one factory (`rag/retriever.py`). The active variant is
  the `rag.variant` key in `agent/config.yaml`, so switching needs no code change.
- Variants are compared on the dev set per persona with Recall@5, MRR and nDCG@10 against gold
  evidence, plus downstream unsupported-claim rate and GigSim reply rate (`evals/runners/rag_eval.py`,
  `evals/runners/ablation.py`).
- The variant that ships is the one the measurements favour, with cost and latency weighed against the
  gains.

## Result
See `evals/results/rag_decision.md` for the chosen variant, the comparison it rests on, and the
one-paragraph decision on what ships.

## Consequences
- Adding a variant means adding a file plus one config value. The eval harness picks it up.
- A better retrieval score does not guarantee a better reply rate. Where they diverge, the decision
  record says which one won and why.
