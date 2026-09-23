"""Чистая функция расчёта рейтинга полноты карточки без БД и AI."""

from __future__ import annotations

from typing import Any
import re

from app.modules.rating.schemas import BreakdownItem, RatingResult

FIELD_WEIGHTS: dict[str, int] = {
    "context": 10,
    "need": 10,
    "data": 20,
    "expected_result": 15,
    "success_criteria": 15,
    "constraints": 10,
    "users": 10,
    "contact": 10,
}

LEVEL_THRESHOLDS: tuple[tuple[int, str, str], ...] = (
    (90, "priority", "Приоритетная"),
    (70, "ready", "Готовая"),
    (40, "working", "Рабочая"),
    (0, "draft", "Черновик"),
)

MIN_FULL_LENGTH = 30
PLACEHOLDERS = {"не знаю", "не указано", "неизвестно", "уточняется", "пока нет", "нет данных", "tbd", "n/a"}

# Семь показателей кейса. В первом два независимых подполя по 10 баллов.
INDICATORS = {
    "context_need": ("context", "need"),
    "data": ("data",),
    "expected_result": ("expected_result",),
    "success_criteria": ("success_criteria",),
    "constraints": ("constraints",),
    "users": ("users",),
    "contact": ("contact",),
}

FIELD_HINTS: dict[str, str] = {
    "context": "Добавьте контекст задачи",
    "need": "Опишите потребность бизнеса",
    "data": "Добавьте данные и материалы",
    "expected_result": "Опишите ожидаемый результат",
    "success_criteria": "Добавьте критерии успеха",
    "constraints": "Укажите ограничения",
    "users": "Опишите пользователей решения",
    "contact": "Добавьте контакт и формат связи",
}

FIELD_LABELS = {"context": "Контекст", "need": "Потребность", "data": "Данные и материалы",
                "expected_result": "Ожидаемый результат", "success_criteria": "Критерии успеха",
                "constraints": "Ограничения", "users": "Пользователи", "contact": "Связь с бизнесом"}


def _value(task: Any, field: str) -> str:
    value = task.get(field) if isinstance(task, dict) else getattr(task, field, None)
    return str(value or "").strip()


def _points(value: str, maximum: int) -> tuple[float, str]:
    normalized = value.casefold().strip(" .!?-_")
    words = re.findall(r"\w+", normalized)
    if (not words or normalized in PLACEHOLDERS
            or len(set("".join(words))) < 2
            or (len(words) > 2 and len(set(words)) == 1)):
        return 0.0, "empty"
    if len(value) < MIN_FULL_LENGTH:
        return maximum / 2, "short"
    return float(maximum), "complete"


def level_for_score(score: float) -> tuple[str, str]:
    """Пороги выделены отдельно, включая точные границы 39/40, 69/70, 89/90."""
    if not 0 <= score <= 100:
        raise ValueError("Рейтинг должен быть от 0 до 100")
    return next((code, name) for threshold, code, name in LEVEL_THRESHOLDS if score >= threshold)


def calculate(task: Any) -> dict:
    """Чистый расчёт: confirmed_fields явно перечисляет подтверждённые поля.

    Отсутствие подтверждения не даёт баллов. potential_score — только прогноз,
    не рейтинг и не основание позиции в каталоге. Снимки проверяет tasks.service.
    """

    score = 0.0
    breakdown: dict[str, BreakdownItem] = {}
    missing: list[str] = []
    potential_score = 0.0
    confirmed = set(task.get("confirmed_fields", []) if isinstance(task, dict)
                    else getattr(task, "confirmed_fields", []))
    confirmed_fields: list[str] = []
    unconfirmed_fields: list[str] = []

    for field, maximum in FIELD_WEIGHTS.items():
        value = _value(task, field)
        potential, state = _points(value, maximum)
        potential_score += potential
        earned = potential
        if value and field not in confirmed:
            earned, state = 0.0, "unconfirmed"
            unconfirmed_fields.append(field)
        elif value:
            confirmed_fields.append(field)
        score += earned
        breakdown[field] = BreakdownItem(earned=earned, maximum=maximum, state=state)
        if state != "complete":
            gain = maximum - earned
            gain_text = str(int(gain)) if gain.is_integer() else str(gain)
            if state == "unconfirmed":
                missing.append(f"Подтвердите поле «{FIELD_LABELS[field]}» — +{potential:g} баллов")
                if potential < maximum:
                    missing.append(f"{FIELD_HINTS[field]} и подтвердите — +{maximum - potential:g} баллов")
            else:
                missing.append(f"{FIELD_HINTS[field]} — +{gain_text} баллов после подтверждения")

    indicators = {}
    for name, fields in INDICATORS.items():
        items = [breakdown[field] for field in fields]
        earned = sum(item.earned for item in items)
        maximum = sum(item.maximum for item in items)
        state = ("unconfirmed" if any(item.state == "unconfirmed" for item in items)
                 else "complete" if earned == maximum else "empty" if earned == 0 else "short")
        indicators[name] = BreakdownItem(earned=earned, maximum=maximum, state=state)
    level, label = level_for_score(score)
    result = RatingResult(
        score=score,
        level=level,
        level_label=label,
        breakdown=breakdown,
        indicators=indicators,
        potential_score=potential_score,
        confirmed_fields=confirmed_fields,
        unconfirmed_fields=unconfirmed_fields,
        missing=missing,
    )
    return result.model_dump()
