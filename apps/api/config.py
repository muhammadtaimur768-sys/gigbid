"""Runtime settings for the GigBid API, read from environment variables only."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL", f"sqlite:///{ROOT / 'data/processed/gigbid.db'}"))
    checkpoint_url: str = field(default_factory=lambda: os.getenv("CHECKPOINT_DATABASE_URL", ""))
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", "dev-insecure-jwt-secret-change-me"))
    jwt_ttl_hours: int = field(default_factory=lambda: int(os.getenv("JWT_TTL_HOURS", "72")))
    cookie_name: str = "gigbid_session"
    cookie_secure: bool = field(default_factory=lambda: _flag("COOKIE_SECURE", "0"))
    token_enc_key: str = field(default_factory=lambda: os.getenv("TOKEN_ENC_KEY", ""))
    cors_origins: list[str] = field(default_factory=lambda: [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()])
    gigsim_url: str = field(default_factory=lambda: os.getenv("GIGSIM_URL", ""))
    mount_gigsim: bool = field(default_factory=lambda: _flag("MOUNT_GIGSIM"))
    mount_mcp: bool = field(default_factory=lambda: _flag("MOUNT_MCP"))
    run_mode: str = field(default_factory=lambda: os.getenv("RUN_MODE", "inline"))  # inline | worker | stream
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379"))
    reviewer_email: str = "reviewer@gigbid.app"
    reviewer_password: str = field(default_factory=lambda: os.getenv("REVIEWER_PASSWORD", "review-gigbid-2026"))
    cron_secret: str = field(default_factory=lambda: os.getenv("CRON_SECRET", ""))
    upwork_client_id: str = field(default_factory=lambda: os.getenv("UPWORK_CLIENT_ID", ""))
    upwork_client_secret: str = field(default_factory=lambda: os.getenv("UPWORK_CLIENT_SECRET", ""))
    upwork_mcp_url: str = field(default_factory=lambda: os.getenv("UPWORK_MCP_URL", "https://mcp.upwork.com/mcp"))
    upwork_metadata_url: str = field(default_factory=lambda: os.getenv("UPWORK_OAUTH_METADATA_URL", ""))
    public_base_url: str = field(default_factory=lambda: os.getenv("PUBLIC_BASE_URL", "http://localhost:8000"))
    web_base_url: str = field(default_factory=lambda: os.getenv("WEB_BASE_URL", ""))
    langsmith_project: str = field(default_factory=lambda: os.getenv("LANGSMITH_PROJECT", "gigbid"))
    health_cache_s: float = field(default_factory=lambda: float(os.getenv("HEALTH_CACHE_SECONDS", "10")))

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://"))


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def agent_config() -> dict:
    """Thresholds and limits are owned by agent/config.yaml (read-only here)."""
    path = ROOT / "agent" / "config.yaml"
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


def cfg(path: str, default=None):
    node = agent_config()
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node
