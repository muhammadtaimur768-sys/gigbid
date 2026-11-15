"""GigBid Workspace MCP server: calendar free slots, tentative interview holds, email drafts.

Local mock backed by data/processed/workspace.json (env WORKSPACE_PATH). The agent only sees MCP
tools, so a Google Calendar / Gmail backend can replace `WorkspaceStore` without touching callers.
Run: python -m mcp_servers.workspace.server [--http]   (port 8203, bearer env MCP_WORKSPACE_TOKEN)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field, model_validator

from mcp_servers.common.audit import AuditLog
from mcp_servers.common.http import build_http_app as _build_http_app
from mcp_servers.common.http import run_http
from mcp_servers.common.idempotency import IdempotencyStore
from mcp_servers.common.ratelimit import TokenBucketLimiter
from mcp_servers.common.settings import repo_path, settings
from mcp_servers.common.toolkit import CallInfo, ToolRuntime, register_model_tool

SERVER_NAME = "workspace"
EMAIL_PATTERN = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
IdemKey = Field(pattern=r"^[A-Za-z0-9_.:-]{8,128}$", description="Unique key; retries never create duplicates.")
DryRun = Field(default=False, description="Preview only; nothing is created.")


class WorkspaceStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else repo_path(os.environ.get("WORKSPACE_PATH",
                                                                     settings()["workspace"]["path"]))
        self._lock = threading.Lock()

    def load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {"busy": [], "holds": [], "drafts": []}

    def save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str))
        tmp.replace(self.path)


store = WorkspaceStore()
mcp = FastMCP("gigbid-workspace", instructions="Calendar and email-draft tools for the freelancer. Holds are "
                                               "tentative; drafts are never sent automatically.")
runtime = ToolRuntime(server=SERVER_NAME, limiter=TokenBucketLimiter(), audit=AuditLog(), idem=IdempotencyStore())


def set_store(s: WorkspaceStore) -> None:
    global store
    store = s


def _dt(v: str | datetime) -> datetime:
    d = v if isinstance(v, datetime) else datetime.fromisoformat(str(v))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


# ---------------- models ----------------
class FreeSlotsInput(BaseModel):
    days: int = Field(default=5, ge=1, le=14, description="Look-ahead in working days.")
    duration_min: int = Field(default=30, ge=15, le=240, description="Slot length in minutes.")
    from_date: Optional[date] = Field(default=None, description="First day to search (default: tomorrow).")
    max_slots: int = Field(default=10, ge=1, le=50)


class Slot(BaseModel):
    start: datetime
    end: datetime


class FreeSlots(BaseModel):
    timezone: str
    duration_min: int
    slots: list[Slot]


class HoldInput(BaseModel):
    start: datetime = Field(description="ISO-8601 start (UTC if no offset).")
    end: datetime = Field(description="ISO-8601 end, after start, at most 4 hours later.")
    title: str = Field(min_length=1, max_length=200)
    attendee: str = Field(min_length=1, max_length=200, description="Client name or platform handle.")
    idempotency_key: str = IdemKey
    dry_run: bool = DryRun

    @model_validator(mode="after")
    def _check(self):
        s, e = _dt(self.start), _dt(self.end)
        if e <= s:
            raise ValueError("end must be after start")
        if e - s > timedelta(hours=4):
            raise ValueError("hold longer than 4 hours")
        return self


class HoldResult(BaseModel):
    status: Literal["tentative", "preview"]
    hold_id: Optional[str] = None
    start: datetime
    end: datetime
    title: str
    attendee: str
    dry_run: bool = False
    replayed: bool = False


class EmailDraftInput(BaseModel):
    to: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)
    idempotency_key: str = IdemKey
    dry_run: bool = DryRun


class EmailDraftResult(BaseModel):
    status: Literal["draft", "preview"]
    draft_id: Optional[str] = None
    to: str
    subject: str
    body: str
    dry_run: bool = False
    replayed: bool = False


class EmptyInput(BaseModel):
    pass


class HoldList(BaseModel):
    holds: list[HoldResult]


# ---------------- handlers ----------------
def _busy(data: dict) -> list[tuple[datetime, datetime]]:
    return [(_dt(b["start"]), _dt(b["end"])) for b in data.get("busy", []) + data.get("holds", [])]


async def _free_slots(p: FreeSlotsInput, info: CallInfo) -> FreeSlots:
    cfg = settings()["workspace"]
    busy = _busy(store.load())
    day = p.from_date or (datetime.now(timezone.utc).date() + timedelta(days=1))
    slots: list[Slot] = []
    seen_days = 0
    step = timedelta(minutes=30)
    dur = timedelta(minutes=p.duration_min)
    while seen_days < p.days and len(slots) < p.max_slots:
        if day.weekday() < 5:
            seen_days += 1
            t = datetime.combine(day, time(cfg["work_day_start_hour"]), tzinfo=timezone.utc)
            end_of_day = datetime.combine(day, time(cfg["work_day_end_hour"]), tzinfo=timezone.utc)
            while t + dur <= end_of_day and len(slots) < p.max_slots:
                if all(t + dur <= b0 or t >= b1 for b0, b1 in busy):
                    slots.append(Slot(start=t, end=t + dur))
                    t += dur
                else:
                    t += step
        day += timedelta(days=1)
    return FreeSlots(timezone=cfg["timezone"], duration_min=p.duration_min, slots=slots)


async def _create_hold(p: HoldInput, info: CallInfo) -> HoldResult:
    s, e = _dt(p.start), _dt(p.end)
    with store._lock:
        data = store.load()
        if any(s < b1 and e > b0 for b0, b1 in _busy(data)):
            raise ValueError("slot is not free; call free_slots first")
        hold_id = "hold-" + hashlib.sha256(f"{info.user}|{p.idempotency_key}".encode()).hexdigest()[:10]
        out = HoldResult(status="preview" if p.dry_run else "tentative", hold_id=None if p.dry_run else hold_id,
                         start=s, end=e, title=p.title, attendee=p.attendee, dry_run=p.dry_run)
        if not p.dry_run:
            data.setdefault("holds", []).append({**out.model_dump(mode="json"), "user": info.user})
            store.save(data)
    return out


async def _create_email_draft(p: EmailDraftInput, info: CallInfo) -> EmailDraftResult:
    draft_id = "mail-" + hashlib.sha256(f"{info.user}|{p.idempotency_key}".encode()).hexdigest()[:10]
    out = EmailDraftResult(status="preview" if p.dry_run else "draft", draft_id=None if p.dry_run else draft_id,
                           to=p.to, subject=p.subject, body=p.body, dry_run=p.dry_run)
    if not p.dry_run:
        with store._lock:
            data = store.load()
            data.setdefault("drafts", []).append({**out.model_dump(mode="json"), "user": info.user})
            store.save(data)
    return out


async def _list_holds(p: EmptyInput, info: CallInfo) -> HoldList:
    return HoldList(holds=[HoldResult(**{k: v for k, v in h.items() if k != "user"})
                           for h in store.load().get("holds", [])])


RO = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
register_model_tool(mcp, runtime, name="free_slots", input_model=FreeSlotsInput, output_model=FreeSlots,
                    handler=_free_slots, annotations=RO.model_copy(update={"title": "Find free calendar slots"}),
                    description="Find free working-hour calendar slots for an interview.")
register_model_tool(mcp, runtime, name="list_holds", input_model=EmptyInput, output_model=HoldList,
                    handler=_list_holds, annotations=RO.model_copy(update={"title": "List interview holds"}),
                    description="List tentative interview holds already on the calendar.")
register_model_tool(
    mcp, runtime, name="create_interview_hold", input_model=HoldInput, output_model=HoldResult, handler=_create_hold,
    annotations=ToolAnnotations(title="Create tentative interview hold", readOnlyHint=False, destructiveHint=False,
                                idempotentHint=True, openWorldHint=False),
    description="Put a tentative interview hold on the calendar (must be a free slot). Requires idempotency_key; "
                "dry_run previews.", write=True)
register_model_tool(
    mcp, runtime, name="create_email_draft", input_model=EmailDraftInput, output_model=EmailDraftResult,
    handler=_create_email_draft,
    annotations=ToolAnnotations(title="Create email draft", readOnlyHint=False, destructiveHint=False,
                                idempotentHint=True, openWorldHint=False),
    description="Save an email draft (never sent automatically). Requires idempotency_key; dry_run previews.",
    write=True)


@mcp.resource("workspace://holds", name="holds", mime_type="application/json",
              description="All tentative interview holds.")
def holds_resource() -> str:
    return json.dumps(store.load().get("holds", []), default=str)


@mcp.prompt(name="schedule_interview", title="Propose interview times to a client")
def schedule_interview(client_name: str, duration_min: int = 30) -> str:
    return (f"Call free_slots with duration_min={duration_min} and pick three options on different days. "
            f"Write a short reply to {client_name} offering them (with timezone). Create a hold only after the "
            "client picks a time and the user approves.")


def build_http_app():
    """ASGI app with bearer auth (env MCP_WORKSPACE_TOKEN); mount at /mcp/workspace."""
    return _build_http_app(mcp, SERVER_NAME)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="GigBid workspace MCP server")
    ap.add_argument("--http", action="store_true")
    ap.add_argument("--port", type=int, default=int(os.environ.get("MCP_WORKSPACE_PORT",
                                                                   settings()["ports"]["workspace"])))
    args = ap.parse_args(argv)
    if args.http:
        run_http(build_http_app(), args.port)
    else:
        mcp.run("stdio")


if __name__ == "__main__":
    main()
