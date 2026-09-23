"""REST-клиент Responses API со строгим JSON-контрактом и безопасными ошибками."""

import json
import re
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.modules.ai.errors import AIServiceError
from app.modules.ai.schemas import ModelInfo

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
Result = TypeVar("Result", bound=BaseModel)


def create_client(timeout: float) -> httpx.Client:
    """Точка подмены транспорта в тестах; ключ не хранится в глобальном клиенте."""
    return httpx.Client(timeout=timeout, follow_redirects=False)


def _validate_header_key(key: str) -> None:
    if not key.isascii() or any(ord(char) < 32 or ord(char) == 127 for char in key):
        raise AIServiceError(503, "Проверьте формат API-ключа OpenAI в настройках.")


def _response_error(response: httpx.Response) -> AIServiceError:
    if response.status_code == 429:
        try:
            body = response.json()
            error = body.get("error", {}) if isinstance(body, dict) else {}
            code = error.get("code") if isinstance(error, dict) else None
            kind = error.get("type") if isinstance(error, dict) else None
        except ValueError:
            code = kind = None
        if code == "insufficient_quota" or kind == "insufficient_quota":
            return AIServiceError(429, "Лимит средств OpenAI API исчерпан. Проверьте баланс и лимиты проекта.")
        return AIServiceError(429, "OpenAI временно ограничил число запросов. Попробуйте немного позже.")
    if response.status_code in (401, 403):
        return AIServiceError(503, "OpenAI не разрешил запрос. Проверьте API-ключ и права проекта на сервере.")
    if response.status_code in (400, 404):
        return AIServiceError(503, "OpenAI не принял настройки запроса. Проверьте модель и её доступность для проекта.")
    return AIServiceError(503, "Сервис OpenAI временно недоступен. Попробуйте повторить запрос позже.")


def _extract_json(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        raise AIServiceError(502, "OpenAI вернул некорректный ответ. Повторите запрос.") from None
    if not isinstance(body, dict):
        raise AIServiceError(502, "OpenAI вернул некорректный ответ. Повторите запрос.")
    output = body.get("output")
    if not isinstance(output, list):
        raise AIServiceError(502, "OpenAI не вернул результат анализа. Повторите запрос.")
    fragments = []
    for item in output:
        if not isinstance(item, dict):
            raise AIServiceError(502, "OpenAI вернул некорректную структуру ответа. Повторите запрос.")
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            raise AIServiceError(502, "OpenAI вернул некорректную структуру ответа. Повторите запрос.")
        for block in content:
            if not isinstance(block, dict):
                raise AIServiceError(502, "OpenAI вернул некорректную структуру ответа. Повторите запрос.")
            if block.get("type") == "refusal":
                raise AIServiceError(502, "OpenAI не смог обработать описание. Уточните текст задачи и повторите запрос.")
            if block.get("type") == "output_text":
                value = block.get("text")
                if not isinstance(value, str):
                    raise AIServiceError(502, "OpenAI вернул некорректный текст ответа. Повторите запрос.")
                fragments.append(value)
    if body.get("status") != "completed":
        raise AIServiceError(502, "OpenAI не завершил ответ. Попробуйте сократить описание или повторить запрос.")
    value = "".join(fragments)
    if not value or len(value) > 120_000:
        raise AIServiceError(502, "OpenAI вернул пустой или слишком большой ответ. Повторите запрос.")
    try:
        result = json.loads(value)
    except (ValueError, RecursionError):
        raise AIServiceError(502, "OpenAI вернул некорректный JSON. Повторите запрос.") from None
    if not isinstance(result, dict):
        raise AIServiceError(502, "OpenAI вернул некорректную структуру данных. Повторите запрос.")
    return result


def request_json(
    settings: Settings, *, instructions: str, payload: dict,
    response_model: type[Result], schema_name: str,
) -> Result:
    secret = settings.openai_api_key
    key = secret.get_secret_value() if secret is not None else ""
    if not key:
        raise AIServiceError(503, "OpenAI не настроен: добавьте OPENAI_API_KEY на сервере.")
    _validate_header_key(key)
    body = {
        "model": settings.openai_model,
        "instructions": instructions,
        "input": [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        "text": {"format": {
            "type": "json_schema", "name": schema_name,
            "schema": response_model.model_json_schema(), "strict": True,
        }},
        "store": False,
        "max_output_tokens": settings.openai_max_output_tokens,
    }
    try:
        with create_client(settings.ai_timeout_seconds) as client:
            response = client.post(
                OPENAI_RESPONSES_URL, json=body,
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            )
    except httpx.TimeoutException:
        raise AIServiceError(504, "OpenAI не ответил вовремя. Попробуйте повторить запрос.") from None
    except httpx.RequestError:
        raise AIServiceError(503, "Не удалось связаться с OpenAI. Проверьте подключение сервера и повторите запрос.") from None
    except UnicodeError:
        raise AIServiceError(503, "Проверьте формат API-ключа OpenAI в настройках.") from None
    if not response.is_success:
        raise _response_error(response)
    result = _extract_json(response)
    try:
        return response_model.model_validate(result)
    except ValidationError:
        raise AIServiceError(502, "Ответ OpenAI не соответствует формату карточки. Повторите запрос.") from None


def list_models(key: str, timeout: float) -> list[ModelInfo]:
    """Обнаружение моделей использует фиксированный origin и безопасные ошибки."""
    if not key:
        raise AIServiceError(503, "OpenAI не настроен: добавьте API-ключ в настройках AI или на сервере.")
    _validate_header_key(key)
    try:
        with create_client(timeout) as client:
            response = client.get("https://api.openai.com/v1/models", headers={"Authorization": "Bearer " + key})
    except httpx.TimeoutException:
        raise AIServiceError(504, "OpenAI не ответил вовремя. Попробуйте повторить запрос.") from None
    except httpx.RequestError:
        raise AIServiceError(503, "Не удалось связаться с OpenAI. Повторите запрос.") from None
    except UnicodeError:
        raise AIServiceError(503, "Проверьте формат API-ключа OpenAI в настройках.") from None
    if not response.is_success:
        raise _response_error(response)
    try:
        entries = response.json()["data"]
        if not isinstance(entries, list):
            raise ValueError
        models, seen = [], set()
        for entry in entries:
            name = entry["id"]
            if not isinstance(name, str) or not name.strip() or len(name) > 240:
                raise ValueError
            if name not in seen:
                models.append(ModelInfo(id=name, chat_candidate=not bool(re.search(
                    r"embedding|embed-|whisper|tts-|dall-e|transcribe", name, re.I))))
                seen.add(name)
        return models
    except (ValueError, KeyError, TypeError):
        raise AIServiceError(502, "OpenAI вернул некорректный список моделей. Повторите запрос.") from None
