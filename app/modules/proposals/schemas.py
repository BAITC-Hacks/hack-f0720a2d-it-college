"""Pydantic-схемы отклика команды и отправки фактического результата этапа."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, field_validator


class ProposalCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    task_id: int = Field(gt=0)
    idea: str = Field(min_length=10, max_length=5_000)
    plan: str = Field(min_length=10, max_length=5_000)
    deadline: str = Field(min_length=2, max_length=120)
    link: str | None = Field(default=None, max_length=500)

    @field_validator("idea", "plan", "deadline")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Поле не может быть пустым")
        return value

    @field_validator("link")
    @classmethod
    def clean_link(cls, value: str | None) -> str | None:
        if not value:
            return None
        try:
            TypeAdapter(HttpUrl).validate_python(value)
        except ValueError as exc:
            raise ValueError("Ссылка должна начинаться с http:// или https://") from exc
        return value


class ProgressSubmit(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    description: str = Field(min_length=30, max_length=5_000, validation_alias=AliasChoices("description", "summary"))
    link: str | None = Field(default=None, max_length=500)

    @field_validator("link")
    @classmethod
    def clean_link(cls, value: str | None) -> str | None:
        if not value:
            return None
        try:
            TypeAdapter(HttpUrl).validate_python(value)
        except ValueError as exc:
            raise ValueError("Ссылка должна начинаться с http:// или https://") from exc
        return value


class ProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proposal_id: int
    description: str
    summary: str
    link: str | None
    status: Literal["submitted", "confirmed"]
    points: int
    submitted_at: datetime
    confirmed_at: datetime | None
    confirmed_by: int | None

    @field_validator("submitted_at", "confirmed_at", mode="before")
    @classmethod
    def normalize_sqlite_utc(cls, value: datetime | None) -> datetime | None:
        # SQLite хранит DateTime без timezone: API стабильно возвращает UTC.
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class ProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    team_id: int
    idea: str
    plan: str
    deadline: str
    link: str | None
    status: Literal["pending", "accepted", "rejected"]
    created_at: datetime
    progress: ProgressRead | None = None
