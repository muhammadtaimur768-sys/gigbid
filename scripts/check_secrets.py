#!/usr/bin/env python3
"""CI guard: no secrets in the repository (complements the gitleaks action).

Fails if
- a .env file (anything but .env.example) is tracked, or
- a tracked text file matches a known credential pattern, or
- a key/secret/password/token assignment holds a long literal value that is not a known
  public development default (the GigSim tokens and reviewer password are synthetic and documented).

Scans `git ls-files` when run in a git checkout, otherwise walks the tree.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "node_modules", "dist", "build", "__pycache__", "playwright-report",
             "test-results", ".ruff_cache", ".pytest_cache"}
SKIP_PREFIXES = ("data/processed/",)
SKIP_FILES = {"package-lock.json", "uv.lock", "poetry.lock", "pnpm-lock.yaml", "yarn.lock",
              "scripts/check_secrets.py"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz", ".onnx",
                   ".bin", ".db", ".sqlite3", ".woff", ".woff2", ".ttf", ".mp4", ".webm", ".npy", ".pkl"}
MAX_BYTES = 2_000_000

PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    "OpenAI-style key": re.compile(r"\bsk-(?:proj-|live-|ant-)?[A-Za-z0-9_-]{20,}\b"),
    "Groq key": re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"),
    "LangSmith key": re.compile(r"\blsv2_(?:pt|sk)_[A-Za-z0-9_]{20,}\b"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "HF token": re.compile(r"\bhf_[A-Za-z0-9]{30,}\b"),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    "URL with password": re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@]+:([^\s:@/]{6,})@"),
}
_NAME = r"[A-Za-z0-9_]*(?:SECRET|PASSWORD|PASSWD|API_KEY|APIKEY|ACCESS_KEY|PRIVATE_KEY|TOKEN|ENC_KEY)[A-Za-z0-9_]*"
# Code: a secret-named variable/key assigned a quoted string literal.
ASSIGN_RE = re.compile(r"""(?i)\b(""" + _NAME + r""")["']?\s*[:=]\s*["']([^"'\s]{16,})["']""")
# Config files (.env, yaml, toml, ini, sh, Dockerfile): KEY=value / KEY: value at line start.
CONFIG_ASSIGN_RE = re.compile(r"""(?i)^\s*(?:export\s+|-\s+)?(""" + _NAME + r""")\s*[:=]\s*["']?([^\s"'#,}]{16,})""")
CONFIG_SUFFIXES = {".env", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".sh", ".conf", ".example", ".properties"}
# Synthetic, publicly documented development values (GigSim, local compose, reviewer login).
ALLOWED_VALUES = {
    "gs-aiml-token", "gs-fullstack-token", "gs-data-token", "gigsim-admin", "review-gigbid-2026",
    "local-dev-marketplace-token", "change-me", "changeme",
}
ALLOWED_URL_PASSWORDS = {"gigbid", "postgres", "password", "change-me"}
PLACEHOLDER_RE = re.compile(r"^(\$\{?|<|\{\{|your[-_]|xxx|\*\*\*|example|dummy|test[-_]|fake|placeholder|os\.environ|env\.|secrets\.)", re.I)


def files() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.splitlines()
        if out:
            return out
    except (OSError, subprocess.CalledProcessError):
        pass
    found = []
    for p in ROOT.rglob("*"):
        if p.is_file() and not any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            found.append(p.relative_to(ROOT).as_posix())
    return found


def tracked_env_files() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [f for f in out.splitlines() if re.search(r"(^|/)\.env(\.[^/]*)?$", f) and not f.endswith(".env.example")]


def scan(rel: str) -> list[str]:
    path = ROOT / rel
    if (rel in SKIP_FILES or Path(rel).name in SKIP_FILES or rel.startswith(SKIP_PREFIXES)
            or any(part in SKIP_DIRS for part in Path(rel).parts)
            or path.suffix.lower() in BINARY_SUFFIXES or not path.is_file() or path.stat().st_size > MAX_BYTES):
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    hits = []
    is_config = path.suffix.lower() in CONFIG_SUFFIXES or path.name.lower().startswith((".env", "dockerfile")) \
        or path.name.endswith(".Dockerfile")
    for n, line in enumerate(text.splitlines(), 1):
        if "secrets-check: ignore" in line:
            continue
        for name, rx in PATTERNS.items():
            m = rx.search(line)
            if not m:
                continue
            if name == "URL with password" and m.group(1).lower() in ALLOWED_URL_PASSWORDS | {"${postgres_password"}:
                continue
            if name == "URL with password" and m.group(1).startswith("$"):
                continue
            hits.append(f"{rel}:{n}: {name}")
        matches = list(ASSIGN_RE.finditer(line))
        if is_config:
            matches += list(CONFIG_ASSIGN_RE.finditer(line))
        for m in matches:
            value = m.group(2)
            if value in ALLOWED_VALUES or PLACEHOLDER_RE.match(value) or value.startswith("$"):
                continue
            if re.fullmatch(r"[A-Z0-9_]+", value):  # another env var name, e.g. api_key_env: GROQ_API_KEY
                continue
            if re.fullmatch(r"[a-z_][a-z0-9_]*(?:\.[a-z0-9_]+)+(?:\(\))?|[a-z_][a-z0-9_]*\(\)?", value):  # dotted ref / call
                continue
            hits.append(f"{rel}:{n}: literal value assigned to {m.group(1)}")
    return hits


def main() -> int:
    problems = [f"{f}: .env files must never be committed" for f in tracked_env_files()]
    listed = files()
    for rel in listed:
        problems += scan(rel)
    if problems:
        print("FAIL possible secrets found (use env vars; mark false positives with 'secrets-check: ignore'):")
        for p in problems:
            print("  " + p)
        return 1
    print(f"OK no secrets found ({len(listed)} files scanned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
