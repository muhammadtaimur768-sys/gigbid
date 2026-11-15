"""Repo entry point for the Portfolio MCP server; the implementation lives in the standalone
package `gigbid_portfolio_mcp` (see mcp_servers/portfolio/pyproject.toml)."""
from mcp_servers.portfolio.gigbid_portfolio_mcp.server import (  # noqa: F401
    build_http_app, get_case_study, list_skills, main, mcp, search_evidence)

if __name__ == "__main__":
    main()
