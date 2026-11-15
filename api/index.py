"""Vercel Python entry point: one function serves /api/*, /gigsim/* and /mcp/* (single-host deploy)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("MOUNT_GIGSIM", "1")
os.environ.setdefault("MOUNT_MCP", "1")
os.environ.setdefault("RUN_MODE", "stream")  # serverless: the SSE request drives the graph
if not os.getenv("DATABASE_URL"):
    # Vercel's filesystem is read-only except /tmp; use Postgres via DATABASE_URL for persistence.
    os.environ["DATABASE_URL"] = "sqlite:////tmp/gigbid.db"
    os.environ.setdefault("GIGSIM_DATABASE_URL", "sqlite:////tmp/gigsim.db")

_host = os.getenv("VERCEL_PROJECT_PRODUCTION_URL") or os.getenv("VERCEL_URL")
if _host and not os.getenv("GIGSIM_URL"):
    # the marketplace MCP adapter reaches the mounted GigSim over HTTP on the same host
    os.environ["GIGSIM_URL"] = f"https://{_host}/gigsim"
if _host and not os.getenv("PUBLIC_BASE_URL"):
    os.environ["PUBLIC_BASE_URL"] = f"https://{_host}"
os.environ.setdefault("CORS_ORIGINS", f"https://{_host}" if _host else "")

from apps.api.main import app  # noqa: E402,F401
