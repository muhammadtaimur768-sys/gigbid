"""Loads rag/config.yaml, merged with the `rag:` section of agent/config.yaml when present."""
from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RAG_CONFIG = ROOT / "rag" / "config.yaml"
SHIPPED = ROOT / "rag" / "shipped_variant.yaml"
AGENT_CONFIG = ROOT / "agent" / "config.yaml"


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def load_config() -> dict:
    cfg = copy.deepcopy(_read(RAG_CONFIG))
    agent_rag = (_read(AGENT_CONFIG).get("rag") or {})
    for key, val in agent_rag.items():
        if isinstance(val, dict) and isinstance(cfg.get(key), dict):
            cfg[key] = {**cfg[key], **val}
        elif key != "variant":
            cfg[key] = val
    shipped = (_read(SHIPPED).get("rag") or {}).get("variant")
    cfg["active_variant"] = agent_rag.get("variant") or shipped or cfg.get("default_variant", "v0")
    return cfg


def resolve_path(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else ROOT / path


def variant_flags(variant: str) -> dict:
    """Turn "v1+v2+v3" into one flag dict. "v0" alone is the naive baseline."""
    variants = load_config()["variants"]
    parts = [p.strip().lower() for p in variant.split("+") if p.strip()]
    if not parts:
        raise ValueError("empty variant")
    flags = dict(variants["base"])
    for p in parts:
        if p not in variants:
            raise ValueError(f"unknown variant component: {p}")
        flags.update(variants[p])
    flags["name"] = "+".join(parts)
    return flags
