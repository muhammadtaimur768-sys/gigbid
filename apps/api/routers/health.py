"""Health with marketplace degraded flag (drives the UI banner)."""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from ..config import get_settings
from ..db import get_engine
from ..graphs import runtime
from ..integrations import optional
from ..schemas import HealthOut
from ..services import marketplace
from ..services.runs import _pending_count, retry_pending

router = APIRouter(prefix="/api", tags=["health"])
VERSION = "0.1.0"


@router.get("/health", response_model=HealthOut)
async def health(force: bool = False):
    mp = await marketplace.ping(force=force)
    db_ok = "ok"
    try:
        with get_engine().connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:
        db_ok = "error"
    pending = _pending_count() if db_ok == "ok" else 0
    if mp["ok"] and pending:
        try:
            await retry_pending()
            pending = _pending_count()
        except Exception:
            pass
    graphs = {"bid": "available" if runtime.bid_graph is not None else "unavailable",
              "conversation": "available" if runtime.conversation_graph is not None else "unavailable"}
    features = {
        "analyse": runtime.bid_graph is not None,
        "messages": runtime.conversation_graph is not None,
        "memory": runtime.store is not None,
        "portfolio_index": optional("rag.retriever", "get_retriever") is not None,
        "upwork_oauth": bool(get_settings().upwork_client_id),
        "regenerate_paragraph": optional("agent.nodes.writer", "writer") is not None,
    }
    degraded = (not mp["ok"]) or db_ok != "ok" or runtime.bid_graph is None
    return HealthOut(status="degraded" if degraded else "ok", marketplace="ok" if mp["ok"] else "unavailable",
                     marketplace_detail=mp.get("detail", ""), db=db_ok, graphs=graphs, features=features,
                     pending_work=pending, run_mode=get_settings().run_mode, version=VERSION)
