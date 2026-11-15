"""Per-user token-bucket rate limiter (in process)."""
from __future__ import annotations

import threading
import time

from .settings import settings


class RateLimited(Exception):
    def __init__(self, retry_after: float):
        super().__init__(f"rate limit exceeded; retry after {retry_after:.1f}s")
        self.retry_after = retry_after


class TokenBucketLimiter:
    def __init__(self, capacity: int | None = None, refill_per_minute: float | None = None):
        cfg = settings()["rate_limit"]
        self.capacity = float(capacity if capacity is not None else cfg["capacity"])
        self.rate = float(refill_per_minute if refill_per_minute is not None else cfg["refill_per_minute"]) / 60.0
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def acquire(self, user: str, cost: float = 1.0) -> None:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(user, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - last) * self.rate)
            if tokens < cost:
                self._buckets[user] = (tokens, now)
                raise RateLimited((cost - tokens) / self.rate if self.rate else 60.0)
            self._buckets[user] = (tokens - cost, now)

    def remaining(self, user: str) -> float:
        tokens, _ = self._buckets.get(user, (self.capacity, time.monotonic()))
        return tokens
