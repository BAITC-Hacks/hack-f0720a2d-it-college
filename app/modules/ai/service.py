"""Выбор OpenAI или явно обозначенной заглушки с общим валидированным контрактом."""

from pydantic import ValidationError

from app.config import get_settings
from app.modules.ai import provider
from app.modules.ai.errors import AIServiceError
from app.modules.ai.prompts import ANALYZE_PROMPT, BUILD_PROMPT, QUESTION_TEMPLATES
from app.modules.ai.schemas import (
    AnalyzeDraftInput,
    AnalyzeDraftOutput,
    AnalysisResult,
    BuildCardInput,
    CARD_FIELDS,
    CardFields,
    OpenAICardFields,
    Question,
)


def get_status() -> dict:
    """Конфигурация провайдера без сетевого запроса и без раскрытия секрета."""
    settings = get_settings()
    has_key = bool(settings.openai_api_key and settings.openai_api_key.get_secret_value())
    selected = "openai" if settings.ai_provider == "openai" or (settings.ai_provider == "auto" and has_key) else "stub"
    return {"provider": selected, "configured": selected == "openai" and has_key,
            "model": settings.openai_model if selected == "openai" else None}


def analyze_draft(raw_text: str, known_fields: dict | None = None) -> dict:
    try:
        payload = AnalyzeDraftInput(raw_text=raw_text, known_fields=known_fields or {})
    except ValidationError:
        raise AIServiceError(422, "Проверьте описание задачи и известные поля карточки.") from None
    selected = get_status()["provider"]
    if selected == "openai":
        result = provider.request_json(
            get_settings(), instructions=ANALYZE_PROMPT, payload=payload.model_dump(),
            response_model=AnalysisResult, schema_name="task_analysis",
        )
        # Явно введённое поле не объявляем отсутствующим даже при ошибке модели.
        result.missing_fields = [field for field in result.missing_fields if not payload.known_fields.get(field)]
    else:
        missing = [field for field in CARD_FIELDS if field != "context" and not payload.known_fields.get(field)]
        question_fields = list(missing)
        for field in CARD_FIELDS:
            if len(question_fields) >= 3:
                break
            if field not in question_fields:
                question_fields.append(field)
        result = AnalysisResult(missing_fields=missing, questions=[
            Question(field=field, text=QUESTION_TEMPLATES[field]) for field in question_fields
        ])
    return AnalyzeDraftOutput(**result.model_dump(), provider=selected).model_dump()


def build_card(raw_text: str, answers: dict[str, str]) -> dict:
    """Модель структурирует описание; явные ответы остаются источником истины."""
    try:
        payload = BuildCardInput(raw_text=raw_text, answers=answers)
    except ValidationError:
        raise AIServiceError(422, "Проверьте описание и ответы: используйте известные поля карточки и допустимую длину текста.") from None
    if get_status()["provider"] == "openai":
        result = provider.request_json(
            get_settings(), instructions=BUILD_PROMPT, payload=payload.model_dump(),
            response_model=OpenAICardFields, schema_name="task_card",
        )
        values = result.model_dump()
        # Сохранение явных ответов не зависит от того, перефразировала ли их модель.
        values.update({field: value for field, value in payload.answers.items() if value})
    else:
        values = {field: payload.answers.get(field) or None for field in CARD_FIELDS}
    if not values["context"]:
        values["context"] = payload.raw_text.strip()
    return CardFields.model_validate(values).model_dump()
