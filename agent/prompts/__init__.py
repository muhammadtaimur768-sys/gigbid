"""Prompt loader. Every prompt lives in agent/prompts/<name>.md with a `<!-- version: N -->` header."""
from __future__ import annotations

import functools
import re
from pathlib import Path
from string import Template

PROMPT_DIR = Path(__file__).resolve().parent
_VERSION_RE = re.compile(r"<!--\s*version:\s*([\w.\-]+)\s*-->")


@functools.lru_cache(maxsize=64)
def load_prompt(name: str) -> tuple[str, str]:
    """Return (template_text, version) for agent/prompts/<name>.md (header stripped)."""
    raw = (PROMPT_DIR / f"{name}.md").read_text()
    m = _VERSION_RE.search(raw)
    version = m.group(1) if m else "0"
    text = _VERSION_RE.sub("", raw, count=1).strip()
    return text, f"{name}@v{version}"


def render_prompt(name: str, variables: dict) -> tuple[str, str]:
    """Fill `$var` placeholders (string.Template; JSON braces in prompts stay untouched)."""
    text, version = load_prompt(name)
    return Template(text).safe_substitute({k: ("" if v is None else v) for k, v in variables.items()}), version


def list_prompts() -> dict[str, str]:
    return {p.stem: load_prompt(p.stem)[1] for p in sorted(PROMPT_DIR.glob("*.md"))}
