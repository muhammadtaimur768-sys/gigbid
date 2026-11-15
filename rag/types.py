"""Shared data models for the retrieval layer."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    chunk_id: str  # "{item_id}#c{n}"
    item_id: str
    persona: str
    type: str  # cv | case_study | repo | code | proposal | review | summary
    project: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    date: Optional[str] = None
    client_industry: Optional[str] = None
    outcome: Optional[str] = None  # won | replied | ignored (proposals only)
    text: str
    context: Optional[str] = None
    parent_id: Optional[str] = None
    source: Optional[str] = None  # file path or URL the chunk came from
    title: Optional[str] = None


class Evidence(BaseModel):
    chunk_id: str
    item_id: str
    type: str
    source: Optional[str] = None
    project: Optional[str] = None
    date: Optional[str] = None
    outcome: Optional[str] = None
    text: str
    score: float = 0.0
    skills: list[str] = Field(default_factory=list)
    rerank_score: Optional[float] = None


class Item(BaseModel):
    """One portfolio item (the unit gold evidence is labelled at)."""

    item_id: str
    persona: str
    type: str  # cv | case_study | repo | proposal | review
    title: Optional[str] = None
    project: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    date: Optional[str] = None
    client_industry: Optional[str] = None
    outcome: Optional[str] = None
    text: str = ""  # main prose (README for repos)
    source: Optional[str] = None
    # repos only: [{path, text}] code files
    files: list[dict] = Field(default_factory=list)
    extra: dict = Field(default_factory=dict)
