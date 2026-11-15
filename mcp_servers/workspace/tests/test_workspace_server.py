
import httpx
from mcp.shared.memory import create_connected_server_and_client_session as connect

from mcp_servers.workspace import server as ws

HOLD = {"start": "2026-11-17T10:00:00Z", "end": "2026-11-17T10:30:00Z", "title": "Interview: RAG chatbot",
        "attendee": "Acme client", "idempotency_key": "hold-job-001-a"}


async def test_tools_and_annotations(isolated_runtime):
    async with connect(ws.mcp._mcp_server) as c:
        tools = {t.name: t for t in (await c.list_tools()).tools}
    assert {"free_slots", "create_interview_hold", "create_email_draft", "list_holds"} == set(tools)
    assert tools["free_slots"].annotations.readOnlyHint is True
    for n in ("create_interview_hold", "create_email_draft"):
        assert tools[n].annotations.readOnlyHint is False and tools[n].annotations.destructiveHint is False
        assert "idempotency_key" in tools[n].inputSchema["required"]


async def test_free_slots_skips_weekend_and_busy(isolated_runtime):
    ws.store.save({"busy": [{"start": "2026-11-16T09:00:00Z", "end": "2026-11-16T12:00:00Z"}], "holds": [],
                   "drafts": []})
    async with connect(ws.mcp._mcp_server) as c:
        r = await c.call_tool("free_slots", {"days": 1, "duration_min": 60, "from_date": "2026-11-15"})
    slots = r.structuredContent["slots"]
    assert slots[0]["start"].startswith("2026-11-16T12:00")  # Sunday skipped, morning busy
    assert len(slots) == 5


async def test_hold_dry_run_idempotency_and_overlap(isolated_runtime):
    async with connect(ws.mcp._mcp_server) as c:
        p = await c.call_tool("create_interview_hold", {**HOLD, "dry_run": True})
        assert p.structuredContent["status"] == "preview" and ws.store.load()["holds"] == []
        a = await c.call_tool("create_interview_hold", HOLD)
        b = await c.call_tool("create_interview_hold", HOLD)
        assert a.structuredContent["hold_id"] == b.structuredContent["hold_id"] and b.structuredContent["replayed"]
        clash = await c.call_tool("create_interview_hold", {**HOLD, "idempotency_key": "hold-job-001-b"})
        assert clash.isError and "not free" in clash.content[0].text
        bad = await c.call_tool("create_interview_hold", {**HOLD, "end": "2026-11-17T09:00:00Z",
                                                          "idempotency_key": "hold-job-001-c"})
        assert bad.isError
        holds = await c.call_tool("list_holds", {})
    assert len(holds.structuredContent["holds"]) == 1


async def test_email_draft(isolated_runtime):
    args = {"to": "client@example.com", "subject": "Interview", "body": "See you Tuesday.",
            "idempotency_key": "mail-0000001"}
    async with connect(ws.mcp._mcp_server) as c:
        r = await c.call_tool("create_email_draft", args)
        assert r.structuredContent["status"] == "draft"
        assert (await c.call_tool("create_email_draft", {**args, "to": "not-an-email"})).isError
    assert len(ws.store.load()["drafts"]) == 1
    assert "client@example.com" not in isolated_runtime.read_text()


async def test_resource_prompt_and_auth(isolated_runtime, monkeypatch):
    async with connect(ws.mcp._mcp_server) as c:
        assert "workspace://holds" in {str(r.uri) for r in (await c.list_resources()).resources}
        p = await c.get_prompt("schedule_interview", {"client_name": "Acme"})
        assert "free_slots" in p.messages[0].content.text
    monkeypatch.setenv("MCP_WORKSPACE_TOKEN", "ws-secret")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=ws.build_http_app()), base_url="http://t") as h:
        r = await h.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert r.status_code == 401
