#!/usr/bin/env python3
"""CI gate: fail if smoke-eval metrics cross the thresholds in evals/thresholds.yaml.

    python scripts/check_eval_thresholds.py                    # check (eval.yml)
    python scripts/check_eval_thresholds.py --write-baseline   # record current values as the baseline
    python scripts/check_eval_thresholds.py --summary out.md   # also write a markdown summary

Exit code 1 when any gate fails or a required metric is missing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "evals" / "thresholds.yaml"


def lookup(data, dotted: str):
    cur = data
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur if isinstance(cur, (int, float)) and not isinstance(cur, bool) else None


def flat_keys(data, prefix: str = "") -> list[str]:
    out = []
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            out += flat_keys(v, key) if isinstance(v, dict) else [key]
    return out


def load_json(path: Path, cache: dict):
    if path not in cache:
        cache[path] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    return cache[path]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--summary", type=Path, help="write a markdown table (e.g. $GITHUB_STEP_SUMMARY)")
    args = ap.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    baseline_path = ROOT / cfg.get("baseline_file", "evals/results/smoke_baseline.json")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.exists() else {}

    cache: dict = {}
    values: dict[str, float] = {}
    rows, failures = [], []
    for gate in cfg.get("gates", []):
        name, optional = gate["name"], bool(gate.get("optional", False))
        path = ROOT / gate["file"]
        data = load_json(path, cache)
        if data is None:
            msg = f"{gate['file']} not found (did the smoke runner write it?)"
            if optional:
                rows.append((name, "-", "skipped", msg))
            else:
                failures.append(f"{name}: {msg}")
                rows.append((name, "-", "FAIL", msg))
            continue
        value, used = None, None
        for key in gate.get("keys", [name]):
            value = lookup(data, key)
            if value is not None:
                used = key
                break
        if value is None:
            msg = f"none of {gate.get('keys')} in {gate['file']} (available: {', '.join(flat_keys(data)[:25])})"
            if optional:
                rows.append((name, "-", "skipped", "metric not produced"))
            else:
                failures.append(f"{name}: {msg}")
                rows.append((name, "-", "FAIL", "metric missing"))
            continue

        values[name] = float(value)
        reasons = []
        if "min" in gate and value < gate["min"]:
            reasons.append(f"{value:.4f} < min {gate['min']}")
        if "max" in gate and value > gate["max"]:
            reasons.append(f"{value:.4f} > max {gate['max']}")
        base = baseline.get(name)
        if isinstance(base, (int, float)):
            if "max_drop" in gate and value < base - gate["max_drop"]:
                reasons.append(f"dropped {base - value:.4f} from baseline {base:.4f} (max_drop {gate['max_drop']})")
            if "max_rise" in gate and value > base + gate["max_rise"]:
                reasons.append(f"rose {value - base:.4f} from baseline {base:.4f} (max_rise {gate['max_rise']})")
        status = "FAIL" if reasons else "ok"
        detail = "; ".join(reasons) or (f"baseline {base:.4f}" if isinstance(base, (int, float)) else "no baseline")
        rows.append((name, f"{value:.4f}", status, f"{detail} [{gate['file']}:{used}]"))
        if reasons:
            failures.append(f"{name}: " + "; ".join(reasons))

    width = max((len(r[0]) for r in rows), default=10)
    for name, val, status, detail in rows:
        print(f"{status:7} {name:<{width}}  {val:>8}  {detail}")

    if args.summary:
        lines = ["## Smoke eval gates", "", "| gate | value | status | detail |", "|---|---|---|---|"]
        lines += [f"| {n} | {v} | {s} | {d} |" for n, v, s, d in rows]
        with args.summary.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    if args.write_baseline:
        baseline_path.write_text(json.dumps(values, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"baseline written to {baseline_path.relative_to(ROOT)}")
        return 0

    if failures:
        print("\nFAIL eval thresholds crossed:")
        for f in failures:
            print("  " + f)
        return 1
    print("\nOK all eval gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
