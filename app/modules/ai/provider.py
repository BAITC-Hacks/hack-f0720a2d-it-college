"""HTTP-клиент Chat Completions для LM Studio, llmster и других совместимых API."""

import json
import re
from dataclasses import dataclass, field
from typing import Callable, TypeVar

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from app.modules.ai.schemas import ModelInfo

T = TypeVar("T")


@dataclass(frozen=True)
class Connection:
    base_url: str
    model: str = ""
    api_key: str = field(default="", repr=False)
    response_format: str = "auto"
    timeout: float = 180
    max_tokens: int = 4096


class InvalidAIResponse(ValueError):
    """Ответ нельзя безопасно применить к карточке."""


def _client(connection: Connection, *, discovery: bool = False) -> httpx.Client:
    return httpx.Client(
        base_url=connection.base_url.rstrip("/") + "/",
        headers={"Authorization": "Bearer " + connection.api_key} if connection.api_key else {},
        timeout=httpx.Timeout(10 if discovery else connection.timeout, connect=5),
        follow_redirects=False, trust_env=False,
    )


def _request(client: httpx.Client, method: str, path: str, **kwargs) -> httpx.Response:
    try:
        return client.request(method, path, **kwargs)
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "AI-сервер не ответил вовремя. Проверьте загрузку модели и повторите запрос.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(503, "Нет связи с AI-сервером. Запустите сервер LM Studio или проверьте адрес в настройках AI.") from exc


def _check_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    code = response.status_code
    if code in (401, 403):
        message = "AI-сервер отклонил доступ. Проверьте API-ключ в настройках AI."
    elif code == 404:
        message = "AI-сервер не нашёл маршрут или модель. Проверьте базовый адрес API и обновите список моделей."
    elif code == 429:
        message = "AI-сервер ограничил запросы. Повторите попытку позже."
    elif code in (400, 422):
        message = "AI-сервер отклонил запрос. Проверьте выбранную модель, её контекст и режим JSON в настройках AI."
    else:
        message = "AI-сервер временно недоступен или вернул ошибку. Повторите попытку."
    # Тело ошибки провайдера может содержать ключи и исходные данные.
    raise HTTPException(503 if code == 429 or code >= 500 else 502, message)


def list_models(connection: Connection) -> list[ModelInfo]:
    with _client(connection, discovery=True) as client:
        response = _request(client, "GET", "models")
    _check_status(response)
    try:
        data = response.json()["data"]
        if not isinstance(data, list):
            raise ValueError
        models, seen = [], set()
        for entry in data:
            model_id = entry["id"]
            if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 240:
                raise ValueError
            if model_id in seen:
                continue
            seen.add(model_id)
            candidate = not re.search(r"embedding|embed-|bge-|whisper|tts-|dall-e", model_id, re.I)
            models.append(ModelInfo(id=model_id, chat_candidate=candidate))
        return models
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(502, "AI-сервер вернул некорректный список моделей: ожидается data с идентификаторами id.") from exc


def select_model(connection: Connection, models: list[ModelInfo]) -> str:
    if connection.model:
        if not any(model.id == connection.model for model in models):
            raise HTTPException(409, "Выбранная AI-модель недоступна. Обновите список и выберите модель в настройках AI.")
        return connection.model
    candidate = next((model.id for model in models if model.chat_candidate), None)
    if not candidate:
        raise HTTPException(503, "На AI-сервере нет текстовых моделей. Добавьте модель в LM Studio и обновите список.")
    return candidate


def _json_schema(model: type[BaseModel]) -> dict:
    return {"type": "json_schema", "json_schema": {"name": model.__name__, "strict": True, "schema": model.model_json_schema()}}


def _parse_content(response: httpx.Response) -> dict:
    try:
        choice = response.json()["choices"][0]
        if choice.get("finish_reason") in ("length", "content_filter"):
            raise InvalidAIResponse("Ответ оборван или отклонён моделью")
        message = choice["message"]
        if message.get("refusal"):
            raise InvalidAIResponse("Модель отказалась сформировать карточку")
        content = message["content"]
        if not isinstance(content, str):
            raise InvalidAIResponse("Ожидается текстовый JSON")
        content = re.sub(r"^\s*<think>.*?</think>\s*", "", content, flags=re.S).strip()
        if content.startswith("```") and content.endswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.I)[:-3].strip()
        result = json.loads(content)
        if not isinstance(result, dict):
            raise InvalidAIResponse("Ожидается JSON-объект")
        return result
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        raise InvalidAIResponse("Ожидается полный JSON-объект в choices[0].message.content") from exc


def generate(connection: Connection, system: str, instruction: str, payload: dict,
             output_type: type[BaseModel], validate: Callable[[BaseModel], T]) -> T:
    model = select_model(connection, list_models(connection))
    messages = [
        {"role": "system", "content": system + "\n" + instruction},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    schema_prompt = "\nJSON Schema:\n" + json.dumps(output_type.model_json_schema(), ensure_ascii=False)
    formats = ["json_schema", "json_object", "text"] if connection.response_format == "auto" else [connection.response_format]
    format_index = 0
    with _client(connection) as client:
        for attempt in range(2):
            while True:
                mode = formats[format_index]
                request_messages = [dict(message) for message in messages]
                if mode != "json_schema":
                    request_messages[0]["content"] += schema_prompt
                body = {"model": model, "messages": request_messages, "stream": False, "max_tokens": connection.max_tokens}
                if mode != "text":
                    body["response_format"] = _json_schema(output_type) if mode == "json_schema" else {"type": "json_object"}
                response = _request(client, "POST", "chat/completions", json=body)
                format_error = response.status_code in (400, 422) and any(
                    token in response.text.lower() for token in ("response_format", "json_schema", "json_object", "structured output"))
                if format_error and format_index + 1 < len(formats):
                    format_index += 1
                    continue
                _check_status(response)
                break
            try:
                parsed = output_type.model_validate(_parse_content(response))
                return validate(parsed)
            except (ValidationError, InvalidAIResponse) as exc:
                if attempt == 0:
                    messages.append({"role": "user", "content": (
                        "Предыдущий ответ не прошёл проверку. Верни заново полный JSON по схеме. "
                        "Используй только точные цитаты входных сведений; неизвестные поля — []. "
                        "Если нужны вопросы, минимум три по РАЗНЫМ полям. Без markdown и пояснений."
                    )})
                    continue
                raise HTTPException(502, "AI дважды вернул некорректный ответ или сведения без источника. Карточка не изменена. Повторите запрос или выберите другую модель.") from exc
