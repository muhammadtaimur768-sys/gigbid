"""Loads mcp_servers/config.yaml (tool-layer settings) once."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(os.environ.get("GIGBID_ROOT", Path(__file__).resolve().parents[2]))
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"


@lru_cache(maxsize=1)
def settings() -> dict[str, Any]:
    with open(CONFIG_PATH) as fh:
        return yaml.safe_load(fh) or {}


def repo_path(rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else REPO_ROOT / p


def marketplace_mode() -> str:
    env = os.environ.get("MARKETPLACE_MODE")
    if env:
        return env
    agent_cfg = REPO_ROOT / "agent" / "config.yaml"
    if agent_cfg.exists():
        try:
            data = yaml.safe_load(agent_cfg.read_text()) or {}
            mode = (data.get("marketplace") or {}).get("mode")
            if mode:
                return str(mode)
        except Exception:
            pass
    return settings()["marketplace"]["default_mode"]
