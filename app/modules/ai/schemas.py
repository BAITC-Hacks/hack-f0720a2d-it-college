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
FIELD_LIMITS = {field: 10_000 for field in CARD_FIELDS} | {"title": 240, "industry": 120}


class AnalyzeDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    raw_text: str = Field(min_length=1, max_length=10_000)

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


class AnalyzeDraftOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    missing_fields: list[CardField] = Field(max_length=len(CARD_FIELDS))
    questions: list[Question] = Field(min_length=3, max_length=len(CARD_FIELDS))

    @model_validator(mode="after")
    def unique_fields(self):
        question_fields = [question.field for question in self.questions]
        if len(set(self.missing_fields)) != len(self.missing_fields):
            raise ValueError("Список недостающих полей не должен содержать повторов")
        if len(set(question_fields)) != len(question_fields):
            raise ValueError("Уточняющие вопросы не должны повторяться")
        if not set(self.missing_fields).issubset(question_fields):
            raise ValueError("Для каждого недостающего поля нужен уточняющий вопрос")
        return self


class BuildCardInput(AnalyzeDraftInput):
    answers: dict[str, str]

    @field_validator("answers")
    @classmethod
    def known_answer_fields(cls, answers: dict[str, str]) -> dict[str, str]:
        unknown = sorted(set(answers) - set(CARD_FIELDS))
        if unknown:
            raise ValueError(f"Неизвестные поля карточки: {', '.join(unknown)}")
        cleaned = {key: value.strip() for key, value in answers.items()}
        for key, value in cleaned.items():
            if len(value) > FIELD_LIMITS[key]:
                raise ValueError(f"Поле {key}: не более {FIELD_LIMITS[key]} символов")
        return cleaned


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

    @field_validator("*")
    @classmethod
    def empty_to_none(cls, value: str | None) -> str | None:
        return value or None
