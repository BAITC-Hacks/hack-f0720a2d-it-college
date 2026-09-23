"""Pydantic-схемы черновика, карточки и переходов статуса задачи."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class DraftCreate(BaseModel):
    raw_text: str = Field(min_length=1, max_length=10_000)
    title: str | None = Field(default=None, max_length=240)
    industry: str | None = Field(default=None, max_length=120)

    @field_validator("raw_text")
    @classmethod
    def valid_raw_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Описание задачи не может быть пустым")
        return value

    @field_validator("title", "industry")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class CardAnswers(BaseModel):
    answers: dict[str, str] = Field(min_length=1)


class ConfirmChanges(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_token: UUID


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, max_length=240)
    industry: str | None = Field(default=None, max_length=120)
    raw_text: str | None = Field(default=None, min_length=1, max_length=10_000)
    context: str | None = None
    need: str | None = None
    users: str | None = None
    data: str | None = None
    constraints: str | None = None
    expected_result: str | None = None
    success_criteria: str | None = None
    contact: str | None = None

    @field_validator("raw_text")
    @classmethod
    def valid_raw_text(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Описание задачи не может быть пустым")
        value = value.strip()
        if not value:
            raise ValueError("Описание задачи не может быть пустым")
        return value

    @field_validator(
        "title",
        "industry",
        "context",
        "need",
        "users",
        "data",
        "constraints",
        "expected_result",
        "success_criteria",
        "contact",
    )
    @classmethod
    def clean_optional_fields(cls, value: Any) -> Any:
        return _strip_optional(value) if isinstance(value, str) else value


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
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
    status: Literal["draft", "confirmed", "published"]
    score: float
    level: Literal["draft", "working", "ready", "priority"]
    level_label: str
    breakdown: dict[str, Any]
    missing: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    has_pending_changes: bool = False
    revision_token: str | None = None
