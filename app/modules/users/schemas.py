"""Pydantic-схемы выбора пользователя и ответа API пользователей."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoginRequest(BaseModel):
    user_id: int = Field(gt=0)
    role: Literal["business", "team"] | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: Literal["business", "team"]
    team_id: int | None

    @model_validator(mode="after")
    def team_user_has_team(self) -> "UserRead":
        if self.role == "team" and self.team_id is None:
            raise ValueError("Пользователь команды должен быть связан с командой")
        return self
