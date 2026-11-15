# ADR 0003: Hand-built LangGraph graphs, not a prebuilt agent

- Status: accepted (subject to the R&D question C comparison)
- Date: 2026-11-15

## Context
The workflow has hard requirements: parallel analysis, a bounded critique loop, compliance blocking,
`interrupt()` before every send or spend, exactly-once submission after a crash, and per-thread step
and token budgets. A single ReAct agent with all tools, or `langgraph-supervisor`, could do the job
with less code, but neither gives structural guarantees for these constraints.

## Decision
Two explicit `StateGraph`s: the bid graph (one thread per job) and the conversation graph (one thread
per client conversation). They have typed state with reducers, Pydantic hand-offs between nodes
(`agent/handoffs.py`), `Send` for the parallel fan-out, conditional edges for skip/watch/bid and
critic loops, and an `interrupt()` approval node in front of every side effect. Postgres checkpointer
in deployment, SQLite locally.

## Consequences
- The safety properties come from the graph's structure: no path reaches `submit` without passing
  `approval`, and the critic loop is capped by the counter in state. They do not depend on prompt wording.
- Every decision can be replayed from checkpoint history at any node.
- More code to maintain than a prebuilt agent. Whether the extra structure pays for itself is measured
  on dev jobs against (a) a single ReAct agent and (b) a prebuilt supervisor. Results: see the
  multi-agent comparison table in the README and its source in `evals/results/`. If the baseline wins
  on some job types, that is reported there.
