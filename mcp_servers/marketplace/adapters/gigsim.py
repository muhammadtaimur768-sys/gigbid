"""GigSim adapter: httpx client with timeouts, bounded retries and exponential backoff.

Retries on connection errors, timeouts, 429 (honouring Retry-After) and 5xx. Writes are safe to
retry because every POST carries the caller's idempotency_key, which GigSim de-duplicates.
After the retry budget is spent it raises MarketplaceUnavailable.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import threading
from pathlib import Path
from typing import Any, Optional

import httpx

from mcp_servers.common.settings import repo_path, settings

from .base import InsufficientConnects, MarketplaceError, MarketplaceNotFound, MarketplaceUnavailable

RETRYABLE = {429, 500, 502, 503, 504}


class GigSimAdapter:
    name = "gigsim"

    def __init__(self, base_url: str | None = None, token: str | None = None, *,
                 transport: httpx.AsyncBaseTransport | None = None, timeout_s: float | None = None,
                 max_retries: int | None = None, backoff_base_s: float | None = None,
                 backoff_max_s: float | None = None, drafts_path: str | Path | None = None,
                 sleep=asyncio.sleep):
        cfg = settings()["gigsim"]
        self.base_url = (base_url or os.environ.get(cfg["url_env"], cfg["default_url"])).rstrip("/")
        self.token = token or os.environ.get(cfg["token_env"], cfg["default_token"])
        self.timeout_s = timeout_s if timeout_s is not None else float(cfg["timeout_s"])
        self.max_retries = max_retries if max_retries is not None else int(cfg["max_retries"])
        self.backoff_base_s = backoff_base_s if backoff_base_s is not None else float(cfg["backoff_base_s"])
        self.backoff_max_s = backoff_max_s if backoff_max_s is not None else float(cfg["backoff_max_s"])
        self._transport = transport
        self._sleep = sleep
        self.drafts_path = Path(drafts_path) if drafts_path else repo_path("data/processed/proposal_drafts.json")
        self._lock = threading.Lock()
        self.attempts_log: list[int] = []  # status per attempt, for tests/diagnostics

    # ---------------- HTTP core ----------------
    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, transport=self._transport,
                                 timeout=httpx.Timeout(self.timeout_s),
                                 headers={"Authorization": f"Bearer {self.token}"})

    def _backoff(self, attempt: int, retry_after: Optional[str]) -> float:
        if retry_after:
            try:
                return min(float(retry_after), self.backoff_max_s)
            except ValueError:
                pass
        delay = self.backoff_base_s * (2 ** attempt)
        return min(delay, self.backoff_max_s) * (0.5 + random.random() / 2)

    async def _request(self, method: str, path: str, **kw: Any) -> Any:
        last_err = "unknown"
        retry_after_hint = None
        async with self._client() as client:
            for attempt in range(self.max_retries + 1):
                try:
                    resp = await client.request(method, path, **kw)
                except (httpx.TimeoutException, httpx.TransportError) as e:
                    self.attempts_log.append(0)
                    last_err = f"{type(e).__name__}: {e}"
                    if attempt < self.max_retries:
                        await self._sleep(self._backoff(attempt, None))
                        continue
                    break
                self.attempts_log.append(resp.status_code)
                if resp.status_code in RETRYABLE:
                    retry_after_hint = resp.headers.get("Retry-After")
                    last_err = f"HTTP {resp.status_code}"
                    if attempt < self.max_retries:
                        await self._sleep(self._backoff(attempt, retry_after_hint))
                        continue
                    break
                if resp.status_code == 404:
                    raise MarketplaceNotFound(f"not found: {path}", 404)
                if resp.status_code == 402:
                    raise InsufficientConnects(_detail(resp) or "not enough Connects", 402)
                if resp.status_code >= 400:
                    raise MarketplaceError(f"GigSim {resp.status_code}: {_detail(resp)}", resp.status_code)
                return resp.json()
        ra = float(retry_after_hint) if retry_after_hint and retry_after_hint.replace(".", "").isdigit() else None
        raise MarketplaceUnavailable(f"GigSim unavailable after {self.max_retries + 1} attempts ({last_err})", ra)

    # ---------------- reads ----------------
    async def health(self) -> dict:
        try:
            async with self._client() as client:
                r = await client.get("/health", timeout=min(self.timeout_s, 3.0))
            return {"ok": r.status_code == 200, "marketplace": self.name, "status": r.status_code}
        except Exception as e:  # health must never raise
            return {"ok": False, "marketplace": self.name, "error": f"{type(e).__name__}"}

    async def search_jobs(self, q: str = "", category: Optional[str] = None, skills: list[str] | None = None,
                          since: Optional[str] = None, limit: int = 20, offset: int = 0) -> dict:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if q:
            params["q"] = q
        if category:
            params["category"] = category
        if skills:
            params["skills"] = ",".join(skills)
        if since:
            params["since"] = since
        return await self._request("GET", "/jobs", params=params)

    async def get_job(self, job_id: str) -> dict:
        return await self._request("GET", f"/jobs/{job_id}")

    async def get_client_history(self, client_id: str) -> dict:
        return await self._request("GET", f"/clients/{client_id}/history")

    async def get_connects(self) -> dict:
        return await self._request("GET", "/connects")

    async def list_threads(self) -> list[dict]:
        data = await self._request("GET", "/threads")
        return data.get("threads", data) if isinstance(data, dict) else data

    async def list_messages(self, thread_id: str) -> list[dict]:
        data = await self._request("GET", f"/threads/{thread_id}/messages")
        return data.get("messages", data) if isinstance(data, dict) else data

    async def get_market_stats(self, category: str) -> dict:
        return await self._request("GET", "/market/stats", params={"category": category})

    async def list_proposals(self) -> list[dict]:
        data = await self._request("GET", "/proposals")
        return data.get("proposals", data) if isinstance(data, dict) else data

    # ---------------- writes ----------------
    def _load_drafts(self) -> dict:
        if self.drafts_path.exists():
            try:
                return json.loads(self.drafts_path.read_text())
            except Exception:
                return {}
        return {}

    async def create_proposal_draft(self, payload: dict, idempotency_key: str, dry_run: bool) -> dict:
        """GigSim has no draft endpoint: drafts are stored locally; cost comes from a GigSim dry run."""
        preview = await self._request("POST", "/proposals", json={**payload, "idempotency_key": idempotency_key,
                                                                    "dry_run": True})
        draft_id = "draft-" + hashlib.sha256(f"{self.token}|{idempotency_key}".encode()).hexdigest()[:12]
        out = {"draft_id": None if dry_run else draft_id, "status": "preview" if dry_run else "draft",
               "job_id": payload["job_id"], "preview": payload,
               "connects_cost": preview.get("connects_cost"), "balance_after": preview.get("balance_after")}
        if not dry_run:
            with self._lock:
                drafts = self._load_drafts()
                drafts[draft_id] = {**out, "idempotency_key": idempotency_key}
                self.drafts_path.parent.mkdir(parents=True, exist_ok=True)
                self.drafts_path.write_text(json.dumps(drafts, default=str))
        return out

    async def submit_proposal(self, payload: dict, idempotency_key: str, dry_run: bool) -> dict:
        data = await self._request("POST", "/proposals", json={**payload, "idempotency_key": idempotency_key,
                                                                "dry_run": dry_run})
        if dry_run:
            return {"status": "would_submit", "job_id": payload["job_id"],
                    "would_send": data.get("would_send", payload), "connects_cost": data.get("connects_cost"),
                    "balance_after": data.get("balance_after")}
        return {"status": "submitted", "job_id": payload["job_id"], "proposal_id": data.get("proposal_id"),
                "connects_spent": data.get("connects_spent"), "connects_cost": data.get("connects_spent"),
                "balance_after": data.get("balance_after")}

    async def send_message(self, thread_id: str, body: str, idempotency_key: str, dry_run: bool) -> dict:
        if dry_run:
            return {"status": "would_send", "thread_id": thread_id,
                    "would_send": {"thread_id": thread_id, "body": body}}
        data = await self._request("POST", f"/threads/{thread_id}/messages",
                                   json={"body": body, "idempotency_key": idempotency_key})
        return {"status": "sent", "thread_id": thread_id, "message_id": data.get("id")}


def _detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        return str(body.get("detail", body))
    except Exception:
        return resp.text[:200]
