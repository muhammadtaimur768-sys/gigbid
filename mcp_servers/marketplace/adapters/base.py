"""Marketplace adapter contract shared by the GigSim and Upwork-live adapters."""
from __future__ import annotations

from typing import Any, Optional, Protocol


class MarketplaceError(Exception):
    """Non-retryable error returned by the marketplace (4xx)."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class MarketplaceNotFound(MarketplaceError):
    pass


class InsufficientConnects(MarketplaceError):
    pass


class MarketplaceUnavailable(Exception):
    """Marketplace unreachable after bounded retries (timeouts, 429 storm, 5xx). Callers enter degraded mode."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class MarketplaceAdapter(Protocol):
    name: str

    async def health(self) -> dict[str, Any]: ...
    async def search_jobs(self, q: str = "", category: Optional[str] = None, skills: list[str] | None = None,
                          since: Optional[str] = None, limit: int = 20, offset: int = 0) -> dict: ...
    async def get_job(self, job_id: str) -> dict: ...
    async def get_client_history(self, client_id: str) -> dict: ...
    async def get_connects(self) -> dict: ...
    async def list_threads(self) -> list[dict]: ...
    async def list_messages(self, thread_id: str) -> list[dict]: ...
    async def get_market_stats(self, category: str) -> dict: ...
    async def list_proposals(self) -> list[dict]: ...
    async def create_proposal_draft(self, payload: dict, idempotency_key: str, dry_run: bool) -> dict: ...
    async def submit_proposal(self, payload: dict, idempotency_key: str, dry_run: bool) -> dict: ...
    async def send_message(self, thread_id: str, body: str, idempotency_key: str, dry_run: bool) -> dict: ...
