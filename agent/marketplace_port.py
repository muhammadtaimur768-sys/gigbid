"""The single port through which the agent reads from and writes to a marketplace.

Implementations:
  * `MCPMarketplacePort` (default): calls the Marketplace MCP server tools (GigSim or live Upwork adapter
    behind it) through agent/mcp_client.py with per-agent allowlists.
  * `GigSimHTTPPort`: talks to the GigSim REST API directly (an httpx client or a FastAPI TestClient);
    used by integration tests and offline evals so nothing needs network ports.
  * `InMemoryMarketplace`: a tiny fake for unit tests.
Select with env `MARKETPLACE_PORT=mcp|gigsim_http|memory`.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from typing import Any, Protocol, runtime_checkable

from agent.settings import cfg


class MarketplaceUnavailable(RuntimeError):
    """Transient: the marketplace (or its MCP server) cannot be reached → retry, then degraded mode."""


class MarketplaceError(RuntimeError):
    """Non-transient error from the marketplace (validation, 402 not enough connects, 404...)."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


@runtime_checkable
class MarketplacePort(Protocol):
    name: str

    def search_jobs(self, q: str = "", category: str | None = None, skills: list[str] | None = None,
                    since: str | None = None, limit: int = 20, offset: int = 0) -> dict: ...
    def get_job(self, job_id: str) -> dict: ...
    def get_client_history(self, client_id: str) -> dict: ...
    def get_connects_balance(self) -> dict: ...
    def get_market_stats(self, category: str) -> dict: ...
    def submit_proposal(self, job_id: str, cover_letter: str, screening_answers: list[dict], bid_amount: float,
                        idempotency_key: str, dry_run: bool = False) -> dict: ...
    def list_proposals(self) -> list[dict]: ...
    def list_threads(self) -> list[dict]: ...
    def list_messages(self, thread_id: str) -> list[dict]: ...
    def send_message(self, thread_id: str, body: str, idempotency_key: str, dry_run: bool = False) -> dict: ...


# ---------------------------------------------------------------- MCP
class MCPMarketplacePort:
    name = "mcp"

    def __init__(self, trace_id: str | None = None, thread_id: str = ""):
        self.trace_id = trace_id
        self.thread_id = thread_id

    def _call(self, agent: str, tool: str, args: dict) -> Any:
        from agent.mcp_client import MCPToolError, call_tool

        try:
            return call_tool(agent, "marketplace", tool, args, trace_id=self.trace_id, thread_id=self.thread_id)
        except MCPToolError as exc:
            msg = exc.message.lower()
            if any(s in msg for s in ("unavailable", "timeout", "rate limit", "429", "502", "503", "500", "connect")):
                raise MarketplaceUnavailable(str(exc)) from exc
            raise MarketplaceError(str(exc)) from exc
        except (OSError, TimeoutError) as exc:
            raise MarketplaceUnavailable(str(exc)) from exc

    def search_jobs(self, q="", category=None, skills=None, since=None, limit=20, offset=0):
        return self._call("scout", "search_jobs", {"q": q, "category": category, "skills": skills or [],
                                                   "since": since, "limit": limit, "offset": offset})

    def get_job(self, job_id):
        return self._call("scout", "get_job", {"job_id": job_id})

    def get_client_history(self, client_id):
        return self._call("scout", "get_client_history", {"client_id": client_id})

    def get_connects_balance(self):
        return self._call("pricing", "get_connects_balance", {})

    def get_market_stats(self, category):
        return self._call("pricing", "get_market_stats", {"category": category})

    def submit_proposal(self, job_id, cover_letter, screening_answers, bid_amount, idempotency_key, dry_run=False):
        agent = "preview" if dry_run else "submit"
        return self._call(agent, "submit_proposal", {
            "job_id": job_id, "cover_letter": cover_letter, "screening_answers": screening_answers,
            "bid_amount": bid_amount, "idempotency_key": idempotency_key, "dry_run": dry_run})

    def list_proposals(self):
        r = self._call("outcomes", "list_proposals", {})
        return r.get("proposals", r) if isinstance(r, dict) else r

    def list_threads(self):
        r = self._call("liaison", "list_threads", {})
        return r.get("threads", r) if isinstance(r, dict) else r

    def list_messages(self, thread_id):
        r = self._call("liaison", "list_messages", {"thread_id": thread_id})
        return r.get("messages", r) if isinstance(r, dict) else r

    def send_message(self, thread_id, body, idempotency_key, dry_run=False):
        return self._call("liaison", "send_message", {"thread_id": thread_id, "body": body,
                                                      "idempotency_key": idempotency_key, "dry_run": dry_run})


# ---------------------------------------------------------------- GigSim REST
class GigSimHTTPPort:
    """Direct GigSim REST client. `client` may be an httpx.Client or a FastAPI TestClient."""

    name = "gigsim_http"

    def __init__(self, base_url: str | None = None, token: str | None = None, client=None,
                 max_retries: int = 3, backoff_s: float = 0.3):
        import httpx

        self.base_url = (base_url or os.environ.get("GIGSIM_URL") or "http://localhost:8100").rstrip("/")
        self.token = token or os.environ.get("GIGSIM_TOKEN") or "gs-aiml-token"
        self.client = client or httpx.Client(base_url=self.base_url, timeout=10.0)
        self.max_retries = max_retries
        self.backoff_s = backoff_s

    def _req(self, method: str, path: str, **kw) -> Any:
        import httpx

        headers = {"Authorization": f"Bearer {self.token}"}
        last = None
        for attempt in range(self.max_retries + 1):
            try:
                r = self.client.request(method, path, headers=headers, **kw)
            except (httpx.TransportError, OSError) as exc:
                last = MarketplaceUnavailable(f"{method} {path}: {exc}")
            else:
                if r.status_code == 429 or r.status_code >= 500:
                    last = MarketplaceUnavailable(f"{method} {path}: HTTP {r.status_code}")
                    wait = float(r.headers.get("Retry-After", 0) or 0) if r.status_code == 429 else 0
                    time.sleep(min(max(wait, self.backoff_s * (2 ** attempt)), 5.0))
                    continue
                if r.status_code >= 400:
                    raise MarketplaceError(f"{method} {path}: HTTP {r.status_code} {r.text[:200]}", r.status_code)
                return r.json()
            time.sleep(min(self.backoff_s * (2 ** attempt), 5.0))
        raise last or MarketplaceUnavailable(path)

    def search_jobs(self, q="", category=None, skills=None, since=None, limit=20, offset=0):
        params = {"q": q, "limit": limit, "offset": offset}
        if category:
            params["category"] = category
        if skills:
            params["skills"] = ",".join(skills)
        if since:
            params["since"] = since
        return self._req("GET", "/jobs", params=params)

    def get_job(self, job_id):
        return self._req("GET", f"/jobs/{job_id}")

    def get_client_history(self, client_id):
        return self._req("GET", f"/clients/{client_id}/history")

    def get_connects_balance(self):
        return self._req("GET", "/connects")

    def get_market_stats(self, category):
        return self._req("GET", "/market/stats", params={"category": category})

    def submit_proposal(self, job_id, cover_letter, screening_answers, bid_amount, idempotency_key, dry_run=False):
        return self._req("POST", "/proposals", json={
            "job_id": job_id, "cover_letter": cover_letter, "screening_answers": screening_answers,
            "bid_amount": bid_amount, "idempotency_key": idempotency_key, "dry_run": dry_run})

    def list_proposals(self):
        r = self._req("GET", "/proposals")
        return r.get("proposals", r) if isinstance(r, dict) else r

    def list_threads(self):
        r = self._req("GET", "/threads")
        return r.get("threads", r) if isinstance(r, dict) else r

    def list_messages(self, thread_id):
        r = self._req("GET", f"/threads/{thread_id}/messages")
        return r.get("messages", r) if isinstance(r, dict) else r

    def send_message(self, thread_id, body, idempotency_key, dry_run=False):
        if dry_run:
            return {"status": "would_send", "thread_id": thread_id, "would_send": {"body": body}}
        return self._req("POST", f"/threads/{thread_id}/messages", json={"body": body, "idempotency_key": idempotency_key})


# ---------------------------------------------------------------- in-memory fake
class InMemoryMarketplace:
    name = "memory"

    def __init__(self, jobs: list[dict] | None = None, clients: dict | None = None, balance: int = 80,
                 stats: dict | None = None, threads: dict | None = None, fail_times: int = 0):
        self.jobs = {j["id"]: j for j in (jobs or [])}
        self.clients = clients or {}
        self.balance = balance
        self.stats = stats or {}
        self.proposals: dict[str, dict] = {}       # idempotency_key -> result
        self.submissions: list[dict] = []          # every real submission (for exactly-once tests)
        self.threads = threads or {}               # thread_id -> {"job_id", "messages": [...]}
        self.sent: dict[str, dict] = {}
        self.fail_times = fail_times               # raise MarketplaceUnavailable this many times on submit
        self._lock = threading.Lock()

    def search_jobs(self, q="", category=None, skills=None, since=None, limit=20, offset=0):
        jobs = [j for j in self.jobs.values() if (not category or j.get("category") == category)
                and (not q or q.lower() in (j.get("title", "") + j.get("description", "")).lower())]
        return {"jobs": jobs[offset:offset + limit], "total": len(jobs)}

    def get_job(self, job_id):
        if job_id not in self.jobs:
            raise MarketplaceError(f"job {job_id} not found", 404)
        return self.jobs[job_id]

    def get_client_history(self, client_id):
        return self.clients.get(client_id) or {"client_id": client_id, "avg_rating": 4.6, "payment_verified": True,
                                               "hires": 5, "jobs_posted": 8, "total_spent": 12000, "reviews": []}

    def get_connects_balance(self):
        return {"freelancer_id": "fl-test", "balance": self.balance, "weekly_spent": 0}

    def get_market_stats(self, category):
        return self.stats.get(category) or {"category": category, "n": 0, "hourly": {"p25": 35, "p50": 55, "p75": 80},
                                            "fixed": {"p25": 400, "p50": 900, "p75": 2000}}

    def submit_proposal(self, job_id, cover_letter, screening_answers, bid_amount, idempotency_key, dry_run=False):
        from agent.policy import connects_cost

        job = self.jobs.get(job_id, {"connects_cost": 4})
        cost = connects_cost(job)
        if dry_run:
            return {"status": "would_submit", "job_id": job_id, "connects_cost": cost,
                    "balance_after": self.balance - cost, "dry_run": True, "marketplace": self.name,
                    "would_send": {"job_id": job_id, "cover_letter": cover_letter,
                                   "screening_answers": screening_answers, "bid_amount": bid_amount}}
        with self._lock:
            if self.fail_times > 0:
                self.fail_times -= 1
                raise MarketplaceUnavailable("simulated outage")
            if idempotency_key in self.proposals:
                return {**self.proposals[idempotency_key], "replayed": True}
            if cost > self.balance:
                raise MarketplaceError("not enough connects", 402)
            self.balance -= cost
            res = {"status": "submitted", "proposal_id": f"prop-{uuid.uuid4().hex[:8]}", "job_id": job_id,
                   "connects_spent": cost, "balance_after": self.balance, "marketplace": self.name}
            self.proposals[idempotency_key] = res
            self.submissions.append({"job_id": job_id, "cover_letter": cover_letter, "bid_amount": bid_amount,
                                     "idempotency_key": idempotency_key, **res})
            return res

    def list_proposals(self):
        return [{"proposal_id": s["proposal_id"], "job_id": s["job_id"], "status": "submitted"} for s in self.submissions]

    def list_threads(self):
        return [{"thread_id": t, "job_id": v.get("job_id"), "unread": 1} for t, v in self.threads.items()]

    def list_messages(self, thread_id):
        return list((self.threads.get(thread_id) or {}).get("messages", []))

    def send_message(self, thread_id, body, idempotency_key, dry_run=False):
        if dry_run:
            return {"status": "would_send", "thread_id": thread_id, "would_send": {"body": body}}
        with self._lock:
            if idempotency_key in self.sent:
                return {**self.sent[idempotency_key], "replayed": True}
            mid = f"msg-{uuid.uuid4().hex[:8]}"
            self.threads.setdefault(thread_id, {"messages": []})["messages"].append(
                {"id": mid, "sender": "freelancer", "body": body})
            res = {"status": "sent", "thread_id": thread_id, "message_id": mid}
            self.sent[idempotency_key] = res
            return res


_default: MarketplacePort | None = None


def get_marketplace(trace_id: str | None = None, thread_id: str = "") -> MarketplacePort:
    """Port selected by env MARKETPLACE_PORT (mcp default)."""
    global _default
    mode = os.environ.get("MARKETPLACE_PORT", cfg("marketplace_port", default="mcp"))
    if mode == "gigsim_http":
        return GigSimHTTPPort()
    if mode == "memory":
        if _default is None:
            _default = InMemoryMarketplace()
        return _default
    return MCPMarketplacePort(trace_id=trace_id, thread_id=thread_id)
