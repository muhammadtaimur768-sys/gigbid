#!/usr/bin/env python3
"""CI guard: nothing under gigsim/ may change.

gigsim/CHECKSUMS.sha256 records the SHA-256 of every file of the provided simulator
(format: "<sha256>  <relative/path>", one per line, like `sha256sum`). This script fails if
any listed file is missing or modified, or if a file was added under gigsim/.

    python scripts/check_gigsim_unchanged.py           # verify (CI)
    python scripts/check_gigsim_unchanged.py --write   # record (only when GigSim is updated upstream)
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIGSIM = ROOT / "gigsim"
CHECKSUMS = GIGSIM / "CHECKSUMS.sha256"
IGNORED_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
IGNORED_NAMES = {".DS_Store", CHECKSUMS.name}


def tracked_files() -> list[Path]:
    files = []
    for p in sorted(GIGSIM.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(GIGSIM)
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue
        if p.suffix in IGNORED_SUFFIXES or p.name in IGNORED_NAMES:
            continue
        files.append(p)
    return files


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def write() -> int:
    lines = [f"{sha256(p)}  {rel(p)}" for p in tracked_files()]
    CHECKSUMS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"recorded {len(lines)} files in {rel(CHECKSUMS)}")
    return 0


def verify() -> int:
    if not GIGSIM.is_dir():
        print("FAIL gigsim/ directory is missing")
        return 1
    if not CHECKSUMS.exists():
        print(f"FAIL {rel(CHECKSUMS)} is missing; record it once with --write when GigSim is first added")
        return 1
    expected: dict[str, str] = {}
    for n, line in enumerate(CHECKSUMS.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            digest, path = line.split(maxsplit=1)
        except ValueError:
            print(f"FAIL malformed line {n} in {rel(CHECKSUMS)}: {line!r}")
            return 1
        expected[path.strip().lstrip("*")] = digest.lower()

    actual = {rel(p): p for p in tracked_files()}
    problems = []
    for path, digest in expected.items():
        if path not in actual:
            problems.append(f"missing   {path}")
        elif sha256(actual[path]) != digest:
            problems.append(f"modified  {path}")
    for path in sorted(set(actual) - set(expected)):
        problems.append(f"added     {path}")

    if problems:
        print("FAIL gigsim/ must not be modified (it is the provided simulator):")
        for p in problems:
            print("  " + p)
        return 1
    print(f"OK gigsim/ unchanged ({len(expected)} files verified)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="record checksums instead of verifying")
    args = ap.parse_args()
    return write() if args.write else verify()


if __name__ == "__main__":
    sys.exit(main())
