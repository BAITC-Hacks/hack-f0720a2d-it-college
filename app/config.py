"""Настройки приложения, загружаемые из переменных окружения и локального .env."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

load_dotenv()


class Settings(BaseModel):
    """Минимальный набор настроек модульного монолита."""

    model_config = ConfigDict(frozen=True)

    database_url: str = "sqlite:///./ai_sana.db"
    ai_base_url: str = "http://127.0.0.1:1234/v1"
    ai_model: str = ""
    ai_api_key: str = Field(default="", repr=False)
    ai_timeout: float = Field(default=180, ge=5, le=600)
    ai_max_tokens: int = Field(default=4096, ge=256, le=16384)
    ai_response_format: str = "auto"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./ai_sana.db"),
        ai_base_url=os.getenv("AI_BASE_URL", os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")),
        ai_model=os.getenv("AI_MODEL", ""),
        ai_api_key=os.getenv("AI_API_KEY", os.getenv("OPENAI_API_KEY", "")),
        ai_timeout=os.getenv("AI_TIMEOUT", "180"),
        ai_max_tokens=os.getenv("AI_MAX_TOKENS", "4096"),
        ai_response_format=os.getenv("AI_RESPONSE_FORMAT", "auto"),
    )
