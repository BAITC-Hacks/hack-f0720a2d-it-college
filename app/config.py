"""Настройки приложения, загружаемые из переменных окружения и локального .env."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

load_dotenv()


class Settings(BaseModel):
    """Минимальный набор настроек модульного монолита."""

    model_config = ConfigDict(frozen=True)

    database_url: str = "sqlite:///./ai_sana.db"
    openai_model: str = "gpt-4.1-mini"
    openai_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./ai_sana.db"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )
