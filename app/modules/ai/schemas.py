"""Контракт входа и выхода заменяемой AI-реализации."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
