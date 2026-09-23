"""Pydantic-схема публичного профиля команды."""

from pydantic import BaseModel, ConfigDict


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    interests: list[str]
    skills: list[str]
    tech: list[str]
