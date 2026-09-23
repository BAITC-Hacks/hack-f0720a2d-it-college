"""Pydantic-схемы черновика, карточки и переходов статуса задачи."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class DraftCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
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
    model_config = ConfigDict(extra="forbid")
    answers: dict[str, str] = Field(min_length=1)

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, values: dict[str, str]) -> dict[str, str]:
        limits = {"title": 240, "industry": 120, "context": 10000, "need": 10000,
                  "users": 10000, "data": 10000, "constraints": 10000,
                  "expected_result": 10000, "success_criteria": 10000, "contact": 10000}
        for field, value in values.items():
            if field not in limits:
                raise ValueError("Неизвестное поле ответа")
            if len(value) > limits[field]:
                raise ValueError(f"Поле {field}: не более {limits[field]} символов")
        return {field: value.strip() for field, value in values.items()}


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_updated_at: datetime | None = None


class TaskPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=240)
    industry: str | None = Field(default=None, max_length=120)
    raw_text: str | None = Field(default=None, min_length=1, max_length=10_000)
    context: str | None = Field(default=None, max_length=10000)
    need: str | None = Field(default=None, max_length=10000)
    users: str | None = Field(default=None, max_length=10000)
    data: str | None = Field(default=None, max_length=10000)
    constraints: str | None = Field(default=None, max_length=10000)
    expected_result: str | None = Field(default=None, max_length=10000)
    success_criteria: str | None = Field(default=None, max_length=10000)
    contact: str | None = Field(default=None, max_length=10000)

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
    indicators: dict[str, Any]
    potential_score: float
    confirmed_fields: list[str]
    unconfirmed_fields: list[str]
    missing: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
