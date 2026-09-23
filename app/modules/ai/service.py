<<<<<<< HEAD
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
=======
"""Публичный AI-сервис: настройки, обнаружение моделей и проверенные сведения."""

import hashlib
import json
import re
from dataclasses import replace

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modules.ai import provider
from app.modules.ai.models import AIAnalysis, AIConnection
from app.modules.ai.prompts import ANALYZE_PROMPT, BUILD_PROMPT, SYSTEM_PROMPT, FIELD_LABELS
from app.modules.ai.schemas import (
    AnalyzeDraftInput, AnalyzeDraftOutput, AnalysisExtraction, BuildCardInput,
    CardExtraction, CardFields, ConnectionInput, ConnectionRead, ModelsRead,
)


def default_connection() -> provider.Connection:
    settings = get_settings()
    try:
        config = ConnectionInput(base_url=settings.ai_base_url, model=settings.ai_model,
                                 response_format=settings.ai_response_format)
    except ValidationError as exc:
        raise HTTPException(503, "Проверьте AI_BASE_URL и AI_RESPONSE_FORMAT в настройках сервера.") from exc
    return provider.Connection(config.base_url, config.model, settings.ai_api_key,
                               config.response_format, settings.ai_timeout, settings.ai_max_tokens)


def get_connection(db: Session, user_id: int) -> provider.Connection:
    connection = default_connection()
    stored = db.get(AIConnection, user_id)
    if stored:
        return replace(connection, base_url=stored.base_url, model=stored.model,
                       api_key=stored.api_key, response_format=stored.response_format)
    return connection


def _public(connection: provider.Connection) -> ConnectionRead:
    return ConnectionRead(base_url=connection.base_url, model=connection.model,
                          has_api_key=bool(connection.api_key), response_format=connection.response_format)


def read_settings(db: Session, user_id: int) -> ConnectionRead:
    return _public(get_connection(db, user_id))


def _configured(db: Session, user_id: int, payload: ConnectionInput) -> provider.Connection:
    current = get_connection(db, user_id)
    # При смене адреса старый ключ не отправляется другому серверу.
    key = current.api_key if current.base_url == payload.base_url else ""
    if payload.clear_api_key:
        key = ""
    if payload.api_key is not None and payload.api_key.get_secret_value().strip():
        key = payload.api_key.get_secret_value().strip()
    return replace(current, base_url=payload.base_url, model=payload.model, api_key=key,
                   response_format=payload.response_format)


def save_settings(db: Session, user_id: int, payload: ConnectionInput) -> ConnectionRead:
    connection = _configured(db, user_id, payload)
    row = db.get(AIConnection, user_id) or AIConnection(user_id=user_id)
    for name in ("base_url", "model", "api_key", "response_format"):
        setattr(row, name, getattr(connection, name))
    db.add(row)
    db.commit()
    return _public(connection)


def available_models(db: Session, user_id: int, payload: ConnectionInput | None = None) -> ModelsRead:
    connection = _configured(db, user_id, payload) if payload else get_connection(db, user_id)
    models = provider.list_models(connection)
    selected = connection.model if any(m.id == connection.model for m in models) else None
    if not connection.model:
        selected = next((m.id for m in models if m.chat_candidate), None)
    return ModelsRead(models=models, selected_model=selected)


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _grounded_card(extraction: CardExtraction, raw_text: str, known: dict, answers: dict) -> CardFields:
    fragments = {_normalize(raw_text)}
    labels = {label for names in FIELD_LABELS.values() for label in names}
    for line in raw_text.splitlines():
        fragments.add(_normalize(line))
        label, separator, value = line.partition(":")
        if separator and label.strip().casefold() in labels:
            line = value.strip()
            fragments.add(_normalize(line))
        fragments.update(_normalize(part) for part in re.split(r"(?<=[.!?])\s+", line) if part.strip())
    fields = {}
    for name, quotes in extraction.model_dump().items():
        manual = answers.get(name) or known.get(name)
        if manual:
            fields[name] = manual
            continue
        other_answers = {_normalize(value) for key, value in answers.items() if key != name and value}
        grounded = []
        for quote in quotes:
            quote = _normalize(quote)
            if quote in other_answers:
                raise provider.InvalidAIResponse("Ответ пользователя перенесён в другое поле")
            if quote not in fragments:
                # Небольшие модели выделяют словосочетания вопреки инструкции.
                # Восстанавливаем целое предложение из источника, вместе с
                # отрицаниями и условиями; неоднозначный источник отклоняем.
                matches = [part for part in fragments if quote in part]
                minimal = [part for part in matches if not any(other != part and other in part for other in matches)]
                if len(minimal) != 1 or minimal[0] in other_answers:
                    raise provider.InvalidAIResponse("Не найден однозначный целый фрагмент источника")
                quote = minimal[0]
            grounded.append(quote)
        fields[name] = "\n".join(dict.fromkeys(grounded)) or None
    # Ручные значения имеют приоритет перед извлечением модели.
    fields.update({key: value for key, value in known.items() if value})
    fields.update({key: value for key, value in answers.items() if value})
    return CardFields.model_validate(fields)


def analyze_draft(raw_text: str, *, known_fields: dict | None = None,
                  connection: provider.Connection | None = None) -> dict:
    raw_text = AnalyzeDraftInput(raw_text=raw_text).raw_text
    known = CardFields.model_validate(known_fields or {}).model_dump(exclude_none=True)

    def validate(result: AnalysisExtraction) -> dict:
        card = _grounded_card(result.card, raw_text, known, {})
        return AnalyzeDraftOutput(missing_fields=list(dict.fromkeys(result.missing_fields)),
                                  questions=result.questions, detected_fields=card).model_dump()

    return provider.generate(connection or default_connection(), SYSTEM_PROMPT, ANALYZE_PROMPT,
                             {"raw_text": raw_text, "known_fields": known}, AnalysisExtraction, validate)


def build_card(raw_text: str, answers: dict[str, str], *, known_fields: dict | None = None,
               connection: provider.Connection | None = None) -> dict:
    payload = BuildCardInput(raw_text=raw_text, answers=answers)
    known = CardFields.model_validate(known_fields or {}).model_dump(exclude_none=True)

    def validate(result: CardExtraction) -> dict:
        return _grounded_card(result, payload.raw_text, known, payload.answers).model_dump()

    return provider.generate(connection or default_connection(), SYSTEM_PROMPT, BUILD_PROMPT,
                             {**payload.model_dump(), "known_fields": known}, CardExtraction, validate)


def _fingerprint(raw_text: str, known_fields: dict, connection: provider.Connection) -> str:
    # Ключ не хранится в кэше и не попадает в API; его изменение инвалидирует результат.
    return hashlib.sha256(json.dumps(
        ["whole-source-v2", raw_text, known_fields, connection.base_url, connection.model, connection.response_format,
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
    except IntegrityError as exc:
        db.rollback()
        cached = db.get(AIAnalysis, task_id)
        if cached and cached.fingerprint == fingerprint:
            return cached.payload
        raise HTTPException(409, "Задача изменилась во время анализа. Обновите страницу.") from exc
    return result


def build_card_for_task(db: Session, task_id: int, user_id: int, raw_text: str, answers: dict, known_fields: dict) -> dict:
    connection = get_connection(db, user_id)
    cached = db.get(AIAnalysis, task_id)
    known = known_fields
    if cached and cached.fingerprint == _fingerprint(raw_text, known_fields, connection):
        # Сборка не должна потерять факты, которые уже были извлечены и проверены на предыдущем шаге.
        detected = {key: value for key, value in cached.payload["detected_fields"].items() if value}
        known = {**detected, **known_fields}
    return build_card(raw_text, answers, known_fields=known, connection=connection)


def delete_for_task(db: Session, task_id: int) -> None:
    db.execute(delete(AIAnalysis).where(AIAnalysis.task_id == task_id))
>>>>>>> ab5a473797132f7124443376acd5c95546baa5a2
