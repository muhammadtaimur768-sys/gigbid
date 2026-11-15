"""Thin marketplace client used by the API for reads (inbox, connects, threads, proposals) and the
health ping. Talks to GigSim over HTTP (GIGSIM_URL) or in-process when GigSim is mounted on this host.
The agent graph uses its own MCP-backed marketplace port; this client never submits proposals."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from ..config import get_settings
from ..integrations import optional
from ..tracing import current_trace_id

log = logging.getLogger("gigbid.marketplace")


class MarketplaceUnavailable(Exception):
    pass


_health_cache: dict[str, Any] = {"ts": 0.0, "ok": None, "detail": ""}
_override_ok: bool | None = None  # tests can force degraded mode


def force_status(ok: bool | None) -> None:
    global _override_ok
    _override_ok = ok
    _health_cache["ts"] = 0.0


def default_token(persona: str | None) -> str:
    return f"gs-{persona or 'aiml'}-token"


def _client(timeout: float = 10.0) -> httpx.AsyncClient:
    s = get_settings()
    headers = {"X-Trace-Id": current_trace_id()}
    if s.mount_gigsim:  # same host: call the mounted GigSim in-process
        app = optional("gigsim.app", "app")
        if app is not None:
            return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://gigsim",
                                     timeout=timeout, headers=headers)
    if s.gigsim_url:
        return httpx.AsyncClient(base_url=s.gigsim_url.rstrip("/"), timeout=timeout, headers=headers)
    app = optional("gigsim.app", "app")
    if app is not None:
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://gigsim",
                                 timeout=timeout, headers=headers)
    return httpx.AsyncClient(base_url="http://localhost:8100", timeout=timeout, headers=headers)


async def _request(method: str, path: str, token: str | None = None, retries: int = 2, **kw) -> Any:
    if _override_ok is False:
        raise MarketplaceUnavailable("marketplace forced unavailable")
    headers = kw.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with _client() as c:
                r = await c.request(method, path, headers=headers, **kw)
            if r.status_code == 429 or r.status_code >= 500:
                last = MarketplaceUnavailable(f"HTTP {r.status_code}")
                wait = float(r.headers.get("retry-after", 0) or 0) if r.status_code == 429 else 0.3 * (2 ** attempt)
                await asyncio.sleep(min(wait, 2.0))
                continue
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            raise MarketplaceUnavailable(f"HTTP {e.response.status_code}") from e
        except (httpx.TransportError, OSError) as e:
            last = MarketplaceUnavailable(str(e) or type(e).__name__)
            await asyncio.sleep(0.2 * (2 ** attempt))
    raise last or MarketplaceUnavailable("unknown error")


async def ping(force: bool = False) -> dict:
    s = get_settings()
    if _override_ok is not None:
        return {"ok": _override_ok, "detail": "forced"}
    now = time.monotonic()
    if not force and _health_cache["ok"] is not None and now - _health_cache["ts"] < s.health_cache_s:
        return {"ok": _health_cache["ok"], "detail": _health_cache["detail"]}
    ok, detail = False, ""
    try:
        async with _client(timeout=3.0) as c:
            r = await c.get("/health")
        ok = r.status_code == 200
        detail = "" if ok else f"HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001
        detail = type(e).__name__
    _health_cache.update(ts=now, ok=ok, detail=detail)
    return {"ok": ok, "detail": detail}


async def list_jobs(token: str, q: str = "", category: str | None = None, skills: list[str] | None = None,
                    limit: int = 50, offset: int = 0) -> dict:
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if q:
        params["q"] = q
    if category:
        params["category"] = category
    if skills:
        params["skills"] = ",".join(skills)
    return await _request("GET", "/jobs", token, params=params)


async def get_job(token: str, job_id: str) -> dict:
    return await _request("GET", f"/jobs/{job_id}", token)


async def get_connects(token: str) -> dict:
    return await _request("GET", "/connects", token)


async def list_proposals(token: str) -> list[dict]:
    data = await _request("GET", "/proposals", token)
    return data.get("proposals", data) if isinstance(data, dict) else data


async def list_threads(token: str) -> list[dict]:
    data = await _request("GET", "/threads", token)
    return data.get("threads", data) if isinstance(data, dict) else data


async def list_messages(token: str, thread_id: str) -> list[dict]:
    data = await _request("GET", f"/threads/{thread_id}/messages", token)
    return data.get("messages", data) if isinstance(data, dict) else data


async def get_events(token: str, since: str | None = None) -> list[dict]:
    data = await _request("GET", "/events", token, params={"since": since} if since else None)
    return data.get("events", data) if isinstance(data, dict) else data


async def get_client_history(token: str, client_id: str) -> dict:
    return await _request("GET", f"/clients/{client_id}/history", token)
