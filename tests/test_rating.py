"""Проверки формулы, порогов и подсказок рейтинга."""

import pytest

from app.modules.rating.service import FIELD_WEIGHTS, calculate, level_for_score


def test_empty_and_complete_rating():
    empty = calculate({})
    assert empty["score"] == 0
    assert empty["level"] == "draft"
    assert any("Добавьте критерии успеха — +15 баллов" in hint for hint in empty["missing"])

    complete = calculate({**{field: "Достаточно подробное описание поля длиной более тридцати символов" for field in FIELD_WEIGHTS}, "confirmed_fields": list(FIELD_WEIGHTS)})
    assert complete["score"] == 100
    assert complete["level"] == "priority"
    assert complete["missing"] == []


def test_short_fields_get_half_weight():
    result = calculate({**{field: "Кратко" for field in FIELD_WEIGHTS}, "confirmed_fields": list(FIELD_WEIGHTS)})
    assert result["score"] == 50
    assert result["level"] == "working"
    assert all(item["state"] == "short" for item in result["breakdown"].values())


@pytest.mark.parametrize("score,level", [(0, "draft"), (39, "draft"), (40, "working"),
    (69, "working"), (70, "ready"), (89, "ready"), (90, "priority"), (100, "priority")])
def test_exact_level_boundaries(score, level):
    assert level_for_score(score)[0] == level


@pytest.mark.parametrize("length,earned", [(0, 0), (1, 10), (29, 10), (30, 20)])
def test_field_length_boundary(length, earned):
    result = calculate({"data": "Я" * length, "confirmed_fields": ["data"]})
    assert result["score"] == earned


def test_confirmation_is_explicit_and_seven_indicators_total_100():
    card = {field: "А" * 30 for field in FIELD_WEIGHTS}
    result = calculate(card)
    assert result["score"] == 0 and result["potential_score"] == 100
    assert len(result["indicators"]) == 7
    assert sum(item["maximum"] for item in result["indicators"].values()) == 100
    assert result["indicators"]["context_need"]["maximum"] == 20
    card["confirmed_fields"] = list(FIELD_WEIGHTS)
    assert calculate(card)["score"] == 100
    card["data"] = ""
    assert calculate(card)["score"] == 80


def test_whitespace_does_not_earn_points():
    assert calculate({"data": " " * 100, "confirmed_fields": ["data"]})["score"] == 0
