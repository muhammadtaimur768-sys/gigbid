"""GigBid API (FastAPI). All GigBid routes live under /api. Optionally mounts GigSim at /gigsim
(MOUNT_GIGSIM=1) and the MCP servers at /mcp/{portfolio,marketplace,workspace} (MOUNT_MCP=1) so one
host can serve the whole system."""
from __future__ import annotations

import logging
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .auth.security import hash_password
from .config import get_settings
from .db import SessionLocal, User, init_db
from .graphs import open_runtime, runtime
from .integrations import optional
from .routers import analytics, auth, cron, health, jobs, messages, oauth, proposals, runs, settings
from .tracing import TraceIdMiddleware, configure_logging

log = logging.getLogger("gigbid.api")
MCP_SERVERS = ("portfolio", "marketplace", "workspace")


def seed_reviewer() -> None:
    s = get_settings()
    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.email == s.reviewer_email)) is None:
            db.add(User(email=s.reviewer_email, password_hash=hash_password(s.reviewer_password),
                        name="Reviewer", persona="aiml", onboarded=True,
                        settings={"autonomy": "manual", "marketplace_mode": "gigsim"}))
            db.commit()
            log.info("seeded reviewer user")
    finally:
        db.close()


_mounted: dict[str, object] = {}


def _mount_optional(app: FastAPI) -> None:
    s = get_settings()
    if s.mount_gigsim:
        gs = optional("gigsim.app", "app")
        if gs is not None:
            app.mount("/gigsim", gs)
            _mounted["gigsim"] = gs
    if s.mount_mcp:
        for name in MCP_SERVERS:
            build = optional(f"mcp_servers.{name}.server", "build_http_app")
            if build is None:
                continue
            try:
                sub = build()
                app.mount(f"/mcp/{name}", sub)
                _mounted[f"mcp/{name}"] = sub
            except Exception:  # noqa: BLE001
                log.exception("mounting MCP server %s failed", name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    seed_reviewer()
    async with AsyncExitStack() as stack:
        await open_runtime(stack)
        for name, sub in _mounted.items():  # mounted sub-apps' lifespans (MCP session managers)
            ctx = getattr(getattr(sub, "router", None), "lifespan_context", None)
            if ctx is not None:
                try:
                    await stack.enter_async_context(ctx(sub))
                except Exception:  # noqa: BLE001
                    log.exception("lifespan for %s failed", name)
        app.state.runtime = runtime
        yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="GigBid API", version="0.1.0", lifespan=lifespan,
                  description="Human-in-the-loop freelance bidding agent API.",
                  generate_unique_id_function=lambda r: f"{r.tags[0] if r.tags else 'api'}_{r.name}")
    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Trace-Id", "X-Marketplace"])
    for r in (auth.router, oauth.router, jobs.router, proposals.router, proposals.pipeline_router,
              messages.router, runs.router, analytics.router, settings.router, health.router, cron.router):
        app.include_router(r)
    _mount_optional(app)
    return app


app = create_app()
