"""Config loading for the agent package (agent/config.yaml + policy pack)."""
from __future__ import annotations

import datetime as dt
import functools
import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = Path(__file__).resolve().parent


@functools.lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    path = Path(os.environ.get("GIGBID_AGENT_CONFIG", AGENT_DIR / "config.yaml"))
    with open(path) as fh:
        return yaml.safe_load(fh)


def cfg(*keys: str, default: Any = None) -> Any:
    node: Any = load_config()
    for k in keys:
        if not isinstance(node, dict) or k not in node:
            return default
        node = node[k]
    return node


def _today() -> dt.date:
    override = os.environ.get("GIGBID_TODAY")
    if override:
        return dt.date.fromisoformat(override)
    return dt.date.today()


@functools.lru_cache(maxsize=4)
def _load_policy(today_iso: str) -> dict[str, Any]:
    rules_path = ROOT / cfg("policy", "rules_path", default="data/policy_pack/rules.yaml")
    updates_dir = ROOT / cfg("policy", "updates_dir", default="data/policy_pack/updates")
    policy: dict[str, Any] = {"rules": [], "bidding": {}, "applied_updates": []}
    if rules_path.exists():
        base = yaml.safe_load(rules_path.read_text()) or {}
        policy["rules"] = list(base.get("rules") or [])
        policy["bidding"] = dict(base.get("bidding") or {})
        policy["proposal"] = dict(base.get("proposal") or {})
        for k, v in base.items():
            policy.setdefault(k, v)
    if updates_dir.exists():
        for upd_path in sorted(updates_dir.glob("*.yaml")):
            upd = yaml.safe_load(upd_path.read_text()) or {}
            eff = str(upd.get("effective_date") or upd.get("effective") or upd_path.stem)
            try:
                if dt.date.fromisoformat(eff[:10]) > dt.date.fromisoformat(today_iso):
                    continue
            except ValueError:
                pass
            _merge_update(policy, upd)
            policy["applied_updates"].append(upd_path.stem)
    return policy


def _merge_update(policy: dict, upd: dict) -> None:
    by_id = {r.get("id"): i for i, r in enumerate(policy["rules"])}
    for key in ("rules", "add_rules", "new_rules"):
        for r in upd.get(key) or []:
            if r.get("id") in by_id:
                policy["rules"][by_id[r["id"]]] = r
            else:
                policy["rules"].append(r)
    for ch in upd.get("changes") or []:
        typ = str(ch.get("type", ""))
        if typ in ("new_rule", "rule", "update_rule"):
            rule = {k: v for k, v in ch.items() if k != "type"}
            rule.setdefault("kind", "length" if rule.get("max_chars") else "regex")
            if rule.get("id") in by_id:
                merged = dict(policy["rules"][by_id[rule["id"]]])
                merged.update(rule)
                if merged.get("patterns") and rule.get("max_chars"):
                    merged["kind"] = policy["rules"][by_id[rule["id"]]].get("kind", "regex")
                policy["rules"][by_id[rule["id"]]] = merged
            else:
                policy["rules"].append(rule)
        elif typ == "connects_surcharge":
            policy.setdefault("bidding", {})[ch.get("id", "surcharge")] = {
                k: v for k, v in ch.items() if k not in ("type", "id")}
    for key in ("bidding", "proposal", "bidding_overrides"):
        if isinstance(upd.get(key), dict):
            policy.setdefault("bidding" if key == "bidding_overrides" else key, {}).update(upd[key])
    for k, v in upd.items():
        if k not in ("rules", "add_rules", "new_rules", "bidding", "proposal", "changes", "bidding_overrides") and k not in policy:
            policy[k] = v


def load_policy() -> dict[str, Any]:
    """Base rules.yaml merged with every update whose effective date has passed."""
    return _load_policy(_today().isoformat())


def max_proposal_chars() -> int | None:
    """Character limit from the policy pack (rule with max_chars, or proposal.max_chars)."""
    pol = load_policy()
    limits = []
    for src in (pol.get("proposal") or {}, pol.get("bidding") or {}):
        for k in ("max_chars", "max_characters", "proposal_max_chars", "max_proposal_chars"):
            if src.get(k):
                limits.append(int(src[k]))
    for r in pol.get("rules", []):
        for k in ("max_chars", "max_characters", "limit"):
            if r.get(k):
                limits.append(int(r[k]))
    return min(limits) if limits else None
