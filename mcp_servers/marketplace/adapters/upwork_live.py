"""Live adapter for the official Upwork MCP server (Streamable HTTP via MultiServerMCPClient).

* OAuth bearer comes from the encrypted per-user token store; with redirect/callback handlers the
  SDK's OAuthClientProvider runs the full authorization-code + PKCE flow and refreshes tokens.
* Tool names are mapped through upwork_tool_map.yaml so the graph sees the same port methods.
* Writes only ever create drafts (enforced: mapped write tools must contain "draft").
* Reads are throttled: search_jobs results are cached for upwork.min_read_interval_s so a schedule
  never polls in a way that looks like scraping. No browser automation, no cookies.
"""
from __future__ import annotations

import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from mcp_servers.common.settings import repo_path, settings

from .base import MarketplaceError, MarketplaceUnavailable
from .token_store import EncryptedTokenStore, UserTokenStorage

WRITE_METHODS = {"create_proposal_draft", "submit_proposal", "send_message"}


def load_tool_map(path: str | Path | None = None) -> dict:
    p = Path(path) if path else repo_path(settings()["upwork"]["tool_map"])
    data = yaml.safe_load(p.read_text())
    for m in WRITE_METHODS:
        spec = data["methods"].get(m) or {}
        tool = spec.get("tool") or ""
        if not spec.get("draft_only") or "draft" not in tool:
            raise ValueError(f"write method {m} must map to a draft-only tool, got {tool!r}")
    return data


def _rename(obj: Any, fields: dict[str, str]) -> Any:
    if isinstance(obj, list):
        return [_rename(o, fields) for o in obj]
    if isinstance(obj, dict):
        return {fields.get(k, k): v for k, v in obj.items()}
    return obj


def _parse_result(res: Any) -> Any:
    sc = getattr(res, "structuredContent", None)
    if sc is not None:
        return sc.get("result", sc) if isinstance(sc, dict) and set(sc) == {"result"} else sc
    texts = [getattr(c, "text", "") for c in getattr(res, "content", []) or []]
    raw = "".join(texts)
    try:
        return json.loads(raw)
    except Exception:
        return {"text": raw}


class UpworkLiveAdapter:
    name = "upwork"

    def __init__(self, user_id: str, *, client_factory: Callable[[dict], Any] | None = None,
                 token_store: EncryptedTokenStore | None = None, tool_map: dict | None = None,
                 oauth_handlers: tuple[Callable, Callable] | None = None, clock=time.monotonic):
        cfg = settings()["upwork"]
        self.user_id = user_id
        self.url = os.environ.get("UPWORK_MCP_URL", cfg["url"])
        self.timeout_s = float(cfg["timeout_s"])
        self.min_read_interval_s = float(cfg["min_read_interval_s"])
        self.map = tool_map or load_tool_map()
        self._client_factory = client_factory
        self._token_store = token_store
        self._oauth_handlers = oauth_handlers
        self._clock = clock
        self._search_cache: dict[str, tuple[float, dict]] = {}

    # ----- connection -----
    async def _connection(self) -> dict:
        from datetime import timedelta

        conn: dict[str, Any] = {"transport": "streamable_http", "url": self.url,
                                "timeout": timedelta(seconds=self.timeout_s)}
        store = self._token_store or EncryptedTokenStore()
        storage = UserTokenStorage(store, self.user_id)
        if self._oauth_handlers:
            from mcp.client.auth import OAuthClientProvider
            from mcp.shared.auth import OAuthClientMetadata

            redirect_handler, callback_handler = self._oauth_handlers
            conn["auth"] = OAuthClientProvider(
                server_url=self.url,
                client_metadata=OAuthClientMetadata(
                    client_name="GigBid", redirect_uris=[os.environ.get(
                        "UPWORK_OAUTH_REDIRECT", "http://localhost:8000/api/auth/upwork/callback")],
                    grant_types=["authorization_code", "refresh_token"], response_types=["code"]),
                storage=storage, redirect_handler=redirect_handler, callback_handler=callback_handler)
        else:
            tokens = await storage.get_tokens()
            if tokens is None:
                raise MarketplaceUnavailable("Upwork account not connected for this user (no OAuth token)")
            conn["headers"] = {"Authorization": f"Bearer {tokens.access_token}"}
        return conn

    def _client(self, connections: dict) -> Any:
        if self._client_factory:
            return self._client_factory(connections)
        from langchain_mcp_adapters.client import MultiServerMCPClient

        return MultiServerMCPClient(connections)

    @asynccontextmanager
    async def _session(self):
        server = self.map.get("server", "upwork")
        client = self._client({server: await self._connection()})
        try:
            async with client.session(server) as session:
                yield session
        except MarketplaceUnavailable:
            raise
        except MarketplaceError:
            raise
        except Exception as e:
            raise MarketplaceUnavailable(f"Upwork MCP unreachable: {type(e).__name__}: {e}") from e

    async def verify_mapping(self) -> list[str]:
        """Return mapped tool names the live server does not expose."""
        async with self._session() as s:
            listed = await s.list_tools()
        names = {t.name for t in listed.tools}
        return sorted({spec["tool"] for spec in self.map["methods"].values()
                       if spec.get("tool") and spec["tool"] not in names})

    async def _call(self, method: str, args: dict) -> Any:
        spec = self.map["methods"].get(method) or {}
        tool = spec.get("tool")
        if not tool:
            raise MarketplaceError(f"{method} is not available on the Upwork MCP server", 501)
        mapped = {spec.get("args", {}).get(k, k): v for k, v in args.items()
                  if v is not None and k in spec.get("args", {})}
        async with self._session() as s:
            res = await s.call_tool(tool, mapped)
        if getattr(res, "isError", False):
            raise MarketplaceError(f"Upwork tool {tool} failed: {_parse_result(res)}")
        data = _parse_result(res)
        if spec.get("result_key") and isinstance(data, dict):
            data = data.get(spec["result_key"], [])
        return _rename(data, spec.get("fields", {}))

    # ----- reads -----
    async def health(self) -> dict:
        try:
            missing = await self.verify_mapping()
            return {"ok": True, "marketplace": self.name, "missing_tools": missing}
        except Exception as e:
            return {"ok": False, "marketplace": self.name, "error": str(e)}

    async def search_jobs(self, q: str = "", category: Optional[str] = None, skills: list[str] | None = None,
                          since: Optional[str] = None, limit: int = 20, offset: int = 0) -> dict:
        key = json.dumps([q, category, skills, since, limit, offset])
        now = self._clock()
        hit = self._search_cache.get(key)
        if hit and now - hit[0] < self.min_read_interval_s:
            return hit[1]
        jobs = await self._call("search_jobs", {"q": q, "category": category, "skills": skills,
                                                "limit": limit, "offset": offset})
        out = {"jobs": jobs, "total": len(jobs)}
        self._search_cache[key] = (now, out)
        return out

    async def get_job(self, job_id: str) -> dict:
        return await self._call("get_job", {"job_id": job_id})

    async def get_client_history(self, client_id: str) -> dict:
        d = await self._call("get_client_history", {"client_id": client_id})
        return {"client_id": client_id, **d}

    async def get_connects(self) -> dict:
        return await self._call("get_connects", {})

    async def list_threads(self) -> list[dict]:
        return await self._call("list_threads", {})

    async def list_messages(self, thread_id: str) -> list[dict]:
        return await self._call("list_messages", {"thread_id": thread_id})

    async def get_market_stats(self, category: str) -> dict:
        res = await self.search_jobs(category=category, limit=50)
        vals = {"hourly": [], "fixed": []}
        for j in res["jobs"]:
            hi = j.get("budget_max") or j.get("budget_min")
            if hi:
                vals["hourly" if j.get("budget_type") == "hourly" else "fixed"].append(float(hi))

        def q(xs: list[float]) -> dict:
            if not xs:
                return {"p25": None, "p50": None, "p75": None}
            xs = sorted(xs)
            return {f"p{p}": xs[min(len(xs) - 1, int(p / 100 * len(xs)))] for p in (25, 50, 75)}
        return {"category": category, "n": len(res["jobs"]), "hourly": q(vals["hourly"]), "fixed": q(vals["fixed"])}

    async def list_proposals(self) -> list[dict]:
        return await self._call("list_proposals", {})

    # ----- writes: drafts only -----
    async def create_proposal_draft(self, payload: dict, idempotency_key: str, dry_run: bool) -> dict:
        if dry_run:
            return {"status": "preview", "job_id": payload["job_id"], "preview": payload, "draft_id": None,
                    "note": "Live mode: on approval a draft is created on Upwork for you to confirm there."}
        d = await self._call("create_proposal_draft", payload)
        return {"status": "draft", "job_id": payload["job_id"], "preview": payload, "draft_id": d.get("draft_id"),
                "note": "Draft created on Upwork; confirm it on Upwork to send."}

    async def submit_proposal(self, payload: dict, idempotency_key: str, dry_run: bool) -> dict:
        if dry_run:
            return {"status": "would_submit", "job_id": payload["job_id"], "would_send": payload,
                    "note": "Live mode creates a draft on Upwork; you confirm it there."}
        d = await self._call("submit_proposal", payload)
        return {"status": "draft_created", "job_id": payload["job_id"], "proposal_id": d.get("draft_id"),
                "note": "Draft created on Upwork; confirm it on Upwork to submit."}

    async def send_message(self, thread_id: str, body: str, idempotency_key: str, dry_run: bool) -> dict:
        if dry_run:
            return {"status": "would_send", "thread_id": thread_id,
                    "would_send": {"thread_id": thread_id, "body": body}}
        d = await self._call("send_message", {"thread_id": thread_id, "body": body})
        return {"status": "draft_created", "thread_id": thread_id, "message_id": d.get("message_id"),
                "note": "Message draft created on Upwork; confirm it there to send."}
