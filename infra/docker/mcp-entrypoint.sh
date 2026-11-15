#!/bin/sh
# Selects which MCP server runs in the shared gigbid-mcp image (streamable HTTP, bearer auth).
set -eu
server="${1:-portfolio}"
shift || true
case "$server" in
  portfolio)   port="${MCP_PORTFOLIO_PORT:-8201}" ;;
  marketplace) port="${MCP_MARKETPLACE_PORT:-8202}" ;;
  workspace)   port="${MCP_WORKSPACE_PORT:-8203}" ;;
  *) echo "unknown MCP server '$server' (expected portfolio|marketplace|workspace)" >&2; exit 64 ;;
esac
export MCP_HOST="${MCP_HOST:-0.0.0.0}"
exec python -m "mcp_servers.${server}.server" --http --port "$port" "$@"
