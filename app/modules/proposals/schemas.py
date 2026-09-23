"""Pydantic-схемы создания и просмотра отклика команды."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProposalCreate(BaseModel):
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
        return value.strip() or None if value is not None else None


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
