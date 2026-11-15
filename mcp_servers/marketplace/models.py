"""Pydantic input/output models for the Marketplace MCP server."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

ID_PATTERN = r"^[A-Za-z0-9_.:-]{1,64}$"
IDEMPOTENCY_PATTERN = r"^[A-Za-z0-9_.:-]{8,128}$"
MAX_COVER_LETTER = 2500  # platform policy update 2026-11-02: proposals must not exceed 2,500 characters

IdempotencyKey = Field(pattern=IDEMPOTENCY_PATTERN,
                       description="Client-chosen unique key (8-128 chars). Retrying with the same key returns "
                                   "the first result and never submits or spends Connects twice.")
DryRun = Field(default=False, description="If true, return exactly what would be sent and what it costs; "
                                          "nothing is created, sent or spent.")


# ---------- shared output shapes ----------
class Job(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    title: str
    description: str = ""
    category: str = ""
    skills_required: list[str] = Field(default_factory=list)
    budget_type: Literal["fixed", "hourly"] = "fixed"
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    duration: Optional[str] = None
    posted_at: Optional[str] = None
    client_id: Optional[str] = None
    connects_cost: Optional[int] = None
    proposals_count: Optional[int] = None
    screening_questions: list[str] = Field(default_factory=list)
    experience_level: Optional[str] = None


class JobList(BaseModel):
    jobs: list[Job]
    total: int


class ClientHistory(BaseModel):
    model_config = ConfigDict(extra="allow")
    client_id: str
    name: Optional[str] = None
    country: Optional[str] = None
    total_spent: Optional[float] = None
    hires: Optional[int] = None
    jobs_posted: Optional[int] = None
    avg_rating: Optional[float] = None
    payment_verified: Optional[bool] = None
    member_since: Optional[str] = None
    reviews: list[dict[str, Any]] = Field(default_factory=list)


class ConnectsBalance(BaseModel):
    freelancer_id: Optional[str] = None
    balance: int
    weekly_spent: Optional[int] = None


class Thread(BaseModel):
    model_config = ConfigDict(extra="allow")
    thread_id: str
    job_id: Optional[str] = None
    client_id: Optional[str] = None
    proposal_id: Optional[str] = None
    last_message_at: Optional[str] = None
    unread: Optional[int | bool] = None


class ThreadList(BaseModel):
    threads: list[Thread]


class Message(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    sender: str
    body: str
    created_at: Optional[str] = None


class MessageList(BaseModel):
    thread_id: str
    messages: list[Message]


class Quantiles(BaseModel):
    p25: Optional[float] = None
    p50: Optional[float] = None
    p75: Optional[float] = None


class MarketStats(BaseModel):
    category: Optional[str] = None
    n: int = 0
    hourly: Quantiles = Field(default_factory=Quantiles)
    fixed: Quantiles = Field(default_factory=Quantiles)


class ProposalSummary(BaseModel):
    model_config = ConfigDict(extra="allow")
    proposal_id: str
    job_id: Optional[str] = None
    status: str


class ProposalList(BaseModel):
    proposals: list[ProposalSummary]


class MarketplaceStatus(BaseModel):
    model_config = ConfigDict(extra="allow")
    ok: bool
    marketplace: str
    error: Optional[str] = None


# ---------- read inputs ----------
class SearchJobsInput(BaseModel):
    q: str = Field(default="", max_length=200, description="Free-text query over title and description.")
    category: Optional[str] = Field(default=None, max_length=80, description="Exact category name.")
    skills: list[str] = Field(default_factory=list, max_length=20, description="Required skills (any match).")
    since: Optional[datetime] = Field(default=None, description="Only jobs posted after this ISO-8601 time.")
    limit: int = Field(default=20, ge=1, le=50, description="Page size (1-50).")
    offset: int = Field(default=0, ge=0, le=10_000, description="Pagination offset.")


class GetJobInput(BaseModel):
    job_id: str = Field(pattern=ID_PATTERN, description="Job id from search_jobs, e.g. 'job-00123'.")


class GetClientHistoryInput(BaseModel):
    client_id: str = Field(pattern=ID_PATTERN, description="Client id from a job's client_id field.")


class EmptyInput(BaseModel):
    pass


class ListMessagesInput(BaseModel):
    thread_id: str = Field(pattern=ID_PATTERN, description="Thread id from list_threads.")


class MarketStatsInput(BaseModel):
    category: str = Field(min_length=1, max_length=80, description="Job category to get rate quantiles for.")


class ListProposalsInput(BaseModel):
    status: Optional[Literal["submitted", "viewed", "replied", "interview", "hired", "lost"]] = Field(
        default=None, description="Optional status filter.")


# ---------- write inputs ----------
class ScreeningAnswer(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=2000)


class ProposalPayload(BaseModel):
    job_id: str
    cover_letter: str
    screening_answers: list[ScreeningAnswer] = Field(default_factory=list)
    bid_amount: float


class _ProposalBase(BaseModel):
    job_id: str = Field(pattern=ID_PATTERN, description="Job to bid on.")
    cover_letter: str = Field(min_length=50, max_length=MAX_COVER_LETTER,
                              description="Cover letter text, 50-2500 characters.")
    screening_answers: list[ScreeningAnswer] = Field(default_factory=list, max_length=10,
                                                     description="One answer per screening question.")
    bid_amount: float = Field(gt=0, le=100_000, description="Bid in USD (hourly rate or fixed total).")
    idempotency_key: str = IdempotencyKey
    dry_run: bool = DryRun

    @model_validator(mode="after")
    def _no_contact_details(self):
        # platform rule: no off-platform contact details in proposals
        from mcp_servers.common.audit import _EMAIL, _PHONE
        if _EMAIL.search(self.cover_letter) or _PHONE.search(self.cover_letter):
            raise ValueError("cover_letter must not contain email addresses or phone numbers")
        return self

    def payload(self) -> ProposalPayload:
        return ProposalPayload(job_id=self.job_id, cover_letter=self.cover_letter,
                               screening_answers=self.screening_answers, bid_amount=self.bid_amount)


class CreateProposalDraftInput(_ProposalBase):
    pass


class SubmitProposalInput(_ProposalBase):
    draft_id: Optional[str] = Field(default=None, pattern=ID_PATTERN,
                                    description="Draft this submission was approved from (for the audit trail).")


class SendMessageInput(BaseModel):
    thread_id: str = Field(pattern=ID_PATTERN, description="Thread to reply in.")
    body: str = Field(min_length=1, max_length=5000, description="Message text (1-5000 characters).")
    idempotency_key: str = IdempotencyKey
    dry_run: bool = DryRun


# ---------- write outputs ----------
class DraftResult(BaseModel):
    draft_id: Optional[str] = None
    status: Literal["draft", "preview"]
    job_id: str
    preview: ProposalPayload
    connects_cost: Optional[int] = None
    balance_after: Optional[int] = None
    marketplace: str
    dry_run: bool = False
    replayed: bool = False
    note: str = ""


class SubmitResult(BaseModel):
    status: Literal["submitted", "would_submit", "draft_created"]
    proposal_id: Optional[str] = None
    job_id: str
    connects_spent: Optional[int] = None
    connects_cost: Optional[int] = None
    balance_after: Optional[int] = None
    would_send: Optional[ProposalPayload] = None
    marketplace: str
    dry_run: bool = False
    replayed: bool = False
    note: str = ""


class SendMessageResult(BaseModel):
    status: Literal["sent", "would_send", "draft_created"]
    thread_id: str
    message_id: Optional[str] = None
    would_send: Optional[dict[str, Any]] = None
    marketplace: str
    dry_run: bool = False
    replayed: bool = False
    note: str = ""
