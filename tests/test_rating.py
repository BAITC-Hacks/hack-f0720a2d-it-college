"""Проверки формулы, порогов и подсказок рейтинга."""

from app.modules.rating.service import FIELD_WEIGHTS, calculate


def test_empty_and_complete_rating():
    empty = calculate({})
    assert empty["score"] == 0
    assert empty["level"] == "draft"
    assert "Добавьте критерии успеха — +15 баллов" in empty["missing"]

    complete = calculate({field: "Достаточно подробное описание поля длиной более тридцати символов" for field in FIELD_WEIGHTS})
    assert complete["score"] == 100
    assert complete["level"] == "priority"
    assert complete["missing"] == []


def test_short_fields_get_half_weight():
    result = calculate({field: "Кратко" for field in FIELD_WEIGHTS})
    assert result["score"] == 50
    assert result["level"] == "working"
    assert all(item["state"] == "short" for item in result["breakdown"].values())
