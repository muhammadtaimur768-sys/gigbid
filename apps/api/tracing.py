"""Trace-id propagation and PII-masked request logging."""
from __future__ import annotations

import contextvars
import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
log = logging.getLogger("gigbid.api")

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")
_TOKEN = re.compile(r"(?i)(bearer\s+|access_token=|token=)[^\s&\"']+")


def mask_pii(text: str) -> str:
    try:  # prefer the shared implementation so every layer masks identically
        from agent.tracing import mask_pii as shared  # type: ignore
        text = shared(text)
    except Exception:
        pass
    text = _TOKEN.sub(lambda m: m.group(1) + "[REDACTED]", text)
    text = _EMAIL.sub("[EMAIL]", text)
    text = _IBAN.sub("[IBAN]", text)
    text = _CARD.sub("[CARD]", text)
    text = _PHONE.sub("[PHONE]", text)
    return text


def new_trace_id() -> str:
    return uuid.uuid4().hex


def current_trace_id() -> str:
    return trace_id_var.get() or new_trace_id()


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-trace-id", "")
        trace_id = incoming if re.fullmatch(r"[A-Za-z0-9_-]{8,64}", incoming or "") else new_trace_id()
        token = trace_id_var.set(trace_id)
        request.state.trace_id = trace_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("trace=%s %s %s failed", trace_id, request.method, mask_pii(request.url.path))
            raise
        finally:
            trace_id_var.reset(token)
        response.headers["X-Trace-Id"] = trace_id
        log.info("trace=%s %s %s?%s -> %s %.1fms", trace_id, request.method, mask_pii(request.url.path),
                 mask_pii(request.url.query), response.status_code, (time.perf_counter() - start) * 1000)
        return response


class PIIMaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = mask_pii(record.getMessage())
            record.args = ()
        except Exception:
            pass
        return True


def configure_logging() -> None:
    root = logging.getLogger("gigbid")
    if not any(isinstance(f, PIIMaskingFilter) for f in root.filters):
        root.addFilter(PIIMaskingFilter())
    handler_exists = any(getattr(h, "_gigbid", False) for h in root.handlers)
    if not handler_exists:
        h = logging.StreamHandler()
        h._gigbid = True  # type: ignore[attr-defined]
        h.addFilter(PIIMaskingFilter())
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(h)
        root.setLevel(logging.INFO)
        root.propagate = False
