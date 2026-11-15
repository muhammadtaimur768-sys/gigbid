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
# Phone: a "+" prefix or digit groups joined by separators, and at least 10 digits in total.
# Plain numbers (status codes, latencies, ids) are never masked.
_PHONE = re.compile(r"(?<![\w.+])(?:\+\d[\d\s().-]{8,}\d|\(?\d{2,5}\)?(?:[\s.-]\(?\d{2,8}\)?){1,4})(?![\w])")
_DATEISH = re.compile(r"^\d{4}-\d{2}-\d{2}|^\d{2}[./-]\d{2}[./-]\d{2,4}")


def _phone_sub(m: re.Match) -> str:
    text = m.group(0)
    digits = sum(c.isdigit() for c in text)
    has_sep = text.startswith("+") or bool(re.search(r"\d[\s().-]+\d", text))
    last_group = re.split(r"[\s().-]+", text.strip("()"))[-1]
    if digits < 10 or not has_sep or _DATEISH.match(text) or len(last_group) < 3:
        return text
    return "[PHONE]"
_TOKEN = re.compile(r"(?i)(bearer\s+|access_token=|token=)[^\s&\"']+")


def mask_pii(text: str) -> str:
    text = _TOKEN.sub(lambda m: m.group(1) + "[REDACTED]", text)
    text = _EMAIL.sub("[EMAIL]", text)
    text = _IBAN.sub("[IBAN]", text)
    text = _CARD.sub("[CARD]", text)
    text = _PHONE.sub(_phone_sub, text)
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
        log.info("trace=%s %s %s%s status=%s dur_ms=%.1f", trace_id, request.method, mask_pii(request.url.path),
                 ("?" + mask_pii(request.url.query)) if request.url.query else "", response.status_code,
                 (time.perf_counter() - start) * 1000)
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
