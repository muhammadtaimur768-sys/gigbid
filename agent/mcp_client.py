"""MCP client used by the agent, with per-agent tool allowlists.

Transport per server:
  * HTTP: env `MCP_<SERVER>_URL` set → streamable HTTP via langchain-mcp-adapters' MultiServerMCPClient.
  * In-process (default): the FastMCP server module is imported and connected through an in-memory
    transport, so no network ports are needed.
The trace id travels in `_meta.trace_id` (and as `X-Trace-Id` on HTTP).
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import threading
from typing import Any

from agent.settings import cfg
from agent.tracing import emit, mask_pii

TOOL_ALLOWLIST: dict[str, list[str]] = dict(cfg("tools", "allowlist", default={}) or {})
SERVERS: dict[str, dict] = dict(cfg("tools", "servers", default={}) or {})


class ToolNotAllowed(PermissionError):
    pass


class MCPToolError(RuntimeError):
    def __init__(self, tool: str, message: str):
        super().__init__(f"{tool}: {message}")
        self.tool = tool
        self.message = message


class _LoopThread:
    """One background event loop so sync graph nodes can call async MCP sessions from any context."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True, name="gigbid-mcp-loop")
        self.thread.start()

    def run(self, coro, timeout: float | None = 60):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)


_loop: _LoopThread | None = None
_loop_lock = threading.Lock()


def _bg() -> _LoopThread:
    global _loop
    with _loop_lock:
        if _loop is None:
            _loop = _LoopThread()
        return _loop


def check_allowed(agent: str, tool: str) -> None:
    allowed = TOOL_ALLOWLIST.get(agent)
    if allowed is None or tool not in allowed:
        raise ToolNotAllowed(f"agent '{agent}' may not call tool '{tool}'")


def server_url(server: str) -> str | None:
    env = (SERVERS.get(server) or {}).get("url_env") or f"MCP_{server.upper()}_URL"
    return os.environ.get(env) or None


def _parse_result(tool: str, res) -> Any:
    if getattr(res, "isError", False):
        msg = " ".join(getattr(c, "text", "") for c in (res.content or []))
        raise MCPToolError(tool, msg or "tool error")
    sc = getattr(res, "structuredContent", None)
    if sc is not None:
        if isinstance(sc, dict) and set(sc) == {"result"}:
            return sc["result"]
        return sc
    texts = [getattr(c, "text", "") for c in (res.content or []) if getattr(c, "type", "") == "text"]
    if len(texts) == 1:
        try:
            return json.loads(texts[0])
        except json.JSONDecodeError:
            return texts[0]
    out = []
    for t in texts:
        try:
            out.append(json.loads(t))
        except json.JSONDecodeError:
            out.append(t)
    return out


async def _call_on_session(session, tool: str, args: dict, trace_id: str | None):
    from mcp import types

    params = types.CallToolRequestParams(name=tool, arguments=args)
    if trace_id:
        params = types.CallToolRequestParams(name=tool, arguments=args, _meta={"trace_id": trace_id})
    req = types.ClientRequest(types.CallToolRequest(method="tools/call", params=params))
    return await session.send_request(req, types.CallToolResult)


async def _call_inprocess(server: str, tool: str, args: dict, trace_id: str | None):
    from mcp.shared.memory import create_connected_server_and_client_session

    mod = importlib.import_module(SERVERS[server]["module"])
    fast = getattr(mod, "mcp")
    async with create_connected_server_and_client_session(fast._mcp_server) as session:
        return await _call_on_session(session, tool, args, trace_id)


async def _call_http(server: str, url: str, tool: str, args: dict, trace_id: str | None):
    from langchain_mcp_adapters.client import MultiServerMCPClient

    headers = {}
    if trace_id:
        headers["X-Trace-Id"] = trace_id
    tok_env = (SERVERS.get(server) or {}).get("token_env")
    if tok_env and os.environ.get(tok_env):
        headers["Authorization"] = f"Bearer {os.environ[tok_env]}"
    client = MultiServerMCPClient({server: {"url": url, "transport": "streamable_http", "headers": headers}})
    async with client.session(server) as session:
        return await _call_on_session(session, tool, args, trace_id)


def call_tool(agent: str, server: str, tool: str, args: dict | None = None, *, trace_id: str | None = None,
              thread_id: str = "", timeout: float = 60) -> Any:
    """Allowlist-checked, traced, synchronous MCP tool call."""
    import time

    check_allowed(agent, tool)
    args = {k: v for k, v in (args or {}).items() if v is not None}
    url = server_url(server)
    t0 = time.perf_counter()
    coro = _call_http(server, url, tool, args, trace_id) if url else _call_inprocess(server, tool, args, trace_id)
    try:
        res = _bg().run(coro, timeout=timeout)
        out = _parse_result(tool, res)
    except Exception as exc:
        emit(trace_id or "", thread_id, agent, "tool_error",
             {"server": server, "tool": tool, "args": mask_pii(args), "error": str(exc)[:500]},
             latency_ms=(time.perf_counter() - t0) * 1000)
        raise
    emit(trace_id or "", thread_id, agent, "tool_call",
         {"server": server, "tool": tool, "args": mask_pii(args), "result": mask_pii(out) if not isinstance(out, (dict, list)) or len(json.dumps(out, default=str)) < 4000 else "[large result]"},
         latency_ms=(time.perf_counter() - t0) * 1000)
    return out


async def acall_tool(agent: str, server: str, tool: str, args: dict | None = None, *, trace_id: str | None = None) -> Any:
    check_allowed(agent, tool)
    url = server_url(server)
    res = await (_call_http(server, url, tool, args or {}, trace_id) if url
                 else _call_inprocess(server, tool, args or {}, trace_id))
    return _parse_result(tool, res)


async def load_agent_tools(agent: str, server: str):
    """LangChain tools for one agent, filtered by its allowlist (used by the ReAct/supervisor baselines)."""
    url = server_url(server)
    if url:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        client = MultiServerMCPClient({server: {"url": url, "transport": "streamable_http"}})
        tools = await client.get_tools(server_name=server)
    else:
        raise RuntimeError("load_agent_tools needs an HTTP MCP server (set MCP_<SERVER>_URL)")
    allowed = set(TOOL_ALLOWLIST.get(agent, []))
    return [t for t in tools if t.name in allowed]
