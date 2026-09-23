"""Responses integration uses synthetic credentials and MockTransport only."""

import json

import httpx
import pytest

from app.config import get_settings
from app.modules.ai import provider, service
from app.modules.ai.errors import AIServiceError
from app.modules.ai.schemas import CARD_FIELDS
from app.modules.users.models import User


FAKE_KEY = "sk-unit-test-only-not-a-real-key"
PRIVATE_UPSTREAM_TEXT = "private upstream diagnostic must not reach the browser"
RAW_TEXT = "Магазин долго обрабатывает обращения покупателей о доставке."


def analysis_result():
    return {
        "missing_fields": ["data", "success_criteria", "contact"],
        "questions": [
            {"field": "data", "text": "Есть ли обезличенные примеры обращений о доставке?"},
            {"field": "success_criteria", "text": "На сколько минут нужно сократить обработку обращения?"},
            {"field": "contact", "text": "Кто из магазина проверит ответы на обращения?"},
        ],
    }


def card_result():
    result = dict.fromkeys(CARD_FIELDS)
    result.update(
        title="Обработка обращений о доставке",
        context=RAW_TEXT,
        need="Сократить время ответа покупателю",
        expected_result="Прототип сервиса обработки обращений",
    )
    return result


def response_body(result):
    return {
        "id": "resp_test",
        "status": "completed",
        "output": [{
            "id": "msg_test", "type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": json.dumps(result, ensure_ascii=False), "annotations": []}],
        }],
    }


@pytest.fixture
def openai_mock(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini-test")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("OPENAI_MAX_OUTPUT_TOKENS", "2048")
    get_settings.cache_clear()
    requests = []
    timeouts = []

    def install(handler):
        def record(request):
            requests.append(request)
            return handler(request)

        def create_client(timeout):
            timeouts.append(timeout)
            return httpx.Client(transport=httpx.MockTransport(record), timeout=timeout)

        monkeypatch.setattr(provider, "create_client", create_client)
        return requests, timeouts

    return install


def assert_strict_objects(value):
    if isinstance(value, dict):
        if value.get("type") == "object":
            assert value.get("additionalProperties") is False
            assert set(value.get("required", [])) == set(value.get("properties", {}))
        for child in value.values():
            assert_strict_objects(child)
    elif isinstance(value, list):
        for child in value:
            assert_strict_objects(child)


@pytest.mark.parametrize("operation", ["analyze", "build"])
def test_responses_request_has_auth_strict_schema_and_context(openai_mock, operation):
    expected = analysis_result() if operation == "analyze" else card_result()
    requests, timeouts = openai_mock(lambda _: httpx.Response(200, json=response_body(expected)))
    if operation == "analyze":
        actual = service.analyze_draft(RAW_TEXT, known_fields={"industry": "Торговля"})
        assert actual == {**expected, "provider": "openai"}
    else:
        actual = service.build_card(RAW_TEXT, {"need": expected["need"]})
        assert actual == expected
        assert actual["contact"] is None

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.openai.com/v1/responses"
    assert request.headers["Authorization"] == f"Bearer {FAKE_KEY}"
    assert request.headers["Content-Type"].startswith("application/json")
    body = json.loads(request.content)
    assert body["model"] == "gpt-4.1-mini-test"
    assert body["store"] is False
    assert body["max_output_tokens"] == 2048
    assert timeouts == [12.5]
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["strict"] is True
    assert_strict_objects(body["text"]["format"]["schema"])
    sent_input = json.dumps(body["input"], ensure_ascii=False)
    assert RAW_TEXT in sent_input
    assert ("Торговля" if operation == "analyze" else expected["need"]) in sent_input
    assert FAKE_KEY not in json.dumps(body)


def test_output_text_can_follow_other_response_items(openai_mock):
    body = response_body(analysis_result())
    body["output"].insert(0, {"type": "reasoning", "id": "reasoning_test", "summary": []})
    openai_mock(lambda _: httpx.Response(200, json=body))
    assert service.analyze_draft(RAW_TEXT)["questions"][0]["field"] == "data"


def test_known_fields_are_sent_and_not_reported_missing(openai_mock):
    expected = analysis_result()
    requests, _ = openai_mock(lambda _: httpx.Response(200, json=response_body(expected)))
    actual = service.analyze_draft(RAW_TEXT, known_fields={"data": "Обезличенные обращения за месяц"})
    assert "data" not in actual["missing_fields"]
    assert "Обезличенные обращения за месяц" in requests[0].content.decode()


@pytest.mark.parametrize("status,expected_status", [(400, 503), (401, 503), (403, 503), (429, 429), (500, 503), (503, 503)])
def test_http_errors_are_safe_and_never_fall_back_to_stub(openai_mock, monkeypatch, status, expected_status):
    monkeypatch.setenv("AI_PROVIDER", "auto")
    get_settings.cache_clear()
    requests, _ = openai_mock(lambda _: httpx.Response(status, json={"error": {
        "message": f"{PRIVATE_UPSTREAM_TEXT}: {FAKE_KEY}", "code": "insufficient_quota" if status == 429 else "error",
    }}))
    with pytest.raises(AIServiceError) as exc:
        service.analyze_draft(RAW_TEXT)
    assert exc.value.status_code == expected_status
    assert exc.value.detail
    assert FAKE_KEY not in str(exc.value)
    assert PRIVATE_UPSTREAM_TEXT not in exc.value.detail
    assert len(requests) == 1


@pytest.mark.parametrize("kind,expected_status", [("timeout", 504), ("connection", 503)])
def test_transport_failures_are_safe(openai_mock, kind, expected_status):
    def fail(request):
        error_type = httpx.ReadTimeout if kind == "timeout" else httpx.ConnectError
        raise error_type(f"{PRIVATE_UPSTREAM_TEXT}: {FAKE_KEY}", request=request)

    openai_mock(fail)
    with pytest.raises(AIServiceError) as exc:
        service.build_card(RAW_TEXT, {"need": "Сократить время ответа"})
    assert exc.value.status_code == expected_status
    assert FAKE_KEY not in str(exc.value)
    assert PRIVATE_UPSTREAM_TEXT not in exc.value.detail


@pytest.mark.parametrize("kind", ["http_json", "output_json", "refusal", "incomplete", "empty", "unknown_field", "duplicate_question", "duplicate_missing", "missing_card_fields"])
def test_invalid_responses_are_rejected(openai_mock, kind):
    result = analysis_result()
    body = response_body(result)
    operation = lambda: service.analyze_draft(RAW_TEXT)
    if kind == "http_json":
        response = httpx.Response(200, text="not JSON")
    else:
        if kind == "output_json":
            body["output"][0]["content"][0]["text"] = "{invalid JSON"
        elif kind == "refusal":
            body["output"][0]["content"] = [{"type": "refusal", "refusal": PRIVATE_UPSTREAM_TEXT}]
        elif kind == "incomplete":
            body["status"] = "incomplete"
            body["incomplete_details"] = {"reason": "max_output_tokens"}
        elif kind == "empty":
            body["output"] = []
        elif kind == "unknown_field":
            result["questions"][0]["field"] = "invented_field"
            body = response_body(result)
        elif kind == "duplicate_question":
            result["questions"][1] = dict(result["questions"][0])
            body = response_body(result)
        elif kind == "duplicate_missing":
            result["missing_fields"].append("data")
            body = response_body(result)
        elif kind == "missing_card_fields":
            body = response_body({"context": RAW_TEXT})
            operation = lambda: service.build_card(RAW_TEXT, {"need": "Сократить время ответа"})
        response = httpx.Response(200, json=body)
    openai_mock(lambda _: response)
    with pytest.raises(AIServiceError) as exc:
        operation()
    assert exc.value.status_code == 502
    assert PRIVATE_UPSTREAM_TEXT not in exc.value.detail


@pytest.mark.parametrize("operation", [
    lambda: service.analyze_draft("   "),
    lambda: service.analyze_draft(RAW_TEXT, {"invented_field": "value"}),
    lambda: service.build_card(RAW_TEXT, {"invented_field": "value"}),
])
def test_invalid_inputs_do_not_make_http_requests(openai_mock, operation):
    requests, _ = openai_mock(lambda _: httpx.Response(200, json=response_body(analysis_result())))
    with pytest.raises(AIServiceError) as exc:
        operation()
    assert exc.value.status_code == 422
    assert requests == []


@pytest.mark.parametrize("configured", [True, False])
def test_ai_status_is_safe_and_does_not_call_provider(client, openai_mock, monkeypatch, configured):
    if not configured:
        monkeypatch.setenv("OPENAI_API_KEY", "")
        get_settings.cache_clear()
    requests, _ = openai_mock(lambda _: pytest.fail("Status must not call OpenAI"))
    response = client.get("/api/ai/status")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is configured
    assert body["provider"] == "openai"
    assert body["model"] == "gpt-4.1-mini-test"
    assert FAKE_KEY not in response.text
    assert "api_key" not in response.text.lower()
    assert requests == []


@pytest.fixture
def saved_task(client, db):
    db.add(User(id=1, name="Бизнес", role="business"))
    db.commit()
    headers = {"X-User-Id": "1"}
    task = client.post("/api/tasks/draft", headers=headers, json={
        "raw_text": RAW_TEXT, "title": "Сохранённое название", "industry": "Торговля",
    }).json()
    url = f"/api/tasks/{task['id']}"
    assert client.patch(url, headers=headers, json={"context": "Сохранённый контекст задачи", "need": "Сохранённая потребность"}).status_code == 200
    assert client.post(url + "/confirm", headers=headers).status_code == 200
    return url, headers, client.get(url).json()


@pytest.mark.parametrize("endpoint", ["questions", "card"])
@pytest.mark.parametrize("failure,expected_status", [("rate_limit", 429), ("malformed", 502), ("timeout", 504)])
def test_task_ai_failure_has_friendly_error_and_preserves_saved_card(client, saved_task, openai_mock, endpoint, failure, expected_status):
    def respond(request):
        if failure == "rate_limit":
            return httpx.Response(429, json={"error": {"message": f"{PRIVATE_UPSTREAM_TEXT}: {FAKE_KEY}"}})
        if failure == "timeout":
            raise httpx.ReadTimeout(f"{PRIVATE_UPSTREAM_TEXT}: {FAKE_KEY}", request=request)
        return httpx.Response(200, json=response_body({"incorrect": "response"}))

    openai_mock(respond)
    url, headers, before = saved_task
    response = client.post(url + "/" + endpoint, headers=headers, json={"answers": {"need": "Новая потребность"}} if endpoint == "card" else None)
    assert response.status_code == expected_status
    assert isinstance(response.json()["detail"], str)
    assert response.json()["detail"]
    assert FAKE_KEY not in response.text
    assert PRIVATE_UPSTREAM_TEXT not in response.text
    assert client.get(url).json() == before


def test_task_endpoints_pass_existing_fields_and_store_valid_ai_card(client, saved_task, openai_mock):
    expected = card_result()
    responses = [analysis_result(), expected]
    requests, _ = openai_mock(lambda _: httpx.Response(200, json=response_body(responses.pop(0))))
    url, headers, before = saved_task
    questions = client.post(url + "/questions", headers=headers)
    assert questions.status_code == 200
    assert questions.json()["provider"] == "openai"
    assert "Сохранённое название" in requests[0].content.decode()
    assert "Сохранённая потребность" in requests[0].content.decode()
    response = client.post(url + "/card", headers=headers, json={"answers": {"need": expected["need"]}})
    assert response.status_code == 200
    assert response.json()["context"] == before["context"]
    assert response.json()["title"] == before["title"]
    assert response.json()["industry"] == before["industry"]
    assert response.json()["expected_result"] == expected["expected_result"]
    assert response.json()["need"] == expected["need"]
    assert response.json()["status"] == "draft"
    assert response.json()["score"] > 0
    assert "Сохранённое название" in requests[1].content.decode()
    assert "Сократить время ответа покупателю" in requests[1].content.decode()
    assert client.get(url).json() == response.json()


def test_settings_do_not_expose_api_key_in_repr(openai_mock):
    assert FAKE_KEY not in repr(get_settings())


def test_skipped_answer_does_not_clear_fact_from_raw_text(openai_mock):
    result = card_result()
    result["contact"] = "Ирина, менеджер магазина"
    openai_mock(lambda _: httpx.Response(200, json=response_body(result)))
    card = service.build_card(RAW_TEXT + " Контакт: Ирина, менеджер магазина.", {"contact": ""})
    assert card["contact"] == "Ирина, менеджер магазина"


def test_skipped_question_preserves_existing_task_fields(client, saved_task, openai_mock):
    openai_mock(lambda _: httpx.Response(200, json=response_body(card_result())))
    url, headers, before = saved_task
    response = client.post(url + "/card", headers=headers, json={"answers": {"need": "   "}})
    assert response.status_code == 200
    assert response.json()["need"] == before["need"]


def test_nonempty_answer_takes_precedence_over_model_text(openai_mock):
    openai_mock(lambda _: httpx.Response(200, json=response_body(card_result())))
    card = service.build_card(RAW_TEXT, {"need": "  Ответ пользователя важнее перефразирования  "})
    assert card["need"] == "Ответ пользователя важнее перефразирования"
