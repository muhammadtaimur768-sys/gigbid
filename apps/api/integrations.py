"""Optional imports of modules built by other components. The API boots when any are missing
and reports the feature as unavailable instead."""
from __future__ import annotations

import importlib
import logging
from typing import Any, Callable

log = logging.getLogger("gigbid.integrations")
_status: dict[str, str] = {}


def optional(module: str, attr: str | None = None) -> Any:
    try:
        mod = importlib.import_module(module)
        obj = getattr(mod, attr) if attr else mod
        _status[f"{module}{':' + attr if attr else ''}"] = "available"
        return obj
    except Exception as exc:  # ImportError, AttributeError, or a broken module
        _status[f"{module}{':' + attr if attr else ''}"] = f"unavailable: {type(exc).__name__}: {exc}"[:240]
        log.warning("optional integration %s%s unavailable: %s", module, ":" + attr if attr else "", exc)
        return None


def first_attr(module: str, names: list[str]) -> Callable | None:
    mod = optional(module)
    if mod is None:
        return None
    for n in names:
        fn = getattr(mod, n, None)
        if fn is not None:
            return fn
    return None


def status() -> dict[str, str]:
    return dict(_status)
