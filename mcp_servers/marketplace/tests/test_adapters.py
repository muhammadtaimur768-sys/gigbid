import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest
from cryptography.fernet import Fernet
from mcp.shared.auth import OAuthToken

from mcp_servers.marketplace.adapters.base import InsufficientConnects, MarketplaceNotFound, MarketplaceUnavailable
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
from mcp_servers.marketplace.adapters.token_store import EncryptedTokenStore, TokenStoreError, UserTokenStorage
from mcp_servers.marketplace.adapters.upwork_live import UpworkLiveAdapter, load_tool_map


async def _nosleep(_):
    return None


def gigsim(handler, tmp_path, retries=3):
    return GigSimAdapter("http://gs", "gs-aiml-token", transport=httpx.MockTransport(handler), max_retries=retries,
                         sleep=_nosleep, drafts_path=tmp_path / "drafts.json")


# ---------------- GigSim adapter ----------------
async def test_gigsim_retries_then_succeeds(tmp_path):
    calls = []

    def h(req):
        calls.append(req)
        assert req.headers["authorization"] == "Bearer gs-aiml-token"
        if len(calls) == 1:
            return httpx.Response(503)
        if len(calls) == 2:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json={"freelancer_id": "fl-aiml", "balance": 40, "weekly_spent": 0})

    a = gigsim(h, tmp_path)
    assert (await a.get_connects())["balance"] == 40
    assert a.attempts_log == [503, 429, 200]


async def test_gigsim_bounded_retries_raise_unavailable(tmp_path):
    def h(req):
        raise httpx.ConnectError("refused")

    a = gigsim(h, tmp_path, retries=2)
    with pytest.raises(MarketplaceUnavailable):
        await a.search_jobs(q="rag")
    assert len(a.attempts_log) == 3


async def test_gigsim_typed_4xx(tmp_path):
    def h(req):
        return httpx.Response(404 if req.url.path.startswith("/jobs/") else 402, json={"detail": "no"})

    a = gigsim(h, tmp_path)
    with pytest.raises(MarketplaceNotFound):
        await a.get_job("job-x")
    with pytest.raises(InsufficientConnects):
        await a.submit_proposal({"job_id": "j", "cover_letter": "c", "bid_amount": 1}, "key-12345", False)
    assert a.attempts_log == [404, 402]  # 4xx never retried


async def test_gigsim_dry_run_and_draft(tmp_path):
    seen = []

    def h(req):
        body = json.loads(req.content)
        seen.append(body)
        assert body["idempotency_key"] == "key-12345"
        return httpx.Response(200, json={"would_send": body, "connects_cost": 14, "balance_after": 26})

    a = gigsim(h, tmp_path)
    payload = {"job_id": "job-1", "cover_letter": "c", "bid_amount": 50, "screening_answers": []}
    r = await a.submit_proposal(payload, "key-12345", True)
    assert r["status"] == "would_submit" and r["connects_cost"] == 14
    d = await a.create_proposal_draft(payload, "key-12345", False)
    assert d["status"] == "draft" and d["draft_id"] in json.loads((tmp_path / "drafts.json").read_text())
    assert all(b["dry_run"] is True for b in seen)


async def test_gigsim_against_real_app_if_available(tmp_path, monkeypatch):
    app_mod = pytest.importorskip("gigsim.app")
    monkeypatch.setenv("GIGSIM_ERROR_RATE", "0")
    a = GigSimAdapter("http://gs", "gs-aiml-token", transport=httpx.ASGITransport(app=app_mod.app),
                      sleep=_nosleep, drafts_path=tmp_path / "d.json")
    try:
        jobs = await a.search_jobs(limit=3)
    except MarketplaceUnavailable:
        pytest.skip("gigsim app not seeded")
    assert "jobs" in jobs


# ---------------- token store ----------------
async def test_token_store_encrypts_per_user(tmp_path):
    key = Fernet.generate_key()
    store = EncryptedTokenStore(tmp_path, key)
    s = UserTokenStorage(store, "user@1")
    await s.set_tokens(OAuthToken(access_token="at-secret", token_type="Bearer", refresh_token="rt"))
    raw = next(tmp_path.glob("*.tokens.enc")).read_bytes()
    assert b"at-secret" not in raw
    assert (await s.get_tokens()).access_token == "at-secret"
    assert await UserTokenStorage(store, "other").get_tokens() is None
    with pytest.raises(TokenStoreError):
        EncryptedTokenStore(tmp_path, Fernet.generate_key()).get("user@1", "tokens")


# ---------------- Upwork live adapter (fake MCP client) ----------------
class FakeUpworkSession:
    def __init__(self, log):
        self.log = log

    async def list_tools(self):
        names = ["search_jobs", "get_job_details", "create_proposal_draft", "create_message_draft"]
        return SimpleNamespace(tools=[SimpleNamespace(name=n) for n in names])

    async def call_tool(self, name, args):
        self.log.append((name, args))
        data = {
            "search_jobs": {"jobs": [{"job_id": "~01abc", "title": "RAG", "skills": ["python"],
                                      "budget_type": "hourly", "budget_max": 60}]},
            "get_job_details": {"job_id": "~01abc", "title": "RAG", "skills": ["python"]},
            "create_proposal_draft": {"id": "upw-draft-9"},
            "create_message_draft": {"id": "upw-msg-3"},
        }[name]
        return SimpleNamespace(structuredContent=data, content=[], isError=False)


class FakeMultiServerClient:
    def __init__(self, connections, log):
        self.connections, self.log = connections, log

    @asynccontextmanager
    async def session(self, name):
        assert name == "upwork"
        yield FakeUpworkSession(self.log)


@pytest.fixture
def upwork(tmp_path):
    log, conns = [], []
    store = EncryptedTokenStore(tmp_path, Fernet.generate_key())
    store.put("u1", "tokens", {"access_token": "upw-at", "token_type": "Bearer"})
    clock = [1000.0]

    def factory(c):
        conns.append(c)
        return FakeMultiServerClient(c, log)

    a = UpworkLiveAdapter("u1", client_factory=factory, token_store=store, clock=lambda: clock[0])
    return a, log, conns, clock


async def test_upwork_maps_reads_and_uses_bearer(upwork):
    a, log, conns, _ = upwork
    res = await a.search_jobs(q="rag", limit=5)
    assert log[0] == ("search_jobs", {"query": "rag", "limit": 5, "offset": 0})
    assert res["jobs"][0]["id"] == "~01abc" and res["jobs"][0]["skills_required"] == ["python"]
    c = conns[0]["upwork"]
    assert c["transport"] == "streamable_http" and c["url"] == "https://mcp.upwork.com/mcp"
    assert c["headers"]["Authorization"] == "Bearer upw-at"
    job = await a.get_job("~01abc")
    assert log[-1][0] == "get_job_details" and job["id"] == "~01abc"


async def test_upwork_writes_only_create_drafts(upwork):
    a, log, _, _ = upwork
    payload = {"job_id": "~01abc", "cover_letter": "hello", "bid_amount": 55, "screening_answers": []}
    r = await a.submit_proposal(payload, "k-123456", False)
    assert r["status"] == "draft_created" and r["proposal_id"] == "upw-draft-9"
    assert log[-1] == ("create_proposal_draft", {"job_id": "~01abc", "cover_letter": "hello", "charge_amount": 55,
                                                 "answers": []})
    m = await a.send_message("room-1", "hi", "k-654321", False)
    assert m["status"] == "draft_created" and log[-1] == ("create_message_draft", {"room_id": "room-1", "text": "hi"})
    assert all("draft" in name or not name.startswith(("create", "submit", "send")) for name, _ in log)
    n = len(log)
    await a.submit_proposal(payload, "k-123456", True)
    assert len(log) == n  # dry run never calls Upwork


async def test_upwork_read_throttle(upwork):
    a, log, _, clock = upwork
    await a.search_jobs(q="rag")
    await a.search_jobs(q="rag")
    assert len(log) == 1
    clock[0] += a.min_read_interval_s + 1
    await a.search_jobs(q="rag")
    assert len(log) == 2


async def test_upwork_verify_mapping_reports_missing(upwork):
    a, *_ = upwork
    missing = await a.verify_mapping()
    assert "get_client_details" in missing and "search_jobs" not in missing


async def test_upwork_not_connected_is_unavailable(tmp_path):
    store = EncryptedTokenStore(tmp_path, Fernet.generate_key())
    a = UpworkLiveAdapter("nobody", client_factory=lambda c: None, token_store=store)
    with pytest.raises(MarketplaceUnavailable):
        await a.get_job("x")


def test_tool_map_rejects_non_draft_writes(tmp_path):
    bad = tmp_path / "map.yaml"
    bad.write_text("methods:\n  create_proposal_draft: {tool: create_proposal_draft, draft_only: true}\n"
                   "  submit_proposal: {tool: submit_proposal}\n"
                   "  send_message: {tool: create_message_draft, draft_only: true}\n")
    with pytest.raises(ValueError):
        load_tool_map(bad)
    assert load_tool_map()["methods"]["submit_proposal"]["tool"] == "create_proposal_draft"
