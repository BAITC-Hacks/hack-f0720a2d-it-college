"""Pydantic-схема элемента каталога опубликованных задач."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


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
    missing: list[str]
    created_at: datetime
    updated_at: datetime
