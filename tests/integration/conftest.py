"""Integration fixtures: GigSim in-process (FastAPI TestClient) + heuristic LLM provider."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "heuristic")
    monkeypatch.setenv("TRACE_DATABASE_URL", f"sqlite:///{tmp_path / 'trace.db'}")
    monkeypatch.setenv("GIGSIM_DATABASE_URL", f"sqlite:///{tmp_path / 'gigsim.db'}")
    monkeypatch.setenv("GIGSIM_ERROR_RATE", "0")
    monkeypatch.setenv("GIGSIM_POLICY_UPDATE", "1")


@pytest.fixture()
def gigsim_client():
    gs_app = pytest.importorskip("gigsim.app")
    from fastapi.testclient import TestClient

    if hasattr(gs_app, "reset_rate_limits"):
        gs_app.reset_rate_limits()
    if hasattr(gs_app, "_stats_cache"):
        gs_app._stats_cache.clear()
    with TestClient(gs_app.app) as c:
        yield c


@pytest.fixture()
def port(gigsim_client):
    from agent.marketplace_port import GigSimHTTPPort

    return GigSimHTTPPort(client=gigsim_client, token="gs-aiml-token")


def dev_jobs(persona: str = "aiml") -> list[dict]:
    return [json.loads(line) for line in open(ROOT / "evals" / "datasets" / f"dev_{persona}.jsonl")]


def open_jobs(port, category="AI & Machine Learning") -> list[dict]:
    return port.search_jobs(category=category, limit=50)["jobs"]


def hidden() -> dict:
    return json.load(open(ROOT / "gigsim" / "seed_data" / "hidden.json"))["jobs"]
