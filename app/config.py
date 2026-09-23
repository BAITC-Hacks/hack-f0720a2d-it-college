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
    ai_provider: Literal["auto", "stub", "openai", "compatible"] = "auto"
    openai_model: str = Field(default="gpt-4.1-mini", min_length=1, max_length=120)
    openai_api_key: SecretStr | None = Field(default=None, repr=False)
    ai_timeout_seconds: float = Field(default=30, ge=1, le=120)
    openai_max_output_tokens: int = Field(default=4000, ge=256, le=16000)
    # Другой сервер подключается явно и никогда не наследует OPENAI_API_KEY.
    ai_base_url: str = "http://127.0.0.1:1234/v1"
    ai_model: str = ""
    ai_api_key: SecretStr | None = Field(default=None, repr=False)
    ai_timeout: float = Field(default=180, ge=5, le=600)
    ai_max_tokens: int = Field(default=4096, ge=256, le=16384)
    ai_response_format: Literal["auto", "json_schema", "json_object", "text"] = "auto"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./ai_sana.db"),
        ai_provider=os.getenv("AI_PROVIDER", "auto").strip().lower(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip() or None,
        ai_timeout_seconds=os.getenv("OPENAI_TIMEOUT_SECONDS", "30"),
        openai_max_output_tokens=os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "4000"),
        ai_base_url=os.getenv("AI_BASE_URL", "http://127.0.0.1:1234/v1").strip(),
        ai_model=os.getenv("AI_MODEL", "").strip(),
        ai_api_key=os.getenv("AI_API_KEY", "").strip() or None,
        ai_timeout=os.getenv("AI_TIMEOUT", "180"),
        ai_max_tokens=os.getenv("AI_MAX_TOKENS", "4096"),
        ai_response_format=os.getenv("AI_RESPONSE_FORMAT", "auto").strip(),
    )
