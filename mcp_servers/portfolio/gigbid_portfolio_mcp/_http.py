"""HTTP exposure (vendored so this package installs standalone): bearer auth wrapped around the Streamable HTTP transport.

`build_http_app(mcp, server_name)` returns a plain ASGI app that
  * answers GET .../health without auth,
  * rejects requests without a valid `Authorization: Bearer <token>` (401),
  * stamps the authenticated user into the trusted header `x-gigbid-auth-user`,
  * forwards to the SDK's StreamableHTTPSessionManager (stateless, JSON responses).
The session manager is started lazily on first request, so the app also works when it is
mounted inside another ASGI app (e.g. FastAPI `app.mount("/mcp/marketplace", ...)`) whose
lifespan never reaches the sub-app.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

log = logging.getLogger(__name__)
# mcp 1.14 logs a harmless ClosedResourceError traceback after every stateless JSON response
logging.getLogger("mcp.server.streamable_http").addFilter(
    lambda r: "Error in message router" not in r.getMessage())
AUTH_USER_HEADER = b"x-gigbid-auth-user"


def load_tokens(server_name: str) -> dict[str, str]:
    """token -> user id. Env MCP_<NAME>_TOKENS='{"tok":"user"}' and/or MCP_<NAME>_TOKEN='tok'."""
    prefix = f"MCP_{server_name.upper()}_"
    tokens: dict[str, str] = {}
    raw = os.environ.get(prefix + "TOKENS")
    if raw:
        tokens.update(json.loads(raw))
    single = os.environ.get(prefix + "TOKEN")
    if single:
        tokens[single] = os.environ.get(prefix + "USER", "default")
    if not tokens:
        dev = f"dev-{server_name}-token"
        log.warning("%sTOKEN not set; accepting development token '%s' only", prefix, dev)
        tokens[dev] = "default"
    return tokens


class _LazySessionManager:
    def __init__(self, mcp: FastMCP):
        self.mcp = mcp
        self._sm: StreamableHTTPSessionManager | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready: asyncio.Event | None = None
        self._task: asyncio.Task | None = None
        self._stop: asyncio.Event | None = None

    async def ensure(self) -> StreamableHTTPSessionManager:
        loop = asyncio.get_running_loop()
        if self._sm is not None and self._loop is loop:
            await self._ready.wait()
            return self._sm
        # (re)create for this event loop; a session manager can only run once
        self._loop = loop
        self._sm = StreamableHTTPSessionManager(app=self.mcp._mcp_server, event_store=None,
                                                json_response=True, stateless=True)
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()
        sm, ready, stop = self._sm, self._ready, self._stop

        async def runner() -> None:
            async with sm.run():
                ready.set()
                await stop.wait()

        self._task = loop.create_task(runner())
        await ready.wait()
        return sm

    async def shutdown(self) -> None:
        if self._stop is not None:
            self._stop.set()
        if self._task is not None:
            try:
                await self._task
            except Exception:
                pass


class BearerAuthMCPApp:
    def __init__(self, mcp: FastMCP, server_name: str, tokens: dict[str, str] | None = None):
        self.server_name = server_name
        self.tokens = tokens if tokens is not None else load_tokens(server_name)
        self.manager = _LazySessionManager(mcp)

    def _authenticate(self, headers: list[tuple[bytes, bytes]]) -> str | None:
        auth = next((v.decode() for k, v in headers if k.lower() == b"authorization"), "")
        if not auth.lower().startswith("bearer "):
            return None
        presented = auth[7:].strip()
        for tok, user in self.tokens.items():
            if hmac.compare_digest(presented, tok):
                return user
        return None

    @staticmethod
    async def _json(send: Any, status: int, body: dict, extra: list | None = None) -> None:
        payload = json.dumps(body).encode()
        headers = [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]
        headers += extra or []
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": payload})

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "lifespan":
            while True:
                msg = await receive()
                if msg["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif msg["type"] == "lifespan.shutdown":
                    await self.manager.shutdown()
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] != "http":
            return
        path = scope.get("path", "")
        if path.rstrip("/").endswith("/health") and scope.get("method") == "GET":
            await self._json(send, 200, {"status": "ok", "server": self.server_name})
            return
        headers = [(k, v) for k, v in scope.get("headers", []) if k.lower() != AUTH_USER_HEADER]
        user = self._authenticate(headers)
        if user is None:
            await self._json(send, 401, {"error": "unauthorized", "detail": "missing or invalid bearer token"},
                             [(b"www-authenticate", b'Bearer realm="gigbid-mcp"')])
            return
        # the authenticated deployment may act for a named end user (multi-tenant API)
        on_behalf = next((v for k, v in headers if k.lower() == b"x-gigbid-user"), None)
        headers.append((AUTH_USER_HEADER, on_behalf or user.encode()))
        scope = dict(scope, headers=headers)
        sm = await self.manager.ensure()
        await sm.handle_request(scope, receive, send)


def build_http_app(mcp: FastMCP, server_name: str, tokens: dict[str, str] | None = None) -> BearerAuthMCPApp:
    return BearerAuthMCPApp(mcp, server_name, tokens)


def run_http(app: Any, port: int, host: str | None = None) -> None:
    import uvicorn

    uvicorn.run(app, host=host or os.environ.get("MCP_HOST", "127.0.0.1"), port=port)
