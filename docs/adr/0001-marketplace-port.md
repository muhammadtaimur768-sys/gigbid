# ADR 0001: One marketplace port, adapters behind it

- Status: accepted
- Date: 2026-11-15

## Context
GigBid has to work against GigSim (development, evaluation, hidden test run) and against the
live Upwork account through the official Upwork MCP server. The two differ in auth (static bearer
vs OAuth), rate limits, error shapes and what writes are allowed. In live mode only drafts are
created, and the human confirms on the platform. If agents called either backend directly, every
node would need branches for both, and the viva question "switch to live mode, what changes?"
would touch the whole codebase.

## Decision
- A single `MarketplacePort` protocol (`agent/marketplace_port.py`) is the only way the graphs
  touch a marketplace. It is implemented by calling the marketplace MCP server's tools.
- The marketplace MCP server picks an adapter from `marketplace.mode` (`gigsim` or `upwork`):
  `adapters/gigsim.py` (httpx with retries) or `adapters/upwork_live.py` (official Upwork MCP via
  `MultiServerMCPClient`, write methods create drafts only).
- Idempotency keys, `dry_run`, rate limiting and audit logging live in the server, so they apply the
  same way to both adapters.
- `MarketplaceUnavailable` is the single failure signal, mapped to degraded mode in API and UI.

## Consequences
- Going live is a config and env change (`MARKETPLACE_MODE=upwork` plus an OAuth connection). Graphs,
  prompts and UI stay the same.
- Live-mode capabilities are the intersection of what both backends support. Anything only GigSim
  has (e.g. `/admin/tick`) stays outside the port.
- There is one extra hop (graph to MCP to adapter) on every call. We accept the latency for a single
  place to audit, rate-limit and test.
