"""Checks on the generated corpora, policy pack and dev sets."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PERSONAS = ["aiml", "fullstack", "data"]


def test_persona_corpora_shape():
    for p in PERSONAS:
        base = ROOT / "data" / "personas" / p
        cases = sorted((base / "case_studies").glob("*.md"))
        assert 15 <= len(cases) <= 25
        repos = [d for d in (base / "repos").iterdir() if d.is_dir()]
        assert 4 <= len(repos) <= 8
        for r in repos:
            assert (r / "README.md").exists() and list((r / "src").iterdir())
        props = [json.loads(line) for line in (base / "proposals.jsonl").read_text().splitlines()]
        assert len(props) == 150 and {x["outcome"] for x in props} <= {"won", "replied", "ignored"}
        fm = yaml.safe_load(cases[0].read_text().split("---")[1])
        assert {"id", "title", "project", "skills", "date", "client_industry", "outcome"} <= set(fm)
        assert 300 <= len(cases[0].read_text().split()) <= 750
        assert (base / "cv.pdf").stat().st_size > 1000
        assert json.loads((base / "profile.json").read_text())["persona"] == p


def test_dev_sets_gold_consistent():
    ids = {}
    for p in PERSONAS:
        base = ROOT / "data" / "personas" / p
        ids[p] = {x["id"] for x in json.loads((base / "manifest.json").read_text())}
        rows = [json.loads(line) for line in (ROOT / "evals" / "datasets" / f"dev_{p}.jsonl").read_text().splitlines()]
        assert len(rows) == 200
        skip = sum(r["gold"]["action"] == "skip" for r in rows) / len(rows)
        assert 0.25 <= skip <= 0.45
        for r in rows:
            g = r["gold"]
            assert set(g["evidence_ids"]) <= ids[p]
            assert g["fair_price_band"][0] <= g["fair_price_band"][1]
            if g["is_scam"]:
                assert g["action"] == "skip"
            if g["action"] == "bid":
                assert g["evidence_ids"]


def test_tool_tasks_and_policy():
    tasks = [json.loads(line) for line in (ROOT / "evals" / "datasets" / "tool_tasks.jsonl").read_text().splitlines()]
    assert len(tasks) == 40 and all(t["expected_calls"] for t in tasks)
    rules = yaml.safe_load((ROOT / "data" / "policy_pack" / "rules.yaml").read_text())
    assert {r["kind"] for r in rules["rules"]} <= {"regex", "llm"}
    assert rules["bidding"]["connects_per_proposal_default"] > 0
    upd = yaml.safe_load((ROOT / "data" / "policy_pack" / "updates" / "2026-11-02.yaml").read_text())
    assert any(c["id"] == "early_bird_surcharge" for c in upd["changes"])
