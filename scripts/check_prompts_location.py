#!/usr/bin/env python3
"""CI guard: every prompt lives in agent/prompts/, never inline in Python.

Checks
1. Python under agent/ (except agent/prompts/) contains no prompt-like string literal:
   - any non-docstring string literal longer than MAX_LEN characters or spanning more than
     MAX_LINES lines (long triple-quoted strings are how inline prompts usually sneak in), or
   - any string literal that reads like a role/system instruction ("You are a ...",
     "Respond only with JSON", "Ignore previous instructions" handling text, ...).
2. Every agent/prompts/*.md starts with a version header `<!-- version: N -->`.

A literal that is genuinely not a prompt (e.g. a regex) can be exempted with a trailing
`# prompt-check: ignore` comment on the line where the literal starts.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "agent"
PROMPTS = AGENT / "prompts"
MAX_LEN = 300
MAX_LINES = 4
IGNORE_MARK = "prompt-check: ignore"
VERSION_RE = re.compile(r"^\s*<!--\s*version:\s*\d+\s*-->", re.IGNORECASE)
ROLE_RE = re.compile(
    r"(\byou are (a|an|the)\b"
    r"|\bact as (a|an|the)\b"
    r"|\brespond (only )?(with|in) (valid )?json\b"
    r"|\breturn (only )?(a )?(valid )?json\b"
    r"|\bas an? (helpful )?(expert|freelancer|bot)\b"
    r"|\byour (task|job|role) is to\b"
    r"|\bsystem prompt\b)",
    re.IGNORECASE,
)


def docstring_nodes(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                ids.add(id(body[0].value))
    return ids


def literal_strings(tree: ast.AST):
    """Yield (node, text) for str constants, including the static parts of f-strings."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node, node.value
        elif isinstance(node, ast.JoinedStr):
            text = "".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
            yield node, text


def check_python(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as exc:
        return [f"{path.relative_to(ROOT)}:{exc.lineno}: cannot parse ({exc.msg})"]
    lines = src.splitlines()
    docs = docstring_nodes(tree)
    in_fstring = {id(v) for n in ast.walk(tree) if isinstance(n, ast.JoinedStr) for v in n.values}
    problems = []
    for node, text in literal_strings(tree):
        if id(node) in docs or id(node) in in_fstring:
            continue
        lineno = getattr(node, "lineno", 0)
        if 0 < lineno <= len(lines) and IGNORE_MARK in lines[lineno - 1]:
            continue
        loc = f"{path.relative_to(ROOT)}:{lineno}"
        n_lines = text.count("\n") + 1
        if len(text) > MAX_LEN or n_lines > MAX_LINES:
            problems.append(f"{loc}: long string literal ({len(text)} chars, {n_lines} lines); move it to agent/prompts/")
        elif ROLE_RE.search(text):
            problems.append(f"{loc}: prompt-like literal {text[:60]!r}; move it to agent/prompts/")
    return problems


def main() -> int:
    problems: list[str] = []
    if not AGENT.is_dir():
        print("SKIP agent/ not present")
        return 0
    py_files = [p for p in sorted(AGENT.rglob("*.py")) if PROMPTS not in p.parents and "__pycache__" not in p.parts]
    for p in py_files:
        problems += check_python(p)

    md_files = sorted(PROMPTS.glob("**/*.md")) if PROMPTS.is_dir() else []
    for p in md_files:
        first = p.read_text(encoding="utf-8").lstrip("﻿").splitlines()[:1]
        if not first or not VERSION_RE.match(first[0]):
            problems.append(f"{p.relative_to(ROOT)}:1: missing '<!-- version: N -->' header")

    if problems:
        print("FAIL prompts must live in agent/prompts/*.md:")
        for p in problems:
            print("  " + p)
        return 1
    print(f"OK prompts only in agent/prompts ({len(py_files)} python files scanned, {len(md_files)} prompt files versioned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
