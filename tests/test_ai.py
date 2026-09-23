"""OpenAI-compatible HTTP, JSON-совместимость, источники фактов и ошибки модели."""

import json

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.ai import provider, service
from app.modules.ai.schemas import CARD_FIELDS, ConnectionInput


def completion(content, finish="stop"):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": finish}]})


def empty_card(**values):
    return {**dict.fromkeys(CARD_FIELDS, []), **values}


def test_real_contract_uses_model_and_preserves_sources(fake_ai):
    raw = "Покупатели долго ждут ответов на обращения."
    analysis = service.analyze_draft(raw, known_fields={"industry": "Ритейл"})
    assert len(analysis["questions"]) >= 3
    assert analysis["detected_fields"]["industry"] == "Ритейл"
    card = service.build_card(raw, {"need": "Сократить время ответа"})
    assert card["context"] == raw
    assert card["need"] == "Сократить время ответа"
    assert card["contact"] is None
    request = next(r for r in fake_ai["requests"] if r.method == "POST")
    body = json.loads(request.content)
    assert body["model"] == "demo-model"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert request.url.path == "/v1/chat/completions"


@pytest.mark.parametrize("url,expected", [
    ("http://localhost:1234/", "http://localhost:1234/v1"),
    ("https://llm.example.org/proxy/v1/", "https://llm.example.org/proxy/v1"),
    ("http://[::1]:1234", "http://[::1]:1234/v1"),
])
def test_local_and_public_base_urls(url, expected):
    assert ConnectionInput(base_url=url).base_url == expected


@pytest.mark.parametrize("url", ["file:///secret", "https://user:password@example.com/v1", "https://example.com/v1?key=secret", "http://localhost:1234/v1/chat/completions"])
def test_invalid_base_url(url):
    with pytest.raises(ValidationError):
        ConnectionInput(base_url=url)


def test_model_discovery_and_explicit_selection(fake_ai):
    fake_ai["models"] = ["text-embedding-nomic", "test-chat", "other-chat"]
    connection = provider.Connection("https://llm.example.org/prefix/v1", api_key="test-secret")
    models = provider.list_models(connection)
    assert len(models) == 3
    assert not models[0].chat_candidate
    assert provider.select_model(connection, models) == "test-chat"
    assert fake_ai["requests"][0].url.path == "/prefix/v1/models"
    assert fake_ai["requests"][0].headers["authorization"] == "Bearer test-secret"
    with pytest.raises(HTTPException) as failure:
        provider.select_model(provider.Connection(connection.base_url, model="missing"), models)
    assert failure.value.status_code == 409


def test_empty_model_list_is_actionable(fake_ai):
    fake_ai["models"] = []
    with pytest.raises(HTTPException) as failure:
        service.analyze_draft("Описание задачи")
    assert failure.value.status_code == 503


def test_invalid_json_retried_once_then_rejected(fake_ai):
    fake_ai["reply"] = lambda request: completion("not JSON") if request.method == "POST" else None
    with pytest.raises(HTTPException) as failure:
        service.build_card("Исходные сведения", {})
    assert failure.value.status_code == 502
    assert len([r for r in fake_ai["requests"] if r.method == "POST"]) == 2


def test_retry_can_recover_and_accept_fenced_json(fake_ai):
    count = 0
    def reply(request):
        nonlocal count
        if request.method == "POST":
            count += 1
            return completion("broken" if count == 1 else "```json\n" + json.dumps(empty_card(context=["Исходные сведения"])) + "\n```")
    fake_ai["reply"] = reply
    assert service.build_card("Исходные сведения", {})["context"] == "Исходные сведения"
    assert count == 2


def test_invented_facts_rejected(fake_ai):
    fake_ai["reply"] = lambda request: completion(json.dumps(empty_card(contact=["Иван, +79999999999"]))) if request.method == "POST" else None
    with pytest.raises(HTTPException) as failure:
        service.build_card("Контакт пока не указан", {})
    assert failure.value.status_code == 502


def test_manual_answers_take_priority(fake_ai):
    fake_ai["reply"] = lambda request: completion(json.dumps(empty_card(constraints=["Три недели"]))) if request.method == "POST" else None
    result = service.build_card("Три недели", {"constraints": "Четыре недели"})
    assert result["constraints"] == "Четыре недели"


def test_unsupported_schema_falls_back_to_json_mode(fake_ai):
    def reply(request):
        if request.method == "POST" and json.loads(request.content).get("response_format", {}).get("type") == "json_schema":
            return httpx.Response(400, json={"error": "response_format json_schema unsupported"})
    fake_ai["reply"] = reply
    assert service.build_card("Исходные сведения", {})["context"] == "Исходные сведения"
    modes = [json.loads(r.content)["response_format"]["type"] for r in fake_ai["requests"] if r.method == "POST"]
    assert modes == ["json_schema", "json_object"]


@pytest.mark.parametrize("status,expected", [(401, 502), (403, 502), (404, 502), (429, 503), (500, 503)])
def test_provider_errors_are_sanitized(fake_ai, status, expected):
    fake_ai["reply"] = lambda request: httpx.Response(status, json={"error": "test-secret"})
    with pytest.raises(HTTPException) as failure:
        service.analyze_draft("Исходные сведения")
    assert failure.value.status_code == expected
    assert "test-secret" not in failure.value.detail


@pytest.mark.parametrize("exception,code", [(httpx.ConnectError, 503), (httpx.ReadTimeout, 504)])
def test_network_errors(fake_ai, exception, code):
    def reply(request):
        raise exception("failure", request=request)
    fake_ai["reply"] = reply
    with pytest.raises(HTTPException) as failure:
        service.analyze_draft("Исходные сведения")
    assert failure.value.status_code == code


def test_truncated_output_is_not_applied(fake_ai):
    fake_ai["reply"] = lambda request: completion(json.dumps(empty_card()), "length") if request.method == "POST" else None
    with pytest.raises(HTTPException) as failure:
        service.build_card("Исходные сведения", {})
    assert failure.value.status_code == 502


@pytest.mark.parametrize("choices", [None, [None], [{"message": "invalid"}]])
def test_malformed_envelope_is_502(fake_ai, choices):
    fake_ai["reply"] = lambda request: httpx.Response(200, json={"choices": choices}) if request.method == "POST" else None
    with pytest.raises(HTTPException) as failure:
        service.build_card("Исходные сведения", {})
    assert failure.value.status_code == 502


def test_json_in_text_mode_supported(fake_ai):
    def reply(request):
        if request.method == "POST" and "response_format" in json.loads(request.content):
            return httpx.Response(422, json={"error": "response_format unsupported"})
    fake_ai["reply"] = reply
    assert service.build_card("Исходные сведения", {})["context"] == "Исходные сведения"
    posts = [json.loads(r.content) for r in fake_ai["requests"] if r.method == "POST"]
    assert len(posts) == 3
    assert "response_format" not in posts[-1]
    assert "JSON Schema:" in posts[-1]["messages"][0]["content"]
