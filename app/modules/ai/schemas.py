"""Контракт входа и выхода заменяемой AI-реализации."""

from typing import Annotated, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

OPENAI_BASE_URL = "https://api.openai.com/v1"
INHERIT_SERVER_KEY = "__AI_SANA_INHERIT_SERVER_KEY__"
ResponseFormat = Literal["auto", "json_schema", "json_object", "text"]
AIProvider = Literal["openai", "compatible", "stub"]


CARD_FIELDS = (
    "title",
    "industry",
    "context",
    "need",
    "users",
    "data",
    "constraints",
    "expected_result",
    "success_criteria",
    "contact",
)

CardField = Literal[
    "title", "industry", "context", "need", "users", "data", "constraints",
    "expected_result", "success_criteria", "contact",
]


def _clean_mapping(values: dict) -> dict:
    result = {key: value.strip() if isinstance(value, str) else value for key, value in values.items()}
    CardFields.model_validate(result)
    return result


class AnalyzeDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str = Field(min_length=1, max_length=10_000)
    known_fields: dict[CardField, str | None] = Field(default_factory=dict)

    @field_validator("known_fields")
    @classmethod
    def clean_known_fields(cls, value: dict) -> dict:
        return _clean_mapping(value)

    @field_validator("raw_text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Описание задачи не может быть пустым")
        return value


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    field: CardField
    text: str = Field(min_length=1, max_length=1_000)


class AnalysisResult(BaseModel):
    """Только результат модели, без вычисляемых сервером метаданных провайдера."""

    model_config = ConfigDict(extra="forbid", strict=True)

    missing_fields: list[CardField] = Field(max_length=10)
    questions: list[Question] = Field(min_length=3, max_length=10)

    @model_validator(mode="after")
    def unique_fields_and_questions(self) -> "AnalysisResult":
        if len(set(self.missing_fields)) != len(self.missing_fields):
            raise ValueError("Список недостающих полей не должен содержать повторы")
        fields = [question.field for question in self.questions]
        texts = [question.text.casefold() for question in self.questions]
        if len(set(fields)) != len(fields) or len(set(texts)) != len(texts):
            raise ValueError("Уточняющие вопросы должны быть уникальны")
        return self


class AnalyzeDraftOutput(AnalysisResult):
    provider: AIProvider = "stub"
    detected_fields: "CardFields" = Field(default_factory=lambda: CardFields())


class AIStatus(BaseModel):
    provider: AIProvider
    configured: bool
    model: str | None
    base_url: str | None = None


class BuildCardInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str = Field(min_length=1, max_length=10_000)
    answers: dict[CardField, str]

    @field_validator("raw_text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Описание задачи не может быть пустым")
        return value

    @field_validator("answers")
    @classmethod
    def known_answer_fields(cls, answers: dict[str, str]) -> dict[str, str]:
        return _clean_mapping(answers)


class CardFields(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    title: str | None = Field(default=None, max_length=240)
    industry: str | None = Field(default=None, max_length=120)
    context: str | None = Field(default=None, max_length=10_000)
    need: str | None = Field(default=None, max_length=10_000)
    users: str | None = Field(default=None, max_length=10_000)
    data: str | None = Field(default=None, max_length=10_000)
    constraints: str | None = Field(default=None, max_length=10_000)
    expected_result: str | None = Field(default=None, max_length=10_000)
    success_criteria: str | None = Field(default=None, max_length=10_000)
    contact: str | None = Field(default=None, max_length=10_000)


class OpenAICardFields(CardFields):
    """Structured Outputs требует все ключи, а отсутствующие сведения — null."""

    title: str | None = Field(max_length=240)
    industry: str | None = Field(max_length=120)
    context: str | None = Field(max_length=10_000)
    need: str | None = Field(max_length=10_000)
    users: str | None = Field(max_length=10_000)
    data: str | None = Field(max_length=10_000)
    constraints: str | None = Field(max_length=10_000)
    expected_result: str | None = Field(max_length=10_000)
    success_criteria: str | None = Field(max_length=10_000)
    contact: str | None = Field(max_length=10_000)


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: Literal["auto", "openai", "compatible", "stub"] = "compatible"
    base_url: str = Field(default="http://127.0.0.1:1234/v1", max_length=2000)
    model: str = Field(default="", max_length=240)
    api_key: SecretStr | None = Field(default=None, max_length=4000)
    clear_api_key: bool = False
    response_format: ResponseFormat = "auto"

    @field_validator("api_key")
    @classmethod
    def valid_api_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            key = value.get_secret_value()
            if (not key.isascii() or any(ord(char) < 32 or ord(char) == 127 for char in key)
                    or key.strip() == INHERIT_SERVER_KEY):
                raise ValueError("API-ключ должен содержать только печатные ASCII-символы одной строки")
        return value

    @model_validator(mode="after")
    def validate_connection(self) -> "ConnectionInput":
        if self.provider in {"auto", "stub"}:
            self.base_url = ""
            return self
        if self.provider == "openai":
            if "base_url" in self.model_fields_set and self.base_url.rstrip("/") != OPENAI_BASE_URL:
                raise ValueError("OpenAI использует только https://api.openai.com/v1")
            if len(self.model) > 120:
                raise ValueError("Название модели OpenAI должно содержать не более 120 символов")
            self.base_url = OPENAI_BASE_URL
            self.response_format = "json_schema"
            return self
        try:
            parts = urlsplit(self.base_url)
            port = parts.port
        except ValueError:
            raise ValueError("Некорректный адрес AI-сервера") from None
        if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username is not None
                or parts.password is not None or parts.query or parts.fragment or (port is not None and port < 1)):
            raise ValueError("Укажите HTTP(S) адрес API без ключа, параметров и логина в URL")
        path = parts.path.rstrip("/") or "/v1"
        if path.endswith(("/chat/completions", "/models", "/responses")):
            raise ValueError("Укажите базовый адрес API, например http://127.0.0.1:1234/v1")
        self.base_url = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))
        return self


class ConnectionRead(BaseModel):
    provider: Literal["auto", "openai", "compatible", "stub"]
    effective_provider: AIProvider
    base_url: str
    model: str
    has_api_key: bool
    response_format: ResponseFormat


class ModelInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    chat_candidate: bool = True


class ModelsRead(BaseModel):
    models: list[ModelInfo]
    selected_model: str | None


Quotes = Annotated[list[Annotated[str, Field(min_length=1, max_length=10_000)]], Field(max_length=6)]


class CardExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    title: Quotes
    industry: Quotes
    context: Quotes
    need: Quotes
    users: Quotes
    data: Quotes
    constraints: Quotes
    expected_result: Quotes
    success_criteria: Quotes
    contact: Quotes


class AnalysisExtraction(AnalysisResult):
    card: CardExtraction


AnalyzeDraftOutput.model_rebuild()
