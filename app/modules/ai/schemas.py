"""Контракты OpenAI-compatible подключения, анализа и извлечения фактов."""

<<<<<<< HEAD
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
=======
from typing import Annotated, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

CardField = Literal["title", "industry", "context", "need", "users", "data", "constraints",
                    "expected_result", "success_criteria", "contact"]
CARD_FIELDS = tuple(CardField.__args__)
AnswerText = Annotated[str, Field(max_length=10_000)]
ResponseFormat = Literal["auto", "json_schema", "json_object", "text"]
>>>>>>> ab5a473797132f7124443376acd5c95546baa5a2


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

CardField = Literal[
    "title", "industry", "context", "need", "users", "data", "constraints",
    "expected_result", "success_criteria", "contact",
]


def _clean_mapping(values: dict) -> dict:
    result = {key: value.strip() if isinstance(value, str) else value for key, value in values.items()}
    CardFields.model_validate(result)
    return result


<<<<<<< HEAD
class AnalyzeDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str = Field(min_length=1, max_length=10_000)
    known_fields: dict[CardField, str | None] = Field(default_factory=dict)

    @field_validator("known_fields")
    @classmethod
    def clean_known_fields(cls, value: dict) -> dict:
        return _clean_mapping(value)
=======
class ConnectionInput(StrictModel):
    base_url: str = Field(default="http://127.0.0.1:1234/v1", min_length=1, max_length=2000)
    model: str = Field(default="", max_length=240)
    api_key: SecretStr | None = Field(default=None, max_length=4000)
    clear_api_key: bool = False
    response_format: ResponseFormat = "auto"
>>>>>>> ab5a473797132f7124443376acd5c95546baa5a2

    @field_validator("api_key")
    @classmethod
    def valid_api_key(cls, value):
        if value is not None and any(char in value.get_secret_value() for char in ("\n", "\r")):
            raise ValueError("API-ключ должен занимать одну строку")
        return value

<<<<<<< HEAD

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
    provider: Literal["stub", "openai"] = "stub"


class AIStatus(BaseModel):
    provider: Literal["stub", "openai"]
    configured: bool
    model: str | None


class BuildCardInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str = Field(min_length=1, max_length=10_000)
    answers: dict[CardField, str]

    @field_validator("raw_text")
=======
    @field_validator("base_url")
>>>>>>> ab5a473797132f7124443376acd5c95546baa5a2
    @classmethod
    def normalize_url(cls, value: str) -> str:
        try:
            parts = urlsplit(value.strip())
            port = parts.port
        except ValueError as exc:
            raise ValueError("Некорректный адрес AI-сервера") from exc
        if (parts.scheme not in ("http", "https") or not parts.hostname or parts.username
                or parts.password or parts.query or parts.fragment or (port is not None and port < 1)):
            raise ValueError("Укажите HTTP(S) адрес API без ключа, параметров и логина в URL")
        path = parts.path.rstrip("/") or "/v1"
        if path.endswith(("/chat/completions", "/models")):
            raise ValueError("Нужен базовый адрес API, например http://127.0.0.1:1234/v1")
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


class ConnectionRead(StrictModel):
    base_url: str
    model: str
    has_api_key: bool
    response_format: ResponseFormat


class ModelInfo(StrictModel):
    id: str
    chat_candidate: bool = True


class ModelsRead(StrictModel):
    models: list[ModelInfo]
    selected_model: str | None


class AnalyzeDraftInput(StrictModel):
    raw_text: str = Field(min_length=1, max_length=10_000)


class Question(StrictModel):
    field: CardField
    text: str = Field(min_length=8, max_length=600)


class CardFields(StrictModel):
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


class AnalyzeDraftOutput(StrictModel):
    missing_fields: list[CardField]
    questions: list[Question] = Field(min_length=3, max_length=10)
    detected_fields: CardFields = Field(default_factory=CardFields)

    @model_validator(mode="after")
    def unique_questions(self):
        if len({q.field for q in self.questions}) != len(self.questions):
            raise ValueError("Каждый вопрос должен относиться к отдельному полю")
        return self


class BuildCardInput(AnalyzeDraftInput):
    answers: dict[CardField, AnswerText]

    @field_validator("answers")
    @classmethod
<<<<<<< HEAD
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
=======
    def strip_answers(cls, answers):
        cleaned = {key: value.strip() for key, value in answers.items()}
        CardFields.model_validate(cleaned)
        return cleaned


# Все значения — дословные фрагменты источников, проверяемые после генерации.
Quotes = Annotated[list[Annotated[str, Field(min_length=1, max_length=10_000)]], Field(max_length=6)]


class CardExtraction(StrictModel):
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


class AnalysisExtraction(StrictModel):
    card: CardExtraction
    missing_fields: list[CardField]
    questions: list[Question] = Field(min_length=3, max_length=10)
>>>>>>> ab5a473797132f7124443376acd5c95546baa5a2
