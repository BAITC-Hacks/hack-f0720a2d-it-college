"""Контракт входа и выхода заменяемой AI-реализации."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class AnalyzeDraftInput(BaseModel):
    raw_text: str = Field(min_length=1, max_length=10_000)

    @field_validator("raw_text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Описание задачи не может быть пустым")
        return value


class Question(BaseModel):
    field: str
    text: str


class AnalyzeDraftOutput(BaseModel):
    missing_fields: list[str]
    questions: list[Question] = Field(min_length=3)


class BuildCardInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str = Field(min_length=1, max_length=10_000)
    answers: dict[str, str]

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
        unknown = sorted(set(answers) - set(CARD_FIELDS))
        if unknown:
            raise ValueError(f"Неизвестные поля карточки: {', '.join(unknown)}")
        return {key: value.strip() for key, value in answers.items()}


class CardFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    industry: str | None = None
    context: str | None = None
    need: str | None = None
    users: str | None = None
    data: str | None = None
    constraints: str | None = None
    expected_result: str | None = None
    success_criteria: str | None = None
    contact: str | None = None
