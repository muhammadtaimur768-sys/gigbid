"""Idempotency store: (user, tool, key) -> first result. Replays return the stored result.

Backed by a JSON file so a server restart does not allow a double submit.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

from .settings import repo_path, settings


class IdempotencyConflict(Exception):
    """Same key reused with different arguments."""


class IdempotencyStore:
    def __init__(self, path: str | Path | None = None, persist: bool = True):
        self.path = Path(path) if path else repo_path(
            os.environ.get("MCP_IDEMPOTENCY_PATH", settings()["idempotency"]["path"]))
        self.persist = persist
        self._lock = threading.Lock()
        self._data: dict[str, dict] = {}
        if persist and self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
            except Exception:
                self._data = {}

    @staticmethod
    def _k(user: str, tool: str, key: str) -> str:
        return f"{user}|{tool}|{key}"

    @staticmethod
    def fingerprint(args: dict) -> str:
        clean = {k: v for k, v in args.items() if k not in ("idempotency_key", "dry_run")}
        return hashlib.sha256(json.dumps(clean, sort_keys=True, default=str).encode()).hexdigest()

    def get(self, user: str, tool: str, key: str, args: dict) -> Any | None:
        rec = self._data.get(self._k(user, tool, key))
        if rec is None:
            return None
        if rec["fp"] != self.fingerprint(args):
            raise IdempotencyConflict(
                f"idempotency_key '{key}' was already used for {tool} with different arguments")
        return rec["result"]

    def put(self, user: str, tool: str, key: str, args: dict, result: Any) -> None:
        with self._lock:
            self._data[self._k(user, tool, key)] = {"fp": self.fingerprint(args), "result": result}
            if self.persist:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(self._data, default=str))
                tmp.replace(self.path)
