# ADR 0005: Open-weight model profile by default, Groq for the public deploy

- Status: accepted
- Date: 2026-11-15

## Context
GigBid must run on a laptop without paid APIs (compose includes Ollama), CI must run with no model at
all, and the public deployment must answer the hidden test run reliably without a GPU host.

## Decision
- Model selection is configuration only (`agent/config.yaml`). Profiles: `open` (Ollama,
  `qwen2.5:7b-instruct` quantised), `open_mistral` (second open model for comparison) and `paid`
  (any OpenAI-compatible API, optional).
- Nodes are grouped into cheap (scout, analyst, risk, matcher, pricing, verifier, compliance, intent,
  decide) and strong (writer, critic, liaison) so a small model handles routing and risk.
- `LLM_PROVIDER=groq` is the deploy override. It keeps open-weight models, served through Groq's
  OpenAI-compatible API (`openai/gpt-oss-20b` for cheap nodes, `openai/gpt-oss-120b` for strong nodes).
- `LLM_PROVIDER=heuristic` swaps every node for its deterministic fallback. CI and the threshold gates
  use it.

## Consequences
- The same open-weight model family runs locally and in deployment. Quality differences between
  profiles are measured, not assumed.
- Groq becomes an external dependency for the live URL. If it is unavailable, cheap nodes fall back to
  the small model and every node keeps its heuristic path, so the system degrades instead of failing.
- Cost per job and per proposal is recorded per node in `trace_events` and reported from
  `evals/results/`.
