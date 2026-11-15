"""Append-only JSONL audit log with PII masking.

Each line: {ts, server, user, tool, args (masked), result (masked, truncated), status, trace_id, latency_ms}.
The file is only ever opened in append mode.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .settings import repo_path, settings

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
_SECRET_KEYS = {"authorization", "token", "access_token", "refresh_token", "password", "api_key", "secret"}

_lock = threading.Lock()


def mask_text(text: str) -> str:
    text = _EMAIL.sub("[EMAIL]", text)
    text = _IBAN.sub("[IBAN]", text)
    text = _CARD.sub("[CARD]", text)
    text = _PHONE.sub("[PHONE]", text)
    return text


def mask(value: Any) -> Any:
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k.lower() in _SECRET_KEYS else mask(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [mask(v) for v in value]
    return value


def _truncate(value: Any, limit: int = 2000) -> Any:
    raw = json.dumps(value, default=str)
    if len(raw) <= limit:
        return value
    return {"_truncated": raw[:limit]}


class AuditLog:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else repo_path(os.environ.get("MCP_AUDIT_PATH", settings()["audit"]["path"]))

    def write(self, *, server: str, user: str, tool: str, args: dict, result: Any, status: str,
              trace_id: str | None, latency_ms: float) -> dict:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "server": server,
            "user": user,
            "tool": tool,
            "args": mask(args),
            "result": _truncate(mask(result)),
            "status": status,
            "trace_id": trace_id,
            "latency_ms": round(latency_ms, 2),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, default=str)
        with _lock, open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return record


def now_ms() -> float:
    return time.perf_counter() * 1000
