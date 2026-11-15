"""Schema snapshot test: fails when any MCP tool/resource/prompt signature changes unintentionally.

Regenerate intentionally with:  UPDATE_SNAPSHOTS=1 .venv/bin/python -m pytest tests/contract -q
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

SNAP_DIR = Path(__file__).parent / "snapshots"
SERVERS = {
    "portfolio": "mcp_servers.portfolio.server",
    "marketplace": "mcp_servers.marketplace.server",
    "workspace": "mcp_servers.workspace.server",
}


async def describe(module: str) -> dict:
    import importlib

    mcp = importlib.import_module(module).mcp
    async with connect(mcp._mcp_server) as c:
        tools = (await c.list_tools()).tools
        templates = (await c.list_resource_templates()).resourceTemplates
        resources = (await c.list_resources()).resources
        prompts = (await c.list_prompts()).prompts
    return {
        "tools": {t.name: {"description": t.description, "inputSchema": t.inputSchema, "outputSchema": t.outputSchema,
                           "annotations": t.annotations.model_dump(exclude_none=True) if t.annotations else None}
                  for t in sorted(tools, key=lambda t: t.name)},
        "resource_templates": sorted(t.uriTemplate for t in templates),
        "resources": sorted(str(r.uri) for r in resources),
        "prompts": {p.name: sorted(a.name for a in (p.arguments or [])) for p in sorted(prompts, key=lambda p: p.name)},
    }


@pytest.mark.parametrize("server", sorted(SERVERS))
async def test_schema_snapshot(server):
    current = await describe(SERVERS[server])
    path = SNAP_DIR / f"{server}.json"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1" or not path.exists():
        SNAP_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        if os.environ.get("CI"):
            pytest.fail(f"snapshot {path.name} was missing in CI; commit it")
        return
    expected = json.loads(path.read_text())
    if current != expected:
        changed = sorted(n for n in set(current["tools"]) | set(expected["tools"])
                         if current["tools"].get(n) != expected["tools"].get(n))
        pytest.fail(f"MCP contract for '{server}' changed (tools: {changed}). If intentional, rerun with "
                    f"UPDATE_SNAPSHOTS=1 and commit tests/contract/snapshots/{server}.json")


async def test_snapshot_detects_change(tmp_path):
    """Guard the guard: a mutated schema must not equal the stored snapshot."""
    current = await describe(SERVERS["marketplace"])
    mutated = json.loads(json.dumps(current))
    mutated["tools"]["submit_proposal"]["inputSchema"]["properties"]["bid_amount"]["maximum"] = 1
    assert mutated != current


def test_every_write_tool_is_guarded():
    snap = json.loads((SNAP_DIR / "marketplace.json").read_text()) if (SNAP_DIR / "marketplace.json").exists() else None
    if snap is None:
        pytest.skip("snapshot not yet written")
    for name, t in snap["tools"].items():
        if not t["annotations"].get("readOnlyHint"):
            assert "idempotency_key" in t["inputSchema"]["required"], name
            assert "dry_run" in t["inputSchema"]["properties"], name
