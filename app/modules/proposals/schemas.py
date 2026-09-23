"""Pydantic-схемы создания и просмотра отклика команды."""

from datetime import datetime
from typing import Literal

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
    created_at: datetime
