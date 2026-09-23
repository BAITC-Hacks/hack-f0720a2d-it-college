"""Pydantic-схема элемента каталога опубликованных задач."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class CatalogTask(BaseModel):
    id: int
    proposals_count: int = 0
    owner_id: int
    title: str | None
    industry: str | None
    raw_text: str
    context: str | None
    need: str | None
    users: str | None
    data: str | None
    constraints: str | None
    expected_result: str | None
    success_criteria: str | None
    contact: str | None
    status: Literal["published"]
    score: float
    level: Literal["draft", "working", "ready", "priority"]
    level_label: str
    breakdown: dict[str, Any]
    indicators: dict[str, Any] = Field(default_factory=dict)
    potential_score: float = 0
    confirmed_fields: list[str] = Field(default_factory=list)
    unconfirmed_fields: list[str] = Field(default_factory=list)
    missing: list[str]
    created_at: datetime
    updated_at: datetime
