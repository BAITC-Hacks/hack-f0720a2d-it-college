"""Настройки приложения, загружаемые из переменных окружения и локального .env."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class Settings(BaseModel):
    """Минимальный набор настроек модульного монолита."""

    model_config = ConfigDict(frozen=True)

    database_url: str = "sqlite:///./ai_sana.db"
    ai_provider: Literal["auto", "stub", "openai"] = "auto"
    openai_model: str = Field(default="gpt-4.1-mini", min_length=1, max_length=120)
    openai_api_key: SecretStr | None = Field(default=None, repr=False)
    ai_timeout_seconds: float = Field(default=30, ge=1, le=120)
    openai_max_output_tokens: int = Field(default=4000, ge=256, le=16000)


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./ai_sana.db"),
        ai_provider=os.getenv("AI_PROVIDER", "auto").strip().lower(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip() or None,
        ai_timeout_seconds=os.getenv("OPENAI_TIMEOUT_SECONDS", "30"),
        openai_max_output_tokens=os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "4000"),
    )
