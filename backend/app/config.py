import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    database_path: Path = BACKEND_DIR / "data" / "backend.sqlite3"
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://localhost:3000")
    ai_provider: str = "mock"
    openai_api_key: str = field(default="", repr=False)
    openai_model: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    ai_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.ai_provider not in {"mock", "openai"}:
            raise ValueError("AI_PROVIDER должен быть mock или openai")
        if self.ai_provider == "openai" and (
            not self.openai_api_key or not self.openai_model
        ):
            raise ValueError("Для AI_PROVIDER=openai задайте OPENAI_API_KEY и OPENAI_MODEL")
        if not 0 < self.ai_timeout_seconds <= 120:
            raise ValueError("AI_TIMEOUT_SECONDS должен быть в пределах (0, 120]")

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(BACKEND_DIR / ".env", override=False)
        path = Path(os.getenv("DATABASE_PATH", "data/backend.sqlite3"))
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return cls(
            database_path=path,
            cors_origins=tuple(
                origin.strip()
                for origin in os.getenv(
                    "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
                ).split(",")
                if origin.strip()
            ),
            ai_provider=os.getenv("AI_PROVIDER", "mock").strip().lower(),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "").strip(),
            openai_base_url=os.getenv(
                "OPENAI_BASE_URL", "https://api.openai.com/v1"
            ).rstrip("/"),
            ai_timeout_seconds=float(os.getenv("AI_TIMEOUT_SECONDS", "30")),
        )
