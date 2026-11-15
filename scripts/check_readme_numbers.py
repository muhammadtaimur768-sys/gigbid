#!/usr/bin/env python3
"""CI guard: every number in README.md traces to a file in evals/results/.

Contract (light, by design):
- Result tables live between generated markers that only scripts/fill_readme.py writes:

      <!-- RESULTS:RAG -->
      <!-- written by scripts/fill_readme.py from evals/results/rag_variants.json -->
      | Variant | ... |
      <!-- /RESULTS:RAG -->

  A block is valid if it is still a placeholder (no digits), or it carries the writer stamp and
  every evals/results/... file the stamp names exists. If make_results_table.py supports `--check`,
  it is run too, so a hand-edited table that no longer matches the JSON fails.
- Outside those blocks, metric-looking numbers (percentages, 0.xx scores, $ amounts, "N points",
  "Nx faster") are only allowed on a line that links the evals/results/ file they come from.
  Fenced code blocks and the <!-- VERSIONS --> ... <!-- /VERSIONS --> block are exempt.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
GENERATOR = "scripts/fill_readme.py"
OPEN_RE = re.compile(r"<!--\s*RESULTS:([A-Z0-9_]+)\s*-->")
CLOSE_RE = re.compile(r"<!--\s*/RESULTS:([A-Z0-9_]+)\s*-->")
STAMP_RE = re.compile(r"<!--\s*written by\s+" + re.escape(GENERATOR) + r"\b(.*?)-->", re.IGNORECASE | re.DOTALL)
RESULTS_PATH_RE = re.compile(r"evals/results/[\w./-]+\.(?:json|csv|md|jsonl)")
METRIC_RE = re.compile(
    r"(\d+(?:\.\d+)?\s?%"                     # 42%  41.5 %
    r"|(?<![\w.])0\.\d+\b"                    # 0.83
    r"|\$\s?\d"                               # $0.004
    r"|\b\d+(?:\.\d+)?\s?(?:pp|points?)\b"    # +12 points
    r"|\b\d+(?:\.\d+)?x\s+(?:faster|cheaper|better|more|fewer)\b)",
    re.IGNORECASE,
)


def strip_exempt(lines: list[str]) -> list[tuple[int, str]]:
    out, in_fence, in_versions = [], False, False
    for n, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("```") or s.startswith("~~~"):
            in_fence = not in_fence
            continue
        if re.search(r"<!--\s*VERSIONS\s*-->", s):
            in_versions = True
            continue
        if re.search(r"<!--\s*/VERSIONS\s*-->", s):
            in_versions = False
            continue
        if not in_fence and not in_versions:
            out.append((n, line))
    return out


def main() -> int:
    if not README.exists():
        print("FAIL README.md missing")
        return 1
    text = README.read_text(encoding="utf-8")
    lines = text.splitlines()
    problems: list[str] = []

    # 1. generated blocks
    blocks: dict[str, tuple[int, int]] = {}
    stack: list[tuple[str, int]] = []
    for n, line in enumerate(lines, 1):
        if m := OPEN_RE.search(line):
            stack.append((m.group(1), n))
        elif m := CLOSE_RE.search(line):
            if not stack or stack[-1][0] != m.group(1):
                problems.append(f"README.md:{n}: closing marker /RESULTS:{m.group(1)} without matching open")
                continue
            name, start = stack.pop()
            blocks[name] = (start, n)
    for name, start in stack:
        problems.append(f"README.md:{start}: RESULTS:{name} is never closed")

    in_block: set[int] = set()
    for name, (start, end) in blocks.items():
        in_block.update(range(start, end + 1))
        body = "\n".join(lines[start:end - 1])
        stamp = STAMP_RE.search(body)
        if not stamp:
            visible = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
            if re.search(r"\d", visible):
                problems.append(f"README.md:{start}: RESULTS:{name} has numbers but no '{GENERATOR}' stamp")
            continue
        sources = RESULTS_PATH_RE.findall(stamp.group(1))
        if not sources:
            problems.append(f"README.md:{start}: RESULTS:{name} stamp names no evals/results/ source file")
        for src in sources:
            if not (ROOT / src).exists():
                problems.append(f"README.md:{start}: RESULTS:{name} cites {src}, which does not exist")

    # 2. free-standing numbers outside blocks
    for n, line in strip_exempt(lines):
        if n in in_block:
            continue
        visible = re.sub(r"<!--.*?-->", "", line)
        if not METRIC_RE.search(visible):
            continue
        cited = RESULTS_PATH_RE.findall(line)
        if not cited:
            problems.append(f"README.md:{n}: metric {METRIC_RE.search(visible).group(0)!r} without an evals/results/ citation")
        for src in cited:
            if not (ROOT / src).exists():
                problems.append(f"README.md:{n}: cites {src}, which does not exist")

    # 3. generator self-check, when available
    if blocks and (ROOT / GENERATOR).exists() and "--check" in (ROOT / GENERATOR).read_text(encoding="utf-8"):
        if importlib.util.find_spec("evals") is not None or (ROOT / "evals").is_dir():
            res = subprocess.run([sys.executable, str(ROOT / GENERATOR), "--check"], cwd=ROOT)
            if res.returncode != 0:
                problems.append(f"{GENERATOR} --check: README tables differ from evals/results (regenerate, do not hand-edit)")

    if problems:
        print("FAIL every number in README.md must trace to evals/results/:")
        for p in problems:
            print("  " + p)
        return 1
    print(f"OK README numbers traced ({len(blocks)} generated blocks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
