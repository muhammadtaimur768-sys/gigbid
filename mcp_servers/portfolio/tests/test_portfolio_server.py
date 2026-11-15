import json

import httpx
from mcp.shared.memory import create_connected_server_and_client_session as connect

from mcp_servers.portfolio.gigbid_portfolio_mcp.server import build_http_app, mcp


async def test_tools_listed_with_read_only_annotations(mini_portfolio):
    async with connect(mcp._mcp_server) as c:
        tools = {t.name: t for t in (await c.list_tools()).tools}
    assert {"search_evidence", "get_case_study", "list_skills"} <= set(tools)
    for t in tools.values():
        assert t.annotations.readOnlyHint is True and t.annotations.destructiveHint is False
        assert t.outputSchema is not None
    k = tools["search_evidence"].inputSchema["properties"]["k"]
    assert k["minimum"] == 1 and k["maximum"] == 20


async def test_search_evidence_returns_typed_items(mini_portfolio):
    async with connect(mcp._mcp_server) as c:
        r = await c.call_tool("search_evidence", {"requirement": "RAG pipeline with reranker", "k": 3})
    assert not r.isError
    items = r.structuredContent["items"]
    assert items and items[0]["item_id"] == "aiml-case-01"
    assert {"type", "source", "date", "outcome"} <= set(items[0])
    assert r.structuredContent["backend"] == "keyword"


async def test_search_filters_and_constraints(mini_portfolio):
    async with connect(mcp._mcp_server) as c:
        r = await c.call_tool("search_evidence", {"requirement": "rag", "filters": {"type": ["proposal"],
                                                                                   "outcome": ["won"]}})
        assert [i["type"] for i in r.structuredContent["items"]] == ["proposal"]
        bad = await c.call_tool("search_evidence", {"requirement": "rag", "k": 99})
        assert bad.isError


async def test_get_case_study_and_not_found(mini_portfolio):
    async with connect(mcp._mcp_server) as c:
        r = await c.call_tool("get_case_study", {"id": "aiml-case-02"})
        assert r.structuredContent["project"] == "churnviz"
        missing = await c.call_tool("get_case_study", {"id": "aiml-case-99"})
        assert missing.isError and "not_found" in missing.content[0].text


async def test_list_skills(mini_portfolio):
    async with connect(mcp._mcp_server) as c:
        r = await c.call_tool("list_skills", {})
    skills = {s["skill"]: s for s in r.structuredContent["skills"]}
    assert skills["rag"]["count"] >= 2


async def test_resources_and_templates(mini_portfolio):
    async with connect(mcp._mcp_server) as c:
        templates = {t.uriTemplate for t in (await c.list_resource_templates()).resourceTemplates}
        assert {"portfolio://case/{id}", "portfolio://proposal/{id}", "portfolio://repo/{id}"} <= templates
        case = await c.read_resource("portfolio://case/aiml-case-01")
        assert json.loads(case.contents[0].text)["title"] == "Legal RAG assistant"
        repo = await c.read_resource("portfolio://repo/aiml-repo-01")
        assert "BM25Okapi" in json.loads(repo.contents[0].text)["text"]
        prop = await c.read_resource("portfolio://proposal/aiml-prop-001")
        assert json.loads(prop.contents[0].text)["outcome"] == "won"


async def test_prompts(mini_portfolio):
    async with connect(mcp._mcp_server) as c:
        names = {p.name for p in (await c.list_prompts()).prompts}
        assert len(names) >= 3 and "answer_screening_question" in names
        p = await c.get_prompt("answer_screening_question", {"question": "Have you built RAG?"})
        assert "search_evidence" in p.messages[0].content.text


async def test_http_requires_bearer(mini_portfolio, monkeypatch):
    monkeypatch.setenv("MCP_PORTFOLIO_TOKEN", "secret-portfolio")
    app = build_http_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as h:
        assert (await h.get("/health")).status_code == 200
        r = await h.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert r.status_code == 401
        r = await h.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                         headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401
