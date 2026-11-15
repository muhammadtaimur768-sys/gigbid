# ADR 0006: Single-host Vercel deploy with mounted sims; docker compose locally

- Status: accepted
- Date: 2026-11-15

## Context
Locally, the assignment requires `docker compose up` to start web, API, worker, the MCP servers,
GigSim, Postgres, Redis, the vector store and Ollama. The public URL must stay up until grades are
released and must survive the hidden test run, cheaply and without operating many services.

## Decision
- **Local / self-hosted:** `infra/docker-compose.yml` runs one container per service. The worker runs
  scouting and long graph runs on Arq/Redis (`RUN_MODE=worker`), and MCP servers talk streamable HTTP.
- **Public deploy:** a single Vercel project. The SPA is built from `apps/web`, and `api/index.py`
  exports the FastAPI app with `MOUNT_GIGSIM=1` (GigSim at `/gigsim`) and `MOUNT_MCP=1` (MCP servers at
  `/mcp/portfolio`, `/mcp/marketplace`, `/mcp/workspace`). Runs execute inline
  (`RUN_MODE=inline`). State lives in managed Postgres, so checkpoints, the store and traces survive
  cold starts. Models come from Groq (ADR 0005). Scheduled scouting is triggered externally through
  `POST /api/cron/scout` (`.github/workflows/scout-cron.yml`).

## Consequences
- One URL, one deploy, no servers to patch. The reviewer login works against the bundled simulator.
- Serverless limits apply: no long-lived worker and bounded request duration. Long runs are split at
  checkpoints, with approvals as natural pause points, and each resume is a new request.
- The two topologies differ only in environment variables. The same code paths are tested in CI.
- The Arq worker is exercised in compose and in the crash-resume drill (`docs/RUNBOOK.md`), not on the
  public host.
