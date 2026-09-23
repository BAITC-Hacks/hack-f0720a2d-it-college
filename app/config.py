"""Настройки приложения, загружаемые из переменных окружения и локального .env."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
<<<<<<< HEAD
from pydantic import BaseModel, ConfigDict, Field, SecretStr
=======
from pydantic import BaseModel, ConfigDict, Field
>>>>>>> ab5a473797132f7124443376acd5c95546baa5a2

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class Settings(BaseModel):
    """Минимальный набор настроек модульного монолита."""

    model_config = ConfigDict(frozen=True)

    database_url: str = "sqlite:///./ai_sana.db"
<<<<<<< HEAD
    ai_provider: Literal["auto", "stub", "openai"] = "auto"
    openai_model: str = Field(default="gpt-4.1-mini", min_length=1, max_length=120)
    openai_api_key: SecretStr | None = Field(default=None, repr=False)
    ai_timeout_seconds: float = Field(default=30, ge=1, le=120)
    openai_max_output_tokens: int = Field(default=4000, ge=256, le=16000)
=======
    ai_base_url: str = "http://127.0.0.1:1234/v1"
    ai_model: str = ""
    ai_api_key: str = Field(default="", repr=False)
    ai_timeout: float = Field(default=180, ge=5, le=600)
    ai_max_tokens: int = Field(default=4096, ge=256, le=16384)
    ai_response_format: str = "auto"
>>>>>>> ab5a473797132f7124443376acd5c95546baa5a2


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./ai_sana.db"),
<<<<<<< HEAD
        ai_provider=os.getenv("AI_PROVIDER", "auto").strip().lower(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip() or None,
        ai_timeout_seconds=os.getenv("OPENAI_TIMEOUT_SECONDS", "30"),
        openai_max_output_tokens=os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "4000"),
=======
        ai_base_url=os.getenv("AI_BASE_URL", os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")),
        ai_model=os.getenv("AI_MODEL", ""),
        ai_api_key=os.getenv("AI_API_KEY", os.getenv("OPENAI_API_KEY", "")),
        ai_timeout=os.getenv("AI_TIMEOUT", "180"),
        ai_max_tokens=os.getenv("AI_MAX_TOKENS", "4096"),
        ai_response_format=os.getenv("AI_RESPONSE_FORMAT", "auto"),
>>>>>>> ab5a473797132f7124443376acd5c95546baa5a2
    )
