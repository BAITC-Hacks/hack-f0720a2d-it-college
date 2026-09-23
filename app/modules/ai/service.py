"""Публичный AI-сервис: OpenAI Responses, совместимые серверы и явная заглушка."""

import hashlib
import json

from fastapi import HTTPException
from pydantic import SecretStr, ValidationError
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modules.ai import compatible_prompts, compatible_provider, provider
from app.modules.ai.compatible_provider import Connection
from app.modules.ai.connections import (
    available_models, default_connection, get_connection, read_settings, save_settings,
)
from app.modules.ai.errors import AIServiceError
from app.modules.ai.grounding import _grounded_card
from app.modules.ai.models import AIAnalysis
from app.modules.ai.prompts import ANALYZE_PROMPT, BUILD_PROMPT, QUESTION_TEMPLATES
from app.modules.ai.schemas import (
    AnalyzeDraftInput, AnalyzeDraftOutput, AnalysisExtraction, AnalysisResult,
    BuildCardInput, CARD_FIELDS, CardExtraction, CardFields, OpenAICardFields, Question,
)


def get_status(db: Session | None = None, user_id: int | None = None) -> dict:
    """Настройки активного пользователя без сети и без раскрытия ключей."""
    connection = get_connection(db, user_id) if db is not None and user_id is not None else default_connection()
    return {
        "provider": connection.provider,
        "configured": connection.provider == "compatible" or (connection.provider == "openai" and bool(connection.api_key)),
        "model": connection.model or None,
        "base_url": connection.base_url or None,
    }


def _openai_settings(connection: Connection):
    return get_settings().model_copy(update={
        "openai_api_key": SecretStr(connection.api_key), "openai_model": connection.model,
        "ai_timeout_seconds": connection.timeout, "openai_max_output_tokens": connection.max_tokens,
    })


def analyze_draft(raw_text: str, known_fields: dict | None = None, *, connection: Connection | None = None) -> dict:
    try:
        payload = AnalyzeDraftInput(raw_text=raw_text, known_fields=known_fields or {})
    except ValidationError:
        raise AIServiceError(422, "Проверьте описание задачи и известные поля карточки.") from None
    connection = connection or default_connection()
    known = {key: value for key, value in payload.known_fields.items() if value}
    if connection.provider == "compatible":
        def validate(result: AnalysisExtraction) -> dict:
            card = _grounded_card(result.card, payload.raw_text, known, {})
            missing = [name for name in result.missing_fields if not known.get(name)]
            return AnalyzeDraftOutput(missing_fields=missing, questions=result.questions,
                                      detected_fields=card, provider="compatible").model_dump()
        return compatible_provider.generate(
            connection, compatible_prompts.SYSTEM_PROMPT, compatible_prompts.ANALYZE_PROMPT,
            payload.model_dump(), AnalysisExtraction, validate,
        )
    if connection.provider == "openai":
        result = provider.request_json(
            _openai_settings(connection), instructions=ANALYZE_PROMPT, payload=payload.model_dump(),
            response_model=AnalysisResult, schema_name="task_analysis",
        )
        result.missing_fields = [name for name in result.missing_fields if not known.get(name)]
    else:
        missing = [field for field in CARD_FIELDS if field != "context" and not known.get(field)]
        question_fields = list(missing)
        for field in CARD_FIELDS:
            if len(question_fields) >= 3:
                break
            if field not in question_fields:
                question_fields.append(field)
        result = AnalysisResult(missing_fields=missing, questions=[
            Question(field=field, text=QUESTION_TEMPLATES[field]) for field in question_fields
        ])
    # Responses сохраняет прежний строгий контракт вопросов; сервер не приписывает
    # модели извлечение полей, которых не было в её ответе.
    detected = CardFields.model_validate(known)
    return AnalyzeDraftOutput(**result.model_dump(), provider=connection.provider, detected_fields=detected).model_dump()


def build_card(raw_text: str, answers: dict[str, str], *, known_fields: dict | None = None,
               connection: Connection | None = None) -> dict:
    """Непустые ручные ответы важнее известных полей и извлечения модели."""
    try:
        payload = BuildCardInput(raw_text=raw_text, answers=answers)
        known = CardFields.model_validate(known_fields or {}).model_dump(exclude_none=True)
    except ValidationError:
        raise AIServiceError(422, "Проверьте описание и ответы: используйте известные поля карточки и допустимую длину текста.") from None
    connection = connection or default_connection()
    supplied = {key: value for key, value in payload.answers.items() if value}
    if connection.provider == "compatible":
        def validate(result: CardExtraction) -> dict:
            return _grounded_card(result, payload.raw_text, known, supplied).model_dump()
        return compatible_provider.generate(
            connection, compatible_prompts.SYSTEM_PROMPT, compatible_prompts.BUILD_PROMPT,
            {"raw_text": payload.raw_text, "known_fields": known, "answers": supplied}, CardExtraction, validate,
        )
    if connection.provider == "openai":
        result = provider.request_json(
            _openai_settings(connection), instructions=BUILD_PROMPT,
            payload={"raw_text": payload.raw_text, "answers": {**known, **supplied}},
            response_model=OpenAICardFields, schema_name="task_card",
        )
        values = result.model_dump()
    else:
        values = {field: None for field in CARD_FIELDS}
    values.update({key: value for key, value in known.items() if value})
    values.update(supplied)
    if not values["context"]:
        values["context"] = payload.raw_text.strip()
    return CardFields.model_validate(values).model_dump()


def _fingerprint(raw_text: str, known_fields: dict, connection: Connection) -> str:
    return hashlib.sha256(json.dumps(
        ["multi-provider-whole-source-v3", raw_text, known_fields, connection.provider,
         connection.base_url, connection.model, connection.response_format,
         hashlib.sha256(connection.api_key.encode()).hexdigest()], sort_keys=True, ensure_ascii=False,
    ).encode()).hexdigest()


def questions_for_task(db: Session, task_id: int, user_id: int, raw_text: str, known_fields: dict) -> dict:
    connection = get_connection(db, user_id)
    fingerprint = _fingerprint(raw_text, known_fields, connection)
    cached = db.get(AIAnalysis, task_id)
    if cached and cached.fingerprint == fingerprint:
        return cached.payload
    result = analyze_draft(raw_text, known_fields=known_fields, connection=connection)
    row = db.get(AIAnalysis, task_id) or AIAnalysis(task_id=task_id)
    row.fingerprint, row.payload = fingerprint, result
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        cached = db.get(AIAnalysis, task_id)
        if cached and cached.fingerprint == fingerprint:
            return cached.payload
        raise HTTPException(409, "Задача изменилась во время анализа. Обновите страницу.") from None
    return result


def build_card_for_task(db: Session, task_id: int, user_id: int, raw_text: str, answers: dict, known_fields: dict) -> dict:
    connection = get_connection(db, user_id)
    cached = db.get(AIAnalysis, task_id)
    known = known_fields
    if cached and cached.fingerprint == _fingerprint(raw_text, known_fields, connection):
        detected = {key: value for key, value in cached.payload.get("detected_fields", {}).items() if value}
        known = {**detected, **known_fields}
    return build_card(raw_text, answers, known_fields=known, connection=connection)


def delete_for_task(db: Session, task_id: int) -> None:
    """Очистка кэша в транзакции владельца задачи; commit остаётся вызывающему сервису."""
    db.execute(delete(AIAnalysis).where(AIAnalysis.task_id == task_id))
