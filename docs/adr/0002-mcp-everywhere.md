# ADR 0002: Every capability is an MCP server

- Status: accepted
- Date: 2026-11-15

## Context
Agents need three kinds of capability: portfolio evidence, marketplace reads and writes, and the
freelancer's workspace (calendar, email drafts). We could wrap them as in-process LangChain tools or
expose them as MCP servers.

## Decision
All three are MCP servers built on the official MCP Python SDK (`FastMCP`): `portfolio`,
`marketplace` and `workspace`. Agents reach them through `langchain-mcp-adapters`
(`MultiServerMCPClient`) with a per-agent tool allowlist. Each server can run over stdio, in memory
(tests) or over streamable HTTP (compose, deploy).

## Consequences
- Tool schemas, annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`), auth, rate limits
  and audit logs sit in one layer, and contract tests snapshot them (`tests/contract/`).
- The portfolio server is useful on its own and is published for any MCP host.
- Live mode reuses the official Upwork MCP server instead of scraping, which keeps GigBid within the
  platform's automation rules.
- Cost: serialization overhead and more moving parts. To keep the deploy small, the API process can
  mount the servers in-process (`MOUNT_MCP=1`, ADR 0006).
- How finely the tools are split (granular tools vs fewer composite tools) is measured in R&D
  question A, not decided here.
