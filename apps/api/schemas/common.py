from __future__ import annotations

import datetime as dt
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Persona = Literal["aiml", "fullstack", "data"]
Autonomy = Literal["manual", "assisted", "autopilot"]


# ---- auth / onboarding ----
class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=255)


class LoginIn(BaseModel):
    email: str
    password: str


class Rates(BaseModel):
    hourly_floor: Optional[float] = Field(default=None, ge=0)
    hourly_target: Optional[float] = Field(default=None, ge=0)
    fixed_min: Optional[float] = Field(default=None, ge=0)


class Filters(BaseModel):
    categories: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    min_budget: Optional[float] = None
    exclude_keywords: list[str] = Field(default_factory=list)


class Budgets(BaseModel):
    weekly_connects: int = Field(default=80, ge=0, le=1000)
    max_connects_per_proposal: int = Field(default=16, ge=0, le=100)
    max_cost_usd_per_proposal: float = Field(default=0.05, ge=0)


class UserSettings(BaseModel):
    autonomy: Autonomy = "manual"
    rates: Rates = Field(default_factory=Rates)
    filters: Filters = Field(default_factory=Filters)
    budgets: Budgets = Field(default_factory=Budgets)
    marketplace_mode: Literal["gigsim", "upwork"] = "gigsim"


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    persona: Optional[str]
    onboarded: bool
    settings: UserSettings


class AuthOut(BaseModel):
    user: UserOut
    access_token: str
    token_type: str = "bearer"


class OnboardingIn(BaseModel):
    persona: Persona
    rates: Optional[Rates] = None
    filters: Optional[Filters] = None
    budgets: Optional[Budgets] = None
    autonomy: Optional[Autonomy] = None


class MarketplaceConnectIn(BaseModel):
    mode: Literal["gigsim", "upwork"] = "gigsim"
    token: Optional[str] = Field(default=None, description="GigSim bearer token; defaults to the persona's demo token")


class MarketplaceConnectOut(BaseModel):
    mode: str
    connected: bool
    detail: str = ""
    authorize_url: Optional[str] = None


class PortfolioUploadOut(BaseModel):
    filename: str
    bytes: int
    indexed: bool
    detail: str = ""


class OkOut(BaseModel):
    ok: bool = True
    detail: str = ""


# ---- jobs / inbox ----
class RiskFlagOut(BaseModel):
    code: str
    severity: Optional[str] = None
    evidence: str = ""


class InboxItemOut(BaseModel):
    job_id: str
    title: str
    category: str = ""
    skills_required: list[str] = Field(default_factory=list)
    budget_type: str = "fixed"
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    posted_at: Optional[str] = None
    proposals_count: Optional[int] = None
    connects_cost: Optional[int] = None
    fit_score: float
    recommended_action: Literal["bid", "watch", "skip"]
    risk_level: Literal["low", "medium", "high"]
    risk_flags: list[RiskFlagOut] = Field(default_factory=list)
    price: Optional[float] = None
    status: str
    thread_id: Optional[str] = None
    analysed: bool = False


class InboxOut(BaseModel):
    items: list[InboxItemOut]
    total: int
    marketplace: Literal["ok", "unavailable"]
    refreshed: bool


class SkipIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class AnalyseOut(BaseModel):
    thread_id: Optional[str] = None
    status: str
    created: bool = False
    queued_degraded: bool = False
    stream_url: Optional[str] = None
    trace_id: str = ""


class JobDetailOut(BaseModel):
    job: dict[str, Any]
    inbox: Optional[InboxItemOut] = None
    client: Optional[dict[str, Any]] = None
    analysis: Optional["StateViewOut"] = None
    run_status: Optional[str] = None
    thread_id: Optional[str] = None


class StateViewOut(BaseModel):
    job: Optional[dict[str, Any]] = None
    job_spec: Optional[dict[str, Any]] = None
    risk: Optional[dict[str, Any]] = None
    fit: Optional[dict[str, Any]] = None
    decision: Optional[dict[str, Any]] = None
    price: Optional[dict[str, Any]] = None
    draft: Optional[dict[str, Any]] = None
    critiques: list[Any] = Field(default_factory=list)
    compliance: Optional[dict[str, Any]] = None
    submission: Optional[dict[str, Any]] = None
    status: Optional[Any] = None
    approval: Optional[dict[str, Any]] = None
    dry_run: Optional[Any] = None
    errors: list[Any] = Field(default_factory=list)
    reply: Optional[dict[str, Any]] = None
    intent: Optional[dict[str, Any]] = None
    status_reason: Optional[str] = None
    outcome: Optional[dict[str, Any]] = None
    usage: Optional[dict[str, Any]] = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    client: Optional[dict[str, Any]] = None
    slots: list[dict[str, Any]] = Field(default_factory=list)


# ---- proposals / approvals ----
class PendingApprovalOut(BaseModel):
    interrupt_id: Optional[str] = None
    payload: Any = None


class ProposalOut(BaseModel):
    thread_id: str
    job_id: Optional[str]
    run_status: str
    pending_approval: Optional[PendingApprovalOut] = None
    view: StateViewOut
    history: list["ApprovalOut"] = Field(default_factory=list)
    trace_id: str = ""


class ApproveIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=1000)


class EditIn(BaseModel):
    edited_text: str = Field(min_length=1, max_length=20000)
    screening_answers: Optional[list[dict[str, str]]] = None


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
    category: Optional[Literal["off_profile", "price", "risk", "tone", "unsupported_claims", "other"]] = None


class ApprovalOut(BaseModel):
    id: int
    thread_id: str
    action: str
    reason: Optional[str] = None
    diff: Optional[dict[str, Any]] = None
    created_at: dt.datetime


class ResumeOut(BaseModel):
    thread_id: str
    status: str
    action: str
    approval_id: int
    stream_url: str
    memory: Optional[dict[str, Any]] = None


class RegenerateIn(BaseModel):
    paragraph_index: int = Field(ge=0)
    instruction: Optional[str] = Field(default=None, max_length=500)


class RegenerateOut(BaseModel):
    paragraph_index: int
    paragraph: str
    cover_letter: str
    claims: list[dict[str, Any]] = Field(default_factory=list)
    source: str


class PipelineCard(BaseModel):
    job_id: str
    thread_id: Optional[str]
    title: str
    category: str
    status: str
    bid_amount: Optional[float]
    connects_spent: int
    updated_at: dt.datetime


class PipelineOut(BaseModel):
    columns: dict[str, list[PipelineCard]]
    marketplace: Literal["ok", "unavailable"]


# ---- messages ----
class ThreadOut(BaseModel):
    thread_id: str
    job_id: Optional[str] = None
    client_id: Optional[str] = None
    proposal_id: Optional[str] = None
    last_message_at: Optional[str] = None
    unread: Optional[int] = None
    pending_reply: bool = False


class ThreadsOut(BaseModel):
    threads: list[ThreadOut]
    marketplace: Literal["ok", "unavailable"]


class MessageOut(BaseModel):
    id: str
    sender: str
    body: str
    created_at: Optional[str] = None


class ThreadDetailOut(BaseModel):
    thread_id: str
    messages: list[MessageOut]
    suggestion_run: Optional[str] = None
    suggestion_status: Optional[str] = None
    pending_approval: Optional[PendingApprovalOut] = None
    reply: Optional[dict[str, Any]] = None


class ReplyDecisionIn(BaseModel):
    action: Literal["approve", "edit", "reject"]
    edited_text: Optional[str] = Field(default=None, max_length=10000)
    reason: Optional[str] = Field(default=None, max_length=1000)
    slot: Optional[dict[str, str]] = None


# ---- runs ----
class RunOut(BaseModel):
    thread_id: str
    kind: str
    job_id: Optional[str]
    status: str
    outcome: Optional[str]
    trace_id: str
    trace_url: Optional[str] = None
    error: Optional[str] = None
    attempts: int
    created_at: dt.datetime
    updated_at: dt.datetime


class RunEventOut(BaseModel):
    id: int
    event: str
    data: dict[str, Any]
    ts: dt.datetime


class RunDetailOut(RunOut):
    events: list[RunEventOut]
    pending_approval: Optional[PendingApprovalOut] = None


class TraceEventOut(BaseModel):
    node: Optional[str] = None
    event: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cost_usd: Optional[float] = None
    latency_ms: Optional[float] = None
    ts: Optional[str] = None
    payload: Optional[Any] = None


class TraceOut(BaseModel):
    trace_id: str
    thread_id: str
    events: list[TraceEventOut]
    langsmith_url: Optional[str] = None
    available: bool


# ---- analytics ----
class CategoryStat(BaseModel):
    category: str
    proposals: int
    replied: int
    hired: int
    reply_rate: Optional[float]
    hire_rate: Optional[float]
    connects_spent: int


class AnalyticsOut(BaseModel):
    by_category: list[CategoryStat]
    connects_spent_total: int
    outcomes: dict[str, int]
    connects_per_reply: Optional[float]
    cost_per_proposal_usd: Optional[float]
    latency_p50_ms: Optional[float]
    latency_p95_ms: Optional[float]
    runs_measured: int
    top_rejection_reasons: list[dict[str, Any]]
    approvals: dict[str, int]
    note: str = ""


# ---- settings ----
class SavedSearchIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    query: str = Field(default="", max_length=256)
    category: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    interval_minutes: int = Field(default=30, ge=5, le=1440)
    enabled: bool = True


class SavedSearchOut(SavedSearchIn):
    id: int
    last_run_at: Optional[dt.datetime] = None


class ConnectedAccount(BaseModel):
    provider: str
    connected: bool
    scope: str = ""
    expires_at: Optional[dt.datetime] = None


class SettingsOut(BaseModel):
    persona: Optional[str]
    settings: UserSettings
    saved_searches: list[SavedSearchOut]
    accounts: list[ConnectedAccount]


class SettingsIn(BaseModel):
    autonomy: Optional[Autonomy] = None
    rates: Optional[Rates] = None
    filters: Optional[Filters] = None
    budgets: Optional[Budgets] = None
    persona: Optional[Persona] = None
    marketplace_mode: Optional[Literal["gigsim", "upwork"]] = None


class MemoryItemOut(BaseModel):
    namespace: list[str]
    key: str
    value: Any
    kind: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MemoryOut(BaseModel):
    items: list[MemoryItemOut]
    available: bool


class MemoryDeleteIn(BaseModel):
    namespace: list[str]
    key: str


# ---- health / cron ----
class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    marketplace: Literal["ok", "unavailable"]
    marketplace_detail: str = ""
    db: Literal["ok", "error"]
    graphs: dict[str, str]
    features: dict[str, bool]
    pending_work: int
    run_mode: str
    version: str


class CronOut(BaseModel):
    searches_run: int
    jobs_seen: int
    runs_started: int
    retried: int
    marketplace: Literal["ok", "unavailable"]


class OAuthStartOut(BaseModel):
    configured: bool
    authorize_url: Optional[str] = None
    detail: str = ""


JobDetailOut.model_rebuild()
ProposalOut.model_rebuild()
