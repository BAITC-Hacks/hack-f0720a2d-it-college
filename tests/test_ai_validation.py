"""Проверки источников из upstream, перенесённые на OpenAI-compatible транспорт."""

import json

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.ai import service
from app.modules.ai.schemas import AnalyzeDraftOutput, BuildCardInput, CARD_FIELDS


def reply_with(fake_ai, **fields):
    card = {**dict.fromkeys(CARD_FIELDS, []), **fields}
    fake_ai["reply"] = lambda request: httpx.Response(200, json={"choices": [
        {"message": {"content": json.dumps(card)}, "finish_reason": "stop"}
    ]}) if request.method == "POST" else None


def test_without_key_still_calls_configured_provider(fake_ai):
    result = service.build_card("Описание бизнеса.", {})
    assert result["context"] == "Описание бизнеса."
    assert any(request.method == "POST" for request in fake_ai["requests"])


@pytest.mark.parametrize("quote", ["invented@example.org", "Бюджет 100000 тенге"])
def test_invention_is_rejected(fake_ai, quote):
    reply_with(fake_ai, data=[quote])
    with pytest.raises(HTTPException) as error:
        service.build_card("Есть таблица заказов, но её нельзя передавать студентам.", {})
    assert error.value.status_code == 502
    assert len([r for r in fake_ai["requests"] if r.method == "POST"]) == 2


def test_partial_quote_restores_restrictions_from_source(fake_ai):
    raw = "Есть таблица заказов, но её нельзя передавать студентам."
    reply_with(fake_ai, data=["Есть таблица заказов"])
    assert service.build_card(raw, {})["data"] == raw


def test_ambiguous_partial_quote_is_rejected(fake_ai):
    reply_with(fake_ai, data=["таблица"])
    with pytest.raises(HTTPException) as error:
        service.build_card("Есть таблица заказов. Есть таблица поставщиков.", {})
    assert error.value.status_code == 502


def test_labeled_source_and_whole_sentences_are_accepted(fake_ai):
    reply_with(fake_ai, data=["Таблица заказов за год"], context=["Поддержка работает медленно."])
    result = service.build_card("Поддержка работает медленно. Нужна помощь.\nДанные: Таблица заказов за год", {})
    assert result["data"] == "Таблица заказов за год"
    assert result["context"] == "Поддержка работает медленно."


@pytest.mark.parametrize("raw", ["Краткое описание бизнеса.", "Обратная связь каждую пятницу."])
def test_answer_cannot_move_to_another_field_even_if_present_in_raw(fake_ai, raw):
    answer = "Обратная связь каждую пятницу."
    reply_with(fake_ai, constraints=[answer])
    with pytest.raises(HTTPException) as error:
        service.build_card(raw, {"contact": answer})
    assert error.value.status_code == 502


def test_manual_answer_has_priority_over_model(fake_ai):
    reply_with(fake_ai, context=["старые сведения"])
    assert service.build_card("Контекст: старые сведения", {"context": "Исправленные сведения"})["context"] == "Исправленные сведения"


@pytest.mark.parametrize("answers", [{"unknown": "нет"}, {"title": "x" * 241}, {"need": "x" * 10001}, {"data": 12}])
def test_input_rejects_unknown_fields_bad_types_and_lengths(answers):
    with pytest.raises(ValidationError):
        BuildCardInput(raw_text="Текст", answers=answers)


def test_output_rejects_unknown_empty_or_repeated_questions():
    with pytest.raises(ValidationError):
        AnalyzeDraftOutput(missing_fields=["unknown"], questions=[{"field": "unknown", "text": ""}] * 3)
    with pytest.raises(ValidationError):
        AnalyzeDraftOutput(missing_fields=["need"], questions=[{"field": "need", "text": "Что нужно?"}] * 3)


def test_errors_do_not_log_sensitive_provider_or_user_text(fake_ai, caplog):
    def timeout(request):
        raise httpx.ReadTimeout("sensitive-provider-error", request=request)
    fake_ai["reply"] = timeout
    with pytest.raises(HTTPException) as error:
        service.build_card("Приватный исходный текст.", {})
    assert error.value.status_code == 504
    assert "sensitive-provider-error" not in caplog.text
    assert "Приватный" not in caplog.text
