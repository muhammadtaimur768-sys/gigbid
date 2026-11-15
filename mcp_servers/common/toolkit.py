"""Helpers to register tools from Pydantic input models with a flat argument schema.

`register_model_tool` builds a wrapper whose signature mirrors the input model's fields (so the
published inputSchema keeps the model's constraints), then validates again through the model
(cross-field validators), applies the per-user rate limit, idempotency replay for writes, and
writes one audit record per call.
"""
from __future__ import annotations

import inspect
import os
import uuid
from dataclasses import dataclass
from typing import Annotated, Any, Awaitable, Callable

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field, ValidationError
from pydantic_core import PydanticUndefined

from .audit import AuditLog, now_ms
from .idempotency import IdempotencyConflict, IdempotencyStore
from .ratelimit import RateLimited, TokenBucketLimiter

AUTH_USER_HEADER = "x-gigbid-auth-user"


@dataclass
class CallInfo:
    user: str
    trace_id: str
    headers: dict[str, str]


def call_info(ctx: Context | None) -> CallInfo:
    user = os.environ.get("MCP_USER_ID", "local")
    trace_id = None
    headers: dict[str, str] = {}
    try:
        rc = ctx.request_context if ctx is not None else None
    except ValueError:
        rc = None
    if rc is not None:
        req = getattr(rc, "request", None)
        if req is not None and hasattr(req, "headers"):
            headers = {k.lower(): v for k, v in req.headers.items()}
            user = headers.get(AUTH_USER_HEADER, user)
            trace_id = headers.get("x-trace-id")
        meta = rc.meta
        if meta is not None:
            extra = getattr(meta, "model_extra", None) or {}
            trace_id = extra.get("trace_id") or trace_id
    return CallInfo(user=user, trace_id=trace_id or uuid.uuid4().hex, headers=headers)


@dataclass
class ToolRuntime:
    server: str
    limiter: TokenBucketLimiter
    audit: AuditLog
    idem: IdempotencyStore


def _signature_from_model(model: type[BaseModel]) -> tuple[list[inspect.Parameter], dict[str, Any]]:
    params = [inspect.Parameter("ctx", inspect.Parameter.KEYWORD_ONLY, annotation=Context)]
    ann: dict[str, Any] = {"ctx": Context}
    for name, f in model.model_fields.items():
        if f.default is not PydanticUndefined:
            default = f.default
        elif f.default_factory is not None:
            default = f.default_factory()
        else:
            default = inspect.Parameter.empty
        info = Field(description=f.description, title=f.title, examples=f.examples)
        annotation = Annotated[(f.annotation, *f.metadata, info)] if f.metadata else Annotated[f.annotation, info]
        params.append(inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=default, annotation=annotation))
        ann[name] = annotation
    return params, ann


def register_model_tool(
    mcp: FastMCP,
    rt: ToolRuntime,
    *,
    name: str,
    input_model: type[BaseModel],
    output_model: type[BaseModel],
    handler: Callable[[Any, CallInfo], Awaitable[BaseModel]],
    annotations: ToolAnnotations,
    description: str,
    write: bool = False,
) -> None:
    async def wrapper(ctx: Context, **kwargs: Any) -> BaseModel:
        info = call_info(ctx)
        t0 = now_ms()
        status, result_dump = "ok", None
        try:
            try:
                rt.limiter.acquire(info.user)
            except RateLimited as e:
                raise ToolError(f"rate_limited: retry after {e.retry_after:.1f}s") from e
            try:
                params = input_model(**kwargs)
            except ValidationError as e:
                raise ToolError(f"invalid_arguments: {e.errors(include_url=False)}") from e
            args = params.model_dump(mode="json")
            key = args.get("idempotency_key") if write else None
            dry = bool(args.get("dry_run")) if write else False
            if write and not dry:
                try:
                    prior = rt.idem.get(info.user, name, key, args)
                except IdempotencyConflict as e:
                    raise ToolError(f"idempotency_conflict: {e}") from e
                if prior is not None:
                    out = output_model(**{**prior, "replayed": True})
                    status, result_dump = "replayed", out.model_dump(mode="json")
                    return out
            out = await handler(params, info)
            result_dump = out.model_dump(mode="json")
            if write and not dry:
                rt.idem.put(info.user, name, key, args, result_dump)
            if dry:
                status = "dry_run"
            return out
        except ToolError as e:
            status, result_dump = "error", {"error": str(e)}
            raise
        except Exception as e:  # surface typed adapter errors with their class name
            status, result_dump = "error", {"error": f"{type(e).__name__}: {e}"}
            raise ToolError(f"{type(e).__name__}: {e}") from e
        finally:
            rt.audit.write(server=rt.server, user=info.user, tool=name, args=kwargs_json(kwargs),
                           result=result_dump, status=status, trace_id=info.trace_id,
                           latency_ms=now_ms() - t0)

    params, ann = _signature_from_model(input_model)
    wrapper.__signature__ = inspect.Signature(params, return_annotation=output_model)  # type: ignore[attr-defined]
    wrapper.__annotations__ = {**ann, "return": output_model}
    wrapper.__name__ = name
    wrapper.__doc__ = description
    mcp.add_tool(wrapper, name=name, title=annotations.title, description=description,
                 annotations=annotations, structured_output=True)


def kwargs_json(kwargs: dict) -> dict:
    out = {}
    for k, v in kwargs.items():
        if isinstance(v, BaseModel):
            out[k] = v.model_dump(mode="json")
        elif isinstance(v, list):
            out[k] = [x.model_dump(mode="json") if isinstance(x, BaseModel) else x for x in v]
        else:
            out[k] = v
    return out
