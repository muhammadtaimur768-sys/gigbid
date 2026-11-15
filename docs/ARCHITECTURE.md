# GigBid architecture

GigBid finds freelance jobs worth bidding on, drafts proposals that only claim what the
portfolio can prove, and never sends anything without a human approving it. This page covers
the two LangGraph graphs, the marketplace port, the MCP surface and the stores, and explains why
each agent exists.

Measured results are not repeated here. They live in `evals/results/` and the README tables
generated from those files.

## 1. System overview

```mermaid
flowchart LR
  subgraph Browser
    UI["React + Vite SPA<br/>inbox · studio · pipeline · messages · runs · analytics · settings"]
  end
  subgraph API["FastAPI (apps/api)"]
    R["routers /api/*"]
    SSE["streaming.py<br/>SSE bridge"]
    AUTH["auth: users, sessions,<br/>encrypted OAuth token store"]
  end
  subgraph Worker["Arq worker (worker/)"]
    SCH["scheduled scouting<br/>per saved search"]
    RUN["long graph runs"]
  end
  subgraph Agent["LangGraph (agent/)"]
    BG["bid graph<br/>(thread per job)"]
    CG["conversation graph<br/>(thread per client thread)"]
    PORT["MarketplacePort"]
    MCPC["mcp_client.py<br/>per-agent tool allowlists"]
  end
  subgraph MCP["MCP servers (mcp_servers/)"]
    MP["portfolio :8201"]
    MM["marketplace :8202"]
    MW["workspace :8203"]
  end
  GS["GigSim :8100<br/>(simulator)"]
  UP["Upwork official MCP<br/>(live mode, drafts only)"]
  PG[("Postgres + pgvector<br/>app data · checkpoints · store · trace_events")]
  RD[("Redis<br/>Arq queue")]
  OL["Ollama (open profile)<br/>or Groq (deploy)"]

  UI -- "/api + X-Trace-Id" --> R
  UI -- EventSource --> SSE
  R --> BG & CG
  R -- enqueue --> RD --> RUN --> BG
  SCH --> BG
  BG & CG --> PORT --> MCPC
  BG & CG --> MCPC
  MCPC --> MP & MM & MW
  MM -- adapters/gigsim.py --> GS
  MM -- adapters/upwork_live.py --> UP
  BG & CG -. LLM calls .-> OL
  BG & CG <--> PG
  R <--> PG
```

One trace id is created per UI request (or per scheduled scout), sent as `X-Trace-Id`, carried
in graph config, forwarded to every MCP call in `_meta.trace_id`, and written to both the
`trace_events` table and the marketplace audit log.

## 2. Bid graph (one thread per job)

```mermaid
flowchart TD
  START((start)) --> scout_intake
  scout_intake -->|Send| analyst["Job Analyst<br/>JobSpec"]
  scout_intake -->|Send| risk["Risk Assessor<br/>RiskReport"]
  scout_intake -->|Send| matcher["Fit Matcher<br/>FitReport"]
  analyst --> decide
  risk --> decide
  matcher --> decide
  decide{"decide<br/>BidDecision"}
  decide -->|skip| END1((end))
  decide -->|watch| END2((end))
  decide -->|bid| pricing["Pricing Strategist<br/>PriceQuote"]
  pricing --> writer["Proposal Writer<br/>ProposalDraft"]
  writer --> verifier["claim verification<br/>(rag/verify.py)"]
  verifier --> critic["Critic<br/>Critique"]
  critic -->|"revise (at most 2 rounds)"| writer
  critic -->|accept| compliance["Compliance Guard<br/>ComplianceVerdict"]
  compliance -->|block| needs_attention[["needs_attention"]]
  compliance -->|pass| approval["approval<br/>interrupt()"]
  approval -->|edit| compliance
  approval -->|reject + reason| END3((end))
  approval -->|approve| submit["submit<br/>(MarketplacePort, idempotency key)"]
  submit --> END4((end))
  submit -->|retries exhausted| dead_letter[["dead_letter"]]
  budget["step / token budget exceeded<br/>(any node)"] -.-> needs_attention
```

- Analyst, Risk and Matcher run in parallel through `Send`; the state fields they write use
  reducers, so parallel writes merge instead of overwriting each other.
- The approval payload carries the draft, the evidence behind every claim, the risk report,
  the price rationale and the `dry_run` preview (cost in Connects, balance after).
- The submit idempotency key is `hash(thread_id, draft_version)`. A crash between approval and
  submit replays the node from the Postgres checkpoint with the same key, and the marketplace
  returns the original result instead of submitting twice.

## 3. Conversation graph (one thread per client conversation)

```mermaid
flowchart TD
  START((start)) --> read_messages
  read_messages --> classify_intent{"classify_intent<br/>question · negotiation ·<br/>interview_request · scam_signal"}
  classify_intent -->|scam_signal| needs_attention[["needs_attention<br/>(flag to user)"]]
  classify_intent -->|interview_request| slots["workspace.free_slots"]
  slots --> draft_reply
  classify_intent -->|question / negotiation| draft_reply["Client Liaison<br/>draft_reply"]
  draft_reply --> compliance["Compliance Guard"]
  compliance -->|block| needs_attention
  compliance -->|pass| approval["approval<br/>interrupt()"]
  approval -->|approve| send["send_message<br/>(+ create_interview_hold)"]
  approval -->|edit| compliance
  approval -->|reject| END1((end))
  send --> END2((end))
```

## 4. Marketplace port

```mermaid
flowchart LR
  subgraph agent
    N["graph nodes"] --> P["MarketplacePort (Protocol)<br/>agent/marketplace_port.py"]
  end
  P -->|MCP tools| S["marketplace MCP server<br/>auth · rate limit · audit · idempotency · dry_run"]
  S --> A{"marketplace.mode"}
  A -->|gigsim| G["adapters/gigsim.py<br/>httpx, backoff on 429/5xx"]
  A -->|upwork| U["adapters/upwork_live.py<br/>official Upwork MCP, OAuth,<br/>write methods create drafts only"]
  P -. "MarketplaceUnavailable" .-> D["degraded mode<br/>banner in UI, runs paused"]
```

Agents never call a marketplace directly. Switching from GigSim to live mode is a config change
(`MARKETPLACE_MODE=upwork`) that swaps the adapter behind the same MCP tools. The graphs, the
prompts and the UI do not change.

## 5. MCP surface

| Server | Tools | Resources / prompts | Notes |
|---|---|---|---|
| portfolio (:8201) | `search_evidence`, `get_case_study`, `list_skills` | `portfolio://case/{id}`, `portfolio://proposal/{id}`, `portfolio://repo/{id}`; prompt templates | Read-only. Published on its own (see `mcp_servers/portfolio/README.md`). |
| marketplace (:8202) | read: `search_jobs`, `get_job`, `get_client_history`, `get_connects_balance`, `list_threads`, `list_messages`, `get_market_stats`, `list_proposals`; write: `create_proposal_draft`, `submit_proposal`, `send_message` | none | Bearer auth, per-user token bucket set below GigSim's limit, append-only audit log, mandatory `idempotency_key`, `dry_run`, tool annotations. |
| workspace (:8203) | `free_slots`, `create_interview_hold`, `create_email_draft` | none | Local mock calendar and mailbox. |

Each agent gets only the tools it needs (`TOOL_ALLOWLIST` in `agent/mcp_client.py`). For
example, the Scout cannot submit, and only the submit and send nodes can reach write tools,
and only after an approval resume. The tool-by-tool trust rationale is in `docs/TOOLS.md`.

## 6. Stores: state, trace and memory kept apart

```mermaid
flowchart LR
  subgraph "per thread (short-lived)"
    ST["Graph state (BidState / ConvState)<br/>job, analyses, evidence, decision, price,<br/>drafts, critiques, approvals, outcomes"]
    CK[("Postgres checkpointer<br/>every super-step; replay / resume")]
  end
  subgraph "audit (append-only)"
    TR[("trace_events<br/>node, tool, args, result, tokens, cost, latency")]
    AL[("marketplace audit log<br/>user, tool, masked args, trace_id")]
  end
  subgraph "long-term (promoted only)"
    SM[("style memory<br/>(style, user_id)")]
    OM[("outcome memory<br/>(outcome, user_id, category)")]
  end
  PI[("portfolio index<br/>chunks + embeddings + BM25<br/>(numpy on disk; pgvector optional)")]
  ST <--> CK
  ST -. "every tool call / node event" .-> TR
  ST -- "edit diffs, via promotion rule" --> SM
  GE["GigSim outcome events"] -- "via promotion rule" --> OM
```

| Kind | What it holds | Where |
|---|---|---|
| State | What this job or conversation needs right now | `agent/state.py`, checkpointed in Postgres (SQLite locally) |
| Execution trace | Every tool name, argument, result and observation, plus tokens, cost and latency per node, with PII masked | `trace_events` table, LangSmith when `LANGSMITH_API_KEY` is set, marketplace audit log |
| Long-term memory | Only promoted knowledge: style rules learned from repeated edits, and what won or got replies per category | LangGraph store namespaces `("style", user)` and `("outcome", user, category)`. Rules are in `agent/memory/promotion_rules.py` and thresholds in `agent/config.yaml`. |

Raw tool output never goes straight into memory. The user can see and delete every memory item in
Settings.

## 7. Why each agent exists

| Agent | Hand-off | Why it is a separate agent |
|---|---|---|
| Scout | job ids into a bid thread | Runs on a schedule in the worker. It filters by saved searches and drops duplicates, so the expensive graph only sees new, on-profile jobs. It needs read-only search tools and nothing else. |
| Job Analyst | `JobSpec` | Breaks a messy post into explicit requirements, deliverables and screening questions. Retrieval and pricing need structured requirements, not prose. |
| Risk Assessor | `RiskReport` | Scams, off-platform contact and planted injections have to be caught before any text reaches the writer. It runs in parallel and can veto the job on its own. |
| Fit Matcher | `FitReport` | Maps each requirement to portfolio evidence (requirement-to-evidence matrix). This is the only source of claims the writer is allowed to make. |
| Decide | `BidDecision` | A deterministic or cheap-model join over the three reports, so skip, watch or bid can be explained and audited. Thresholds are in config. |
| Pricing Strategist | `PriceQuote` | Uses market stats, the client's history and the freelancer's floor and target. Kept separate so the price can be explained and tuned without touching the writer. |
| Proposal Writer | `ProposalDraft` | Drafts from the `FitReport` evidence and the style memory only. |
| Claim verification | claims with support labels | Splits the draft into claims and grounds each one. Unsupported claims are removed or rewritten before the Critic sees the draft. |
| Critic | `Critique` | Checks quality (generic openings, answers to screening questions, length). Bounded at two revision rounds. |
| Compliance Guard | `ComplianceVerdict` | Applies the policy pack (`data/policy_pack/`) as rules plus checks. It can block with a reason shown in the UI, and it re-checks human edits. |
| Client Liaison | reply drafts | Runs in the conversation graph. It classifies intent, drafts replies and offers interview slots, and every send goes through approval. |

Whether this split is worth its cost compared with a single ReAct agent and a prebuilt supervisor
is measured, not assumed (R&D question C). See the comparison table in the README and its source
file in `evals/results/`.

## 8. Failure handling

- Per-node retries and timeouts (`agent/config.yaml`). Cheap nodes have a fallback model, and every node
  has a deterministic heuristic path (`LLM_PROVIDER=heuristic`), which CI uses.
- GigSim 429 responses: the adapter honours `Retry-After` with backoff, and the MCP token bucket stays
  under the simulator's limit. 5xx responses are retried with backoff, then the run goes to `dead_letter`.
- If the marketplace MCP server is unreachable, `MarketplaceUnavailable` is raised, `/api/health` reports
  degraded and the UI shows the degraded banner. Pending approvals stay in the checkpointer until it returns.
- Exceeding the step or token budget moves the thread to `needs_attention`, which is visible in the inbox.

## 9. Deployment topologies

- **Local / compose**: one container per service (see `infra/docker-compose.yml`), with Postgres
  (pgvector), Redis, Arq worker and Ollama.
- **Public deploy (single host)**: the API process mounts GigSim at `/gigsim` and the MCP servers at
  `/mcp/*` (`MOUNT_GIGSIM=1`, `MOUNT_MCP=1`) and uses Groq for models. See ADR 0006 and
  `docs/RUNBOOK.md`.
