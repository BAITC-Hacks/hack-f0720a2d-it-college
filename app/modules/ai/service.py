"""Локальная AI-заглушка с валидированным и заменяемым контрактом."""

from app.modules.ai.prompts import QUESTION_TEMPLATES
from app.modules.ai.schemas import (
    AnalyzeDraftInput,
    AnalyzeDraftOutput,
    BuildCardInput,
    CARD_FIELDS,
    CardFields,
    Question,
)


def analyze_draft(raw_text: str) -> dict:
    """Считает исходный текст контекстом и задаёт вопросы по остальным полям."""

    AnalyzeDraftInput(raw_text=raw_text)
    missing_fields = [field for field in CARD_FIELDS if field != "context"]
    questions = [Question(field=field, text=QUESTION_TEMPLATES[field]) for field in missing_fields]
    return AnalyzeDraftOutput(missing_fields=missing_fields, questions=questions).model_dump()


def build_card(raw_text: str, answers: dict[str, str]) -> dict:
    """Раскладывает пользовательский текст и ответы без добавления новых фактов."""

    payload = BuildCardInput(raw_text=raw_text, answers=answers)
    values = {field: payload.answers.get(field) or None for field in CARD_FIELDS}
    if not values["context"]:
        values["context"] = payload.raw_text.strip()
    return CardFields.model_validate(values).model_dump()
