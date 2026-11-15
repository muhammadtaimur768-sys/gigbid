# GigBid runbook

Operational procedures: run locally, deploy, schedule scouting, run the failure drills, and rotate
secrets. Commands assume the repository root.

## 1. Run locally

### Option A: docker compose (full stack)
```bash
cp .env.example .env            # fill JWT_SECRET, TOKEN_ENC_KEY, REVIEWER_PASSWORD, POSTGRES_PASSWORD
docker compose up --build       # or: make up
```
| Service | URL / port | Health |
|---|---|---|
| web (nginx + SPA) | http://localhost:8080 | `/healthz` |
| api | http://localhost:8000 | `/api/health` (includes marketplace status) |
| gigsim | http://localhost:8100 | `/health` |
| mcp-portfolio / mcp-marketplace / mcp-workspace | :8201 / :8202 / :8203, path `/mcp` | TCP |
| postgres (pgvector) | :5432 | `pg_isready` |
| redis | internal | `redis-cli ping` |
| ollama | :11434 | `ollama list` |

On first start, `ollama-pull` downloads the models in `OLLAMA_MODELS_TO_PULL` into the `ollama`
volume and exits. Until it finishes, LLM nodes use their fallbacks. Check progress with
`docker compose logs -f ollama-pull`.

Sign in as `reviewer@gigbid.app` with the `REVIEWER_PASSWORD` from `.env`. Run `make demo` to
start the stack, seed the reviewer and advance GigSim one tick so the inbox has fresh jobs.

### Option B: processes, no Docker
```bash
uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"
(cd apps/web && npm ci)
make seed                       # GigSim seed, portfolio indexes, reviewer
make dev                        # GigSim, 3 MCP servers, API (reload), Vite on http://localhost:5173
```
Without Ollama running, set `LLM_PROVIDER=heuristic` for deterministic node fallbacks.

### Tests and evals
```bash
make lint test                  # ruff, unit + contract + integration (LLM_PROVIDER=heuristic)
make e2e                        # Playwright
make guards                     # CI guards (gigsim unchanged, prompts, README numbers, secrets)
make eval                       # full evals -> evals/results/*.json, then README tables
make eval-smoke                 # what the PR eval gate runs
```

## 2. Deploy (single host, Vercel)

Topology and rationale: ADR 0006. The API process mounts GigSim (`MOUNT_GIGSIM=1`) and the MCP
servers (`MOUNT_MCP=1`), and the SPA is built from `apps/web`.

1. Create a managed Postgres database (any provider with pgvector) and copy its URL.
2. Set the project environment variables (Production) with `vercel env add`:
   `DATABASE_URL`, `JWT_SECRET`, `TOKEN_ENC_KEY`, `REVIEWER_PASSWORD`, `CRON_SECRET`,
   `GROQ_API_KEY`, `LLM_PROVIDER=groq`, `MOUNT_GIGSIM=1`, `MOUNT_MCP=1`, `RUN_MODE=inline`,
   `MCP_MARKETPLACE_TOKEN`, `PUBLIC_BASE_URL`, optionally `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT`.
   Leave the `MCP_*_URL` variables unset (servers are mounted in-process) or point them at
   `$PUBLIC_BASE_URL/mcp/<server>/mcp`.
3. Deploy: `vercel --prod`. On startup the API creates its tables and seeds the reviewer account.
4. Smoke test: `curl $PUBLIC_BASE_URL/api/health`, then sign in as the reviewer and open the inbox.
5. Scheduled scouting: set the repository variable `PUBLIC_BASE_URL` and the secret `CRON_SECRET`.
   `.github/workflows/scout-cron.yml` then calls `POST /api/cron/scout` every 30 minutes.
6. Keep it live until grades are released. Check `/api/health` before the hidden test run window and
   do not rotate `DATABASE_URL` during it.

Rollback: `vercel rollback` to the previous deployment. The database is shared, so roll back only
across releases without schema changes. Otherwise restore from the provider's backup.

## 3. Scheduling and the live-mode polling interval

Each saved search has its own schedule. The worker (compose) or the cron trigger (deploy) enqueues
one scout run per due search. Scout runs are idempotent: a job id already analysed for this user is
skipped, and submissions carry an idempotency key, so a duplicate trigger or a worker restart never
re-analyses or double-submits.

| Mode | Interval | Configured by |
|---|---|---|
| GigSim | on demand / per tick (any interval is safe, it is a simulator) | saved search schedule |
| Live (Upwork official MCP) | **30 minutes**, minimum, per saved search | `SCOUT_INTERVAL_MINUTES=30` |

Why 30 minutes in live mode:
- **Rate limits are conservative by policy, not by measurement.** We have no published per-app quota
  for the Upwork MCP server to design against, and Upwork treats aggressive automation as a violation.
  Each scout cycle costs 1 search plus, for each new job, a job read and a client-history read. Spacing
  cycles at 30 minutes keeps GigBid near the request pattern of a person checking their feed a couple
  of times an hour, and far below the token bucket the marketplace MCP server enforces per user
  (configured below GigSim's own limit).
- **A human approves every send.** End-to-end latency is set by when the freelancer reviews drafts,
  not by polling. Polling every minute would not make proposals arrive sooner.
- **The policy update charges for speed.** Since the 2026-11-02 policy update, bidding on a job posted
  less than an hour ago costs extra Connects (early-bird surcharge). Faster polling mostly buys the
  right to pay that surcharge. With a 30-minute cycle, the worst-case first look still falls inside the
  first hour if the user wants it.
- **Backoff overrides schedule.** On 429 the adapter honours `Retry-After`, and the next cycle is
  skipped if the previous one is still backing off.

Change the interval only with a reason recorded here. Never set it below 15 minutes in live mode.

## 4. Drill: kill the marketplace MCP server

Purpose: show what the user sees when the marketplace is down, and that nothing is lost.

```bash
docker compose stop mcp-marketplace          # or kill the process started by make dev
curl -s localhost:8000/api/health | python -m json.tool   # marketplace: "unavailable", status degraded
```
Expected:
- The UI shows the degraded banner ("marketplace unavailable") from `/api/health`
  (`DegradedBanner` component).
- Runs that need the marketplace raise `MarketplaceUnavailable` in `agent/marketplace_port.py`.
  The node retries with backoff and then parks the thread. It does not go to dead letter while the
  outage is transient, and no partial submission happens.
- Pending approvals stay in the checkpointer and can still be reviewed. Approving queues the submit,
  which runs when the marketplace is back.

Recover:
```bash
docker compose start mcp-marketplace
```
The banner clears on the next health poll, and parked threads resume from their last checkpoint.

## 5. Drill: crash and resume (exactly-once submit)

Purpose: approve a proposal, crash before it is submitted, and prove it is submitted exactly once.

```bash
# 1. Open a job in the Proposal studio and run it until it waits for approval.
# 2. Kill the API (and the worker) while the approval is pending:
docker compose kill api worker
# 3. Restart:
docker compose up -d api worker
# 4. Refresh the browser: the pending approval is still there (read from the Postgres checkpoint).
# 5. Approve. To crash *after* approval but *before* submit, kill the worker as soon as you click:
docker compose kill worker && docker compose up -d worker
```
Verify exactly-once:
```bash
# GigSim: one proposal for the job, even if the submit node ran more than once
curl -s -H "Authorization: Bearer gs-aiml-token" localhost:8100/proposals | python -m json.tool
# Audit log: the submit_proposal calls share one idempotency_key; repeats returned the original result
docker compose exec mcp-marketplace grep submit_proposal data/processed/audit.log
```
Why it works: the submit node's idempotency key is `hash(thread_id, draft_version)`. Replaying the
node from the checkpoint sends the same key, and the marketplace returns the stored result without
spending Connects again. Use the run viewer (`/runs/:id`) or checkpoint history to replay any job
from any node.

## 6. Rotate keys and secrets

Secrets come only from environment variables. `.env` is never committed, and CI runs gitleaks
plus `scripts/check_secrets.py`.

| Secret | Rotation | Side effects |
|---|---|---|
| `JWT_SECRET` | Generate a new value, update env, redeploy or restart the api | All sessions are invalidated, so users sign in again |
| `TOKEN_ENC_KEY` (Fernet) | Decrypt stored OAuth tokens with the old key and re-encrypt them with the new one (`cryptography.fernet.MultiFernet([new, old]).rotate(token)`), then switch the env to the new key | If the key is swapped without re-encryption, stored OAuth tokens become unreadable and users must reconnect Upwork |
| `GROQ_API_KEY`, `OPENAI_API_KEY`, `LANGSMITH_API_KEY` | Create the new key in the provider console, update env, redeploy, revoke the old key | None |
| `MCP_MARKETPLACE_TOKEN` | Update the env for both the api and the marketplace server together, then restart both | Calls fail with 401 between the two restarts |
| `CRON_SECRET` | Update the Vercel env and the GitHub secret | One missed scout cycle at most |
| `REVIEWER_PASSWORD` | Update env and re-run the reviewer seed | Share the new password with graders |
| Upwork OAuth tokens | Revoke in Upwork, reconnect from Settings | Stored encrypted per user |
| `POSTGRES_PASSWORD` / `DATABASE_URL` | Rotate in the DB provider, update env, restart all services | Do not rotate during the hidden test run |

If a secret leaks into git: rotate it first, then purge it from history. Rotating is what protects
you, because the purge does not remove copies others already fetched.

## 7. Where to look

- Traces: run viewer `/runs/:id`, the `trace_events` table, and LangSmith when enabled. Search by the
  `X-Trace-Id` shown in the UI.
- Marketplace calls: `data/processed/audit.log` (append-only, PII masked).
- Stuck threads: the inbox filter "needs attention" lists budget-exceeded and compliance-blocked
  threads, and dead-letter threads show their last error.
