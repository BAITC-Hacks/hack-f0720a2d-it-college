"""Pydantic-схемы результата расчёта рейтинга."""

from typing import Literal

from pydantic import BaseModel, Field


class BreakdownItem(BaseModel):
    earned: float = Field(ge=0)
    maximum: int = Field(gt=0)
    state: Literal["empty", "short", "complete"]


class RatingResult(BaseModel):
    score: float = Field(ge=0, le=100)
    level: Literal["draft", "working", "ready", "priority"]
    level_label: str
    breakdown: dict[str, BreakdownItem]
    missing: list[str]
