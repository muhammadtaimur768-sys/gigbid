"""Structured hand-off objects exchanged between agents (C3).

Every object a later step decides on is one of these Pydantic models, never free text.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Requirement(BaseModel):
    id: str  # "r1", "r2", ...
    text: str
    kind: Literal["skill", "deliverable", "experience", "domain", "other"] = "other"
    must_have: bool = True


class JobSpec(BaseModel):
    job_id: str
    title: str
    category: str
    deliverables: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    budget_type: Literal["fixed", "hourly"] = "fixed"
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    timeline: Optional[str] = None
    screening_questions: list[str] = Field(default_factory=list)
    hidden_needs: list[str] = Field(default_factory=list)


class RiskFlag(BaseModel):
    code: Literal[
        "scam", "free_work", "off_platform_contact", "off_platform_payment",
        "prompt_injection", "low_client_quality", "unrealistic_budget", "duplicate",
    ]
    severity: Literal["low", "medium", "high"]
    evidence: str  # quoted snippet that triggered the flag


class RiskReport(BaseModel):
    job_id: str
    client_score: float = Field(ge=0, le=1)  # 1 = excellent client
    is_scam: bool
    injection_detected: bool
    flags: list[RiskFlag] = Field(default_factory=list)
    summary: str = ""


class EvidenceRef(BaseModel):
    item_id: str  # portfolio item id, e.g. "aiml-case-03"
    chunk_id: str
    type: str  # case_study | repo | code | proposal | review | cv
    snippet: str
    score: float = 0.0
    outcome: Optional[str] = None  # won | replied | ignored (proposals only)


class RequirementMatch(BaseModel):
    requirement_id: str
    requirement: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    strength: Literal["strong", "partial", "none"] = "none"


class FitReport(BaseModel):
    job_id: str
    fit_score: float = Field(ge=0, le=1)
    matches: list[RequirementMatch] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    skill_overlap: Optional[float] = None  # share of listed job skills found in the freelancer profile


class BidDecision(BaseModel):
    job_id: str
    action: Literal["bid", "watch", "skip"]
    confidence: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)


class PriceQuote(BaseModel):
    job_id: str
    amount: float
    budget_type: Literal["fixed", "hourly"]
    connects_cost: int
    worth_connects: bool
    rationale: str
    market_p25: Optional[float] = None
    market_p50: Optional[float] = None
    market_p75: Optional[float] = None


class Claim(BaseModel):
    id: str
    text: str
    status: Literal["supported", "partly_supported", "unsupported"] = "unsupported"
    evidence_ids: list[str] = Field(default_factory=list)  # chunk ids
    action: Literal["kept", "rewritten", "removed"] = "kept"


class ProposalDraft(BaseModel):
    job_id: str
    version: int = 1
    cover_letter: str
    screening_answers: list[dict] = Field(default_factory=list)  # [{question, answer}]
    claims: list[Claim] = Field(default_factory=list)
    unsupported_before: int = 0
    unsupported_after: int = 0


class Critique(BaseModel):
    job_id: str
    verdict: Literal["pass", "revise"]
    score: float = Field(ge=0, le=10)
    reasons: list[str] = Field(default_factory=list)
    round: int = 0


class ComplianceVerdict(BaseModel):
    job_id: str
    allowed: bool
    violations: list[str] = Field(default_factory=list)  # rule ids from policy pack
    redactions: list[str] = Field(default_factory=list)
    cleaned_text: Optional[str] = None
    reason: str = ""


class ApprovalDecision(BaseModel):
    action: Literal["approve", "edit", "reject"]
    edited_text: Optional[str] = None
    reason: Optional[str] = None
    user_id: Optional[str] = None


class MessageIntent(BaseModel):
    thread_id: str
    intent: Literal["question", "negotiation", "interview_request", "scam_signal", "other"]
    confidence: float = Field(ge=0, le=1)
    injection_detected: bool = False


class ReplyDraft(BaseModel):
    thread_id: str
    body: str
    proposed_slots: list[dict] = Field(default_factory=list)  # [{start, end}]
