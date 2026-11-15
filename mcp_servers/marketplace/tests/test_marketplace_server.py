import json

import httpx
import pytest
from mcp import types
from mcp.shared.memory import create_connected_server_and_client_session as connect

from mcp_servers.marketplace import server as mk

from .fakes import FakeAdapter

LETTER = ("I built a retrieval chatbot over 40k legal PDFs with hybrid search and a reranker; "
          "happy to do the same for your documents within two weeks.")
PROPOSAL = {"job_id": "job-001", "cover_letter": LETTER, "bid_amount": 1200,
            "screening_answers": [{"question": "Describe a RAG system you built.", "answer": "Legal RAG, 40k docs."}],
            "idempotency_key": "bid-job-001-v1"}

READS = {"search_jobs", "get_job", "get_client_history", "get_connects_balance", "list_threads", "list_messages",
         "get_market_stats", "list_proposals", "get_marketplace_status"}
WRITES = {"create_proposal_draft", "submit_proposal", "send_message"}


@pytest.fixture
def fake(isolated_runtime):
    a = FakeAdapter()
    mk.set_adapter(a)
    yield a
    mk.set_adapter(None)


async def test_tool_list_and_annotations(fake):
    async with connect(mk.mcp._mcp_server) as c:
        tools = {t.name: t for t in (await c.list_tools()).tools}
    assert READS | WRITES == set(tools)
    for n in READS:
        assert tools[n].annotations.readOnlyHint is True
    for n in WRITES:
        a = tools[n].annotations
        assert a.readOnlyHint is False and a.idempotentHint is True
        assert "idempotency_key" in tools[n].inputSchema["required"]
        assert "dry_run" in tools[n].inputSchema["properties"]
        assert tools[n].outputSchema is not None
    assert tools["submit_proposal"].annotations.destructiveHint is True
    assert tools["create_proposal_draft"].annotations.destructiveHint is False


async def test_read_tools(fake):
    async with connect(mk.mcp._mcp_server) as c:
        r = await c.call_tool("search_jobs", {"q": "rag", "limit": 5})
        assert r.structuredContent["total"] == 1
        assert r.structuredContent["jobs"][0]["connects_cost"] == 12
        r = await c.call_tool("get_job", {"job_id": "job-001"})
        assert r.structuredContent["screening_questions"]
        r = await c.call_tool("get_client_history", {"client_id": "cl-01"})
        assert r.structuredContent["payment_verified"] is True
        r = await c.call_tool("get_connects_balance", {})
        assert r.structuredContent["balance"] == 30
        r = await c.call_tool("list_messages", {"thread_id": "th-1"})
        assert r.structuredContent["messages"][0]["sender"] == "client"
        r = await c.call_tool("get_market_stats", {"category": "AI & ML"})
        assert r.structuredContent["hourly"]["p50"] == 45
        r = await c.call_tool("list_proposals", {"status": "lost"})
        assert [p["proposal_id"] for p in r.structuredContent["proposals"]] == ["p2"]
        r = await c.call_tool("list_threads", {})
        assert r.structuredContent["threads"][0]["thread_id"] == "th-1"


async def test_input_constraints(fake):
    async with connect(mk.mcp._mcp_server) as c:
        assert (await c.call_tool("search_jobs", {"limit": 500})).isError
        assert (await c.call_tool("get_job", {"job_id": "../etc/passwd"})).isError
        short = {**PROPOSAL, "cover_letter": "too short"}
        assert (await c.call_tool("submit_proposal", short)).isError
        long_ = {**PROPOSAL, "cover_letter": "x" * 2501}
        assert (await c.call_tool("submit_proposal", long_)).isError
        no_key = {k: v for k, v in PROPOSAL.items() if k != "idempotency_key"}
        assert (await c.call_tool("submit_proposal", no_key)).isError
        contact = {**PROPOSAL, "cover_letter": LETTER + " Email me: me@example.com"}
        r = await c.call_tool("submit_proposal", contact)
        assert r.isError and "email" in r.content[0].text
    assert fake.submits == 0


async def test_dry_run_changes_nothing(fake):
    async with connect(mk.mcp._mcp_server) as c:
        r = await c.call_tool("submit_proposal", {**PROPOSAL, "dry_run": True})
    s = r.structuredContent
    assert s["status"] == "would_submit" and s["connects_cost"] == 12 and s["balance_after"] == 18
    assert s["would_send"]["cover_letter"] == LETTER
    assert fake.submits == 0 and fake.balance == 30


async def test_idempotent_submit_never_double_spends(fake):
    async with connect(mk.mcp._mcp_server) as c:
        r1 = await c.call_tool("submit_proposal", PROPOSAL)
        r2 = await c.call_tool("submit_proposal", PROPOSAL)
        conflict = await c.call_tool("submit_proposal", {**PROPOSAL, "bid_amount": 900})
    assert r1.structuredContent["proposal_id"] == r2.structuredContent["proposal_id"]
    assert r2.structuredContent["replayed"] is True
    assert fake.submits == 1 and fake.balance == 18
    assert conflict.isError and "idempotency_conflict" in conflict.content[0].text


async def test_draft_and_message(fake):
    async with connect(mk.mcp._mcp_server) as c:
        d = await c.call_tool("create_proposal_draft", {**PROPOSAL, "idempotency_key": "draft-job-001"})
        assert d.structuredContent["status"] == "draft" and d.structuredContent["connects_cost"] == 12
        m = {"thread_id": "th-1", "body": "Monday works for me.", "idempotency_key": "msg-th-1-001"}
        p = await c.call_tool("send_message", {**m, "dry_run": True})
        assert p.structuredContent["status"] == "would_send" and fake.sent == []
        await c.call_tool("send_message", m)
        await c.call_tool("send_message", m)
    assert fake.sent == ["Monday works for me."]


async def test_typed_unavailable_error(fake):
    fake.down = True
    async with connect(mk.mcp._mcp_server) as c:
        r = await c.call_tool("get_job", {"job_id": "job-001"})
        s = await c.call_tool("get_marketplace_status", {})
    assert r.isError and "MarketplaceUnavailable" in r.content[0].text
    assert s.structuredContent["ok"] is False


async def test_audit_log_masks_pii_and_carries_trace_id(fake, isolated_runtime):
    async with connect(mk.mcp._mcp_server) as c:
        req = types.ClientRequest(types.CallToolRequest(method="tools/call", params=types.CallToolRequestParams(
            name="list_messages", arguments={"thread_id": "th-1"}, _meta={"trace_id": "trace-abc"})))
        await c.send_request(req, types.CallToolResult)
        await c.call_tool("submit_proposal", {**PROPOSAL, "dry_run": True})
    lines = [json.loads(x) for x in isolated_runtime.read_text().splitlines()]
    assert lines[0]["trace_id"] == "trace-abc" and lines[0]["tool"] == "list_messages"
    assert "bob@x.com" not in isolated_runtime.read_text() and "[EMAIL]" in isolated_runtime.read_text()
    assert lines[1]["status"] == "dry_run" and lines[1]["user"] == "local"


async def test_rate_limiter_per_user(fake, monkeypatch):
    from mcp_servers.common.ratelimit import TokenBucketLimiter

    monkeypatch.setattr(mk.runtime, "limiter", TokenBucketLimiter(capacity=2, refill_per_minute=1))
    async with connect(mk.mcp._mcp_server) as c:
        ok = [await c.call_tool("get_connects_balance", {}) for _ in range(2)]
        blocked = await c.call_tool("get_connects_balance", {})
    assert not any(r.isError for r in ok)
    assert blocked.isError and "rate_limited" in blocked.content[0].text


async def test_http_bearer_auth_end_to_end(fake, monkeypatch, isolated_runtime):
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    monkeypatch.setenv("MCP_MARKETPLACE_TOKEN", "secret-mk")
    app = mk.build_http_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as h:
        r = await h.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert r.status_code == 401 and r.headers["www-authenticate"].startswith("Bearer")

    def factory(headers=None, timeout=None, auth=None):
        return httpx.AsyncClient(transport=transport, base_url="http://t", headers=headers, timeout=timeout, auth=auth)

    async with streamablehttp_client("http://t/mcp", headers={"Authorization": "Bearer secret-mk",
                                                              "X-Trace-Id": "trace-http-1",
                                                              "X-GigBid-User": "user-42"},
                                     httpx_client_factory=factory) as (read, write, _):
        async with ClientSession(read, write) as s:
            await s.initialize()
            res = await s.call_tool("get_connects_balance", {})
            assert res.structuredContent["balance"] == 30
    await app.manager.shutdown()
    rec = json.loads(isolated_runtime.read_text().splitlines()[-1])
    assert rec["user"] == "user-42" and rec["trace_id"] == "trace-http-1"


async def test_resource_and_prompt(fake):
    async with connect(mk.mcp._mcp_server) as c:
        t = {x.uriTemplate for x in (await c.list_resource_templates()).resourceTemplates}
        assert "marketplace://job/{job_id}" in t
        job = await c.read_resource("marketplace://job/job-001")
        assert json.loads(job.contents[0].text)["id"] == "job-001"
        p = await c.get_prompt("triage_job", {"job_id": "job-001"})
        assert "get_client_history" in p.messages[0].content.text
