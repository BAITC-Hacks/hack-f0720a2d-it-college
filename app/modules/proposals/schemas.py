"""Pydantic-схемы создания и просмотра отклика команды."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, field_validator


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
    version: int = 1
    created_at: datetime


StageName = Literal["research", "prototype", "final"]


class MilestoneSubmission(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    stage: StageName
    description: str = Field(min_length=10, max_length=5_000)
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


class MilestoneReview(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    submission_token: UUID
    comment: str | None = Field(default=None, max_length=2_000)

    @field_validator("comment")
    @classmethod
    def clean_comment(cls, value: str | None) -> str | None:
        return value or None


class MilestoneRead(BaseModel):
    stage: StageName
    title: str
    points: int
    status: Literal["not_started", "pending", "confirmed", "rejected"]
    description: str | None = None
    link: str | None = None
    submission_token: str | None = None
    review_comment: str | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None


class ProgressRead(BaseModel):
    proposal_id: int
    team_points: int
    earned_points: int
    completion_percent: int
    stages: list[MilestoneRead]
