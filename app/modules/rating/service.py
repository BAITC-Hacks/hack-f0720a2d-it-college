"""Чистая функция расчёта рейтинга полноты карточки без БД и AI."""

from __future__ import annotations

from typing import Any

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


def _value(task: Any, field: str) -> str:
    value = task.get(field) if isinstance(task, dict) else getattr(task, field, None)
    return str(value or "").strip()


def _points(value: str, maximum: int) -> tuple[float, str]:
    if not value:
        return 0.0, "empty"
    if len(value) < MIN_FULL_LENGTH:
        return maximum / 2, "short"
    return float(maximum), "complete"


def calculate(task: Any) -> dict:
    """Возвращает сериализуемый рейтинг для объекта или словаря карточки."""

    score = 0.0
    breakdown: dict[str, BreakdownItem] = {}
    missing: list[str] = []

    for field, maximum in FIELD_WEIGHTS.items():
        earned, state = _points(_value(task, field), maximum)
        score += earned
        breakdown[field] = BreakdownItem(earned=earned, maximum=maximum, state=state)
        if state != "complete":
            gain = maximum - earned
            gain_text = str(int(gain)) if gain.is_integer() else str(gain)
            missing.append(f"{FIELD_HINTS[field]} — +{gain_text} баллов")

    level, label = next((code, name) for threshold, code, name in LEVEL_THRESHOLDS if score >= threshold)
    result = RatingResult(
        score=score,
        level=level,
        level_label=label,
        breakdown=breakdown,
        missing=missing,
    )
    return result.model_dump()
