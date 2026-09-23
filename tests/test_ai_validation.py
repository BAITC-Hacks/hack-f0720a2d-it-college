"""AI-контракт, автономный режим, повтор и fallback: только подменённый транспорт."""

import json

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.modules.ai import client as ai_client
from app.modules.ai import service
from app.modules.ai.prompts import FIELD_LABELS, RETRY_PROMPT, SYSTEM_PROMPT
from app.modules.ai.schemas import AnalyzeDraftOutput, BuildCardInput, CARD_FIELDS, CardFields


@pytest.fixture(autouse=True)
def offline_by_default(monkeypatch):
    monkeypatch.setattr(service, "get_settings", lambda: Settings(openai_api_key=None))

    def refuse_network(*args, **kwargs):
        raise AssertionError("Тест не должен отправлять запрос в сеть")

    monkeypatch.setattr(ai_client.httpx, "post", refuse_network)


def enable_fake_key(monkeypatch):
    monkeypatch.setattr(service, "get_settings", lambda: Settings(openai_api_key="unit-test-only"))


def full_card(raw_text, **fields):
    return json.dumps(CardFields(context=raw_text, **fields).model_dump(), ensure_ascii=False)


def test_without_key_never_calls_provider(monkeypatch):
    monkeypatch.setattr(service, "request_card", lambda *a, **kw: pytest.fail("Provider called"))
    raw_text = "Хотим сократить время обработки обращений."
    assert service.build_card(raw_text, {})["context"] == raw_text
    assert len(service.analyze_draft(raw_text)["questions"]) >= 3


def test_labeled_fallback_detects_only_missing_fields():
    raw_text = "Название: Помощник\nДанные: Таблица заказов за год\nКонтакт: business@example.org"
    analysis = service.analyze_draft(raw_text)
    assert not {"title", "data", "contact"}.intersection(analysis["missing_fields"])
    assert "context" in analysis["missing_fields"]
    card = service.build_card(raw_text, {"need": "Уменьшить время обработки"})
    assert card["data"] == "Таблица заказов за год"
    assert card["need"] == "Уменьшить время обработки"
    assert card["context"] is None
    assert card["success_criteria"] is None


def test_complete_draft_still_has_three_distinct_review_questions():
    raw_text = "\n".join(f"{FIELD_LABELS[field][0]}: Сведения для {field}" for field in CARD_FIELDS)
    result = service.analyze_draft(raw_text)
    assert result["missing_fields"] == []
    assert len(result["questions"]) == 3
    assert len({item["field"] for item in result["questions"]}) == 3


def test_invalid_json_retried_once_then_validated(monkeypatch):
    enable_fake_key(monkeypatch)
    raw_text = "Покупатели долго ждут ответа."
    calls = []

    def provider(payload, **kwargs):
        calls.append(kwargs["retry"])
        return "это не JSON" if len(calls) == 1 else full_card(raw_text, need="Покупатели долго ждут ответа.")

    monkeypatch.setattr(service, "request_card", provider)
    result = service.build_card(raw_text, {})
    assert calls == [False, True]
    assert result["need"] == raw_text


def test_valid_provider_extraction_affects_questions(monkeypatch):
    enable_fake_key(monkeypatch)
    raw_text = "Процесс занимает много времени. Есть таблица заказов за год."
    attempts = []

    def provider(*args, **kwargs):
        attempts.append(kwargs["retry"])
        return full_card("Процесс занимает много времени.", data="Есть таблица заказов за год.")

    monkeypatch.setattr(service, "request_card", provider)
    result = service.analyze_draft(raw_text)
    assert "data" not in result["missing_fields"]
    assert "contact" in result["missing_fields"]
    assert attempts == [False]


@pytest.mark.parametrize("response", ["не JSON", "{}", "[]", '{"unknown": 12}'])
def test_two_invalid_responses_use_local_fallback(monkeypatch, response):
    enable_fake_key(monkeypatch)
    attempts = []

    def provider(*args, **kwargs):
        attempts.append(kwargs["retry"])
        return response

    monkeypatch.setattr(service, "request_card", provider)
    card = service.build_card("Описание бизнеса.", {"need": "Дословный ответ владельца"})
    assert attempts == [False, True]
    assert card["need"] == "Дословный ответ владельца"
    assert card["contact"] is None


def test_network_timeout_uses_fallback_without_logging_input(monkeypatch, caplog):
    enable_fake_key(monkeypatch)

    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("sensitive-provider-error")

    monkeypatch.setattr(service, "request_card", timeout)
    assert service.build_card("Приватный исходный текст.", {})["context"] == "Приватный исходный текст."
    assert len(caplog.records) == 3
    assert "unit-test-only" not in caplog.text
    assert "sensitive-provider-error" not in caplog.text
    assert "Приватный" not in caplog.text


@pytest.mark.parametrize(
    "extra",
    [
        {"contact": "invented@example.org"},
        {"constraints": "Бюджет 100000 тенге"},
        {"data": "Есть таблица заказов."},
    ],
)
def test_invented_facts_are_rejected(monkeypatch, extra):
    enable_fake_key(monkeypatch)
    raw_text = "Есть таблица заказов, но её нельзя передавать студентам."
    monkeypatch.setattr(service, "request_card", lambda *a, **kw: full_card(raw_text, **extra))
    result = service.build_card(raw_text, {})
    assert result["context"] == raw_text
    for field in extra:
        assert result[field] is None


def test_answer_cannot_move_to_another_field(monkeypatch):
    enable_fake_key(monkeypatch)
    raw_text = "Краткое описание бизнеса."
    answer = "Важный срок, который указал пользователь"
    monkeypatch.setattr(service, "request_card", lambda *a, **kw: full_card(raw_text, need=answer))
    result = service.build_card(raw_text, {"constraints": answer})
    assert result["constraints"] == answer
    assert result["need"] is None


def test_answer_cannot_move_even_when_the_same_text_is_in_raw(monkeypatch):
    enable_fake_key(monkeypatch)
    raw_text = "Обратная связь каждую пятницу."
    monkeypatch.setattr(service, "request_card", lambda *a, **kw: full_card(raw_text, contact=raw_text, constraints=raw_text))
    result = service.build_card(raw_text, {"contact": raw_text})
    assert result["contact"] == raw_text
    assert result["constraints"] is None


def test_explicit_answer_cannot_be_changed_by_provider(monkeypatch):
    enable_fake_key(monkeypatch)
    raw_text = "Контекст: старые сведения"
    monkeypatch.setattr(service, "request_card", lambda *a, **kw: full_card("старые сведения"))
    assert service.build_card(raw_text, {"context": "Исправленные сведения"})["context"] == "Исправленные сведения"


@pytest.mark.parametrize("answers", [{"unknown": "нет"}, {"title": "x" * 241}, {"need": "x" * 10_001}, {"data": 12}])
def test_input_rejects_unknown_fields_bad_types_and_lengths(answers):
    with pytest.raises(ValidationError):
        BuildCardInput(raw_text="Текст", answers=answers)


def test_output_rejects_unknown_empty_or_repeated_questions():
    with pytest.raises(ValidationError):
        AnalyzeDraftOutput(missing_fields=["unknown"], questions=[{"field": "unknown", "text": ""}] * 3)
    with pytest.raises(ValidationError):
        AnalyzeDraftOutput(missing_fields=["need"], questions=[{"field": "need", "text": "Что нужно?"}] * 3)


def test_responses_request_uses_prompt_schema_and_nonpersistent_storage(monkeypatch):
    raw_text = "Поддержка работает медленно."
    payload = BuildCardInput(raw_text=raw_text, answers={})
    captures = []

    def mock_post(url, **kwargs):
        captures.append((url, kwargs))
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "status": "completed", "output": [
                {"type": "reasoning", "summary": []},
                {"type": "message", "content": [{"type": "output_text", "text": full_card(raw_text)}]},
            ],
        })

    monkeypatch.setattr(ai_client.httpx, "post", mock_post)
    text = ai_client.request_card(payload, api_key="unit-test-only", model="test-model", retry=True)
    assert json.loads(text)["context"] == raw_text
    url, kwargs = captures[0]
    assert url == "https://api.openai.com/v1/responses"
    body = kwargs["json"]
    assert SYSTEM_PROMPT in body["instructions"] and RETRY_PROMPT in body["instructions"]
    assert json.loads(body["input"]) == payload.model_dump()
    assert body["store"] is False
    output_schema = body["text"]["format"]
    assert output_schema["strict"] is True
    assert set(output_schema["schema"]["required"]) == set(CARD_FIELDS)
    assert output_schema["schema"]["additionalProperties"] is False


@pytest.mark.parametrize("body", [
    {"status": "incomplete", "output": []},
    {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "Нет"}]}]},
    {"status": "completed", "output": []},
    {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": 12}]}]},
])
def test_responses_refusal_incomplete_and_empty_output_are_errors(monkeypatch, body):
    monkeypatch.setattr(ai_client.httpx, "post", lambda url, **kwargs: httpx.Response(
        200, request=httpx.Request("POST", url), json=body,
    ))
    with pytest.raises(ValueError):
        ai_client.request_card(BuildCardInput(raw_text="Текст", answers={}), api_key="unit-test-only", model="test-model", retry=False)
