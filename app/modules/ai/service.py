"""Экстрактивная AI-карточка: проверка, один повтор и автономная заглушка."""

from __future__ import annotations

import json
import logging
import re

import httpx

from app.config import get_settings
from app.modules.ai.client import request_card
from app.modules.ai.prompts import FIELD_LABELS, QUESTION_TEMPLATES, REVIEW_TEMPLATES
from app.modules.ai.schemas import (
    AnalyzeDraftInput,
    AnalyzeDraftOutput,
    BuildCardInput,
    CARD_FIELDS,
    FIELD_LIMITS,
    CardFields,
    Question,
)

LOGGER = logging.getLogger(__name__)
MAX_ATTEMPTS = 2  # Первый запрос и ровно один повтор, затем локальный fallback.
LABEL_TO_FIELD = {label: field for field, labels in FIELD_LABELS.items() for label in labels}


def _labeled_values(raw_text: str) -> dict[str, str | None]:
    """Переносит только текст после явных меток; неизвестные строки не интерпретирует."""
    values = {field: None for field in CARD_FIELDS}
    found_label = False
    for line in raw_text.splitlines():
        label, separator, value = line.partition(":")
        field = LABEL_TO_FIELD.get(label.strip().casefold())
        if separator and field:
            found_label = True
            value = value.strip()
            # Длинное название не обрезаем до потенциально неверного утверждения.
            if value and len(value) <= FIELD_LIMITS[field]:
                values[field] = value
    if not found_label:
        values["context"] = raw_text.strip()
    return values


def _fallback_card(payload: BuildCardInput) -> CardFields:
    values = _labeled_values(payload.raw_text)
    for field, value in payload.answers.items():
        if value:
            values[field] = value
    return CardFields.model_validate(values)


def _source_fragments(raw_text: str) -> set[str]:
    """Целые строки/предложения защищают от вырезания отрицаний внутри фразы."""
    fragments = {raw_text.strip()}
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        fragments.add(line)
        label, separator, value = line.partition(":")
        if separator and label.strip().casefold() in LABEL_TO_FIELD:
            line = value.strip()
            fragments.add(line)
        fragments.update(part.strip() for part in re.split(r"(?<=[.!?])\s+", line) if part.strip())
    return fragments


def _validated_card(text: str, payload: BuildCardInput) -> CardFields:
    data = json.loads(text)
    if not isinstance(data, dict) or set(data) != set(CARD_FIELDS):
        raise ValueError("AI должен вернуть все известные поля карточки и только их")
    card = CardFields.model_validate(data)
    fragments = _source_fragments(payload.raw_text)
    for field, value in card.model_dump().items():
        answer = payload.answers.get(field)
        if answer:
            if value != answer:
                raise ValueError("AI изменил явно заданный ответ пользователя")
        elif value is not None:
            other_answers = {text for key, text in payload.answers.items() if key != field and text}
            if value in other_answers:
                raise ValueError("AI перенёс ответ пользователя в другое поле")
            if value not in fragments:
                raise ValueError("AI добавил сведения без точного основания в исходном тексте")
    return card


def _extract_card(payload: BuildCardInput) -> CardFields:
    settings = get_settings()
    if settings.openai_api_key and settings.openai_api_key.strip():
        for attempt in range(MAX_ATTEMPTS):
            try:
                text = request_card(
                    payload,
                    api_key=settings.openai_api_key,
                    model=settings.openai_model,
                    retry=attempt > 0,
                )
                return _validated_card(text, payload)
            except (httpx.HTTPError, ValueError, TypeError):
                # Не записываем ключи, пользовательские данные или сырой ответ в лог.
                LOGGER.warning("AI-ответ не прошёл проверку, попытка %s/%s", attempt + 1, MAX_ATTEMPTS)
        LOGGER.warning("Используется локальная AI-заглушка")
    return _fallback_card(payload)


def analyze_draft(raw_text: str) -> dict:
    """Проверяет полноту и задаёт вопросы; не подтверждает и не публикует карточку."""

    validated = AnalyzeDraftInput(raw_text=raw_text)
    card = _extract_card(BuildCardInput(raw_text=validated.raw_text, answers={}))
    missing_fields = [field for field, value in card.model_dump().items() if not value]
    questions = [Question(field=field, text=QUESTION_TEMPLATES[field]) for field in missing_fields]
    # Полный черновик всё равно требует проверки. Эти вопросы не объявляются missing.
    for field, text in REVIEW_TEMPLATES.items():
        if len(questions) >= 3:
            break
        if field not in missing_fields:
            questions.append(Question(field=field, text=text))
    return AnalyzeDraftOutput(missing_fields=missing_fields, questions=questions).model_dump()


def build_card(raw_text: str, answers: dict[str, str]) -> dict:
    """Приоритет у ответов пользователя; результат всегда требует ручной проверки."""

    payload = BuildCardInput(raw_text=raw_text, answers=answers)
    return _extract_card(payload).model_dump()
