# Tool catalogue

Every capability the agents use is an MCP tool on one of three first-party servers built with the
official MCP Python SDK (FastMCP, `mcp==1.14.1`), plus two third-party servers we did not write.
Schemas are frozen by `tests/contract/snapshots/*.json`; CI fails if a signature changes unintentionally.

**Annotation key:** RO = `readOnlyHint`, D = `destructiveHint`, I = `idempotentHint`, OW = `openWorldHint`.
**Auth:** over HTTP every server requires `Authorization: Bearer <token>` (env `MCP_PORTFOLIO_TOKEN`,
`MCP_MARKETPLACE_TOKEN`, `MCP_WORKSPACE_TOKEN`; a JSON map `MCP_<NAME>_TOKENS` allows several tokens).
Requests without a valid token get 401 before reaching the MCP layer. Over stdio the server runs as a
child process of the host and inherits its trust. Marketplace and workspace calls pass through a
per-user token bucket (50 calls/min, below GigSim's 60/min) and land in the append-only audit log
`data/processed/audit.log` (user, tool, PII-masked args and result, status, trace_id from `_meta.trace_id`
or the `X-Trace-Id` header).

## First-party tools

| Tool | Server | R/W | Annotations | Auth | Notes |
|---|---|---|---|---|---|
| `search_evidence` | portfolio | read | RO, !D, I, !OW | bearer (HTTP) | requirement 2-500 chars, k 1-20, filters type/outcome/skills/industry/project |
| `get_case_study` | portfolio | read | RO, !D, I, !OW | bearer (HTTP) | id pattern `^[A-Za-z0-9_.-]{1,80}$` |
| `list_skills` | portfolio | read | RO, !D, I, !OW | bearer (HTTP) | |
| `search_jobs` | marketplace | read | RO, !D, I, OW | bearer + rate limit + audit | limit 1-50, skills max 20 |
| `get_job` | marketplace | read | RO, !D, I, OW | bearer + rate limit + audit | job text is untrusted |
| `get_client_history` | marketplace | read | RO, !D, I, OW | bearer + rate limit + audit | |
| `get_connects_balance` | marketplace | read | RO, !D, I, OW | bearer + rate limit + audit | |
| `list_threads` | marketplace | read | RO, !D, I, OW | bearer + rate limit + audit | |
| `list_messages` | marketplace | read | RO, !D, I, OW | bearer + rate limit + audit | |
| `get_market_stats` | marketplace | read | RO, !D, I, OW | bearer + rate limit + audit | p25/p50/p75 hourly and fixed |
| `list_proposals` | marketplace | read | RO, !D, I, OW | bearer + rate limit + audit | optional status filter |
| `get_marketplace_status` | marketplace | read | RO, !D, I, OW | bearer | degraded-mode signal |
| `create_proposal_draft` | marketplace | write | !RO, !D, I, OW | bearer + rate limit + audit | `idempotency_key` required, `dry_run`, cover letter 50-2500 chars, no emails/phones |
| `submit_proposal` | marketplace | write | !RO, **D**, I, OW | bearer + rate limit + audit | spends Connects; `idempotency_key` required; `dry_run` returns payload + cost; live Upwork mode creates a draft only |
| `send_message` | marketplace | write | !RO, !D, I, OW | bearer + rate limit + audit | `idempotency_key` required, `dry_run`; live mode creates a draft only |
| `free_slots` | workspace | read | RO, !D, I, !OW | bearer + rate limit + audit | days 1-14, duration 15-240 min |
| `list_holds` | workspace | read | RO, !D, I, !OW | bearer + rate limit + audit | |
| `create_interview_hold` | workspace | write | !RO, !D, I, !OW | bearer + rate limit + audit | tentative only; rejects overlaps; `idempotency_key`, `dry_run` |
| `create_email_draft` | workspace | write | !RO, !D, I, !OW | bearer + rate limit + audit | never sends; `idempotency_key`, `dry_run` |

Why these annotations: `submit_proposal` is the only destructive tool because it spends Connects and
cannot be undone. Drafts, holds and messages only add data, so they are not destructive. All writes are
idempotent *because* the key is mandatory: a retry with the same key returns the stored first result
(`replayed: true`) and never submits or spends twice; reusing a key with different arguments is rejected.
Marketplace tools are open-world (they reach an external service); portfolio and workspace are closed.

**Resources:** `portfolio://case/{id}`, `portfolio://proposal/{id}`, `portfolio://repo/{id}`,
`portfolio://items`, `marketplace://job/{job_id}`, `workspace://holds`.
**Prompts:** `answer_screening_question`, `prove_requirements`, `draft_opening_paragraph`,
`skills_gap_check` (portfolio); `triage_job` (marketplace); `schedule_interview` (workspace).

## Mounting and running

| Server | stdio | HTTP | ASGI factory (mount path) |
|---|---|---|---|
| portfolio | `python -m mcp_servers.portfolio.server` or `gigbid-portfolio-mcp` | `--http` (port 8201) | `mcp_servers.portfolio.server.build_http_app()` (`/mcp/portfolio`) |
| marketplace | `python -m mcp_servers.marketplace.server` | `--http` (port 8202) | `mcp_servers.marketplace.server.build_http_app()` (`/mcp/marketplace`) |
| workspace | `python -m mcp_servers.workspace.server` | `--http` (port 8203) | `mcp_servers.workspace.server.build_http_app()` (`/mcp/workspace`) |

The ASGI apps run the SDK's Streamable HTTP transport in stateless JSON mode and start their session
manager lazily on the first request, so they work when mounted inside the API without lifespan wiring.
Any path under the mount reaches the MCP endpoint; `GET <mount>/health` is unauthenticated.

## Marketplace adapters

`MARKETPLACE_MODE` (or `marketplace.mode` in `agent/config.yaml`) selects the backend; the tool surface
is identical, so the graph cannot tell which one it is using.

* **gigsim** (`adapters/gigsim.py`): httpx with a timeout, bounded retries (3) with exponential backoff
  and jitter on connection errors, timeouts, 429 (honours `Retry-After`) and 5xx. 4xx is not retried
  (`MarketplaceNotFound`, `InsufficientConnects`, `MarketplaceError`). Running out of retries raises the
  typed `MarketplaceUnavailable`, which the API turns into the degraded banner.
* **upwork** (`adapters/upwork_live.py`): `MultiServerMCPClient` over `streamable_http` to
  `https://mcp.upwork.com/mcp`. OAuth tokens are stored per user, encrypted with Fernet
  (`TOKEN_ENC_KEY`), through the SDK's `TokenStorage` protocol, so `OAuthClientProvider` can run the
  authorization-code + PKCE flow and refresh tokens. Tool names map through
  `adapters/upwork_tool_map.yaml`; the loader refuses any write mapping that is not a draft tool, so
  proposals and messages are only ever created as drafts that the user confirms on Upwork. `search_jobs`
  results are cached for `upwork.min_read_interval_s` (900 s) so scheduled reads never look like
  scraping. No browser automation, cookies or page scraping. The live server could not be called from
  this environment, so the mapping layer is tested with a fake client (`tests/test_adapters.py`), and
  `verify_mapping()` lists mapped tool names that the live server does not expose.

## Third-party servers

| Server | Used for | Trust rationale |
|---|---|---|
| Upwork MCP (`https://mcp.upwork.com/mcp`) | live marketplace mode | Run by the marketplace itself behind its own OAuth. We use only the scopes a user grants, store tokens encrypted per user, and allow only read and draft tools through our allowlist mapping, so a compromised or changed tool cannot submit or spend on its own. |
| GitHub MCP (`github/github-mcp-server`, official) | importing a freelancer's repos into the portfolio | Maintained by GitHub, open source, and pinned to a release. It runs with a fine-grained read-only token scoped to the user's chosen repos, and its output is treated as untrusted text that goes through the same ingestion and injection filters as any upload. |
