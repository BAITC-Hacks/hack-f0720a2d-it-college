"""Необязательный HTTP-клиент Responses API; ключ остаётся только на сервере."""

from __future__ import annotations

import json

import httpx

from app.modules.ai.prompts import RETRY_PROMPT, SYSTEM_PROMPT
from app.modules.ai.schemas import BuildCardInput, CardFields

RESPONSES_URL = "https://api.openai.com/v1/responses"
REQUEST_TIMEOUT_SECONDS = 8.0
MAX_OUTPUT_CHARACTERS = 110_000


def request_card(payload: BuildCardInput, *, api_key: str, model: str, retry: bool) -> str:
    """Возвращает сырой JSON, который service обязан проверить перед использованием."""
    schema = CardFields.model_json_schema()
    # Strict Structured Outputs требует все ключи; неизвестные значения — null.
    schema["required"] = list(schema["properties"])
    for field_schema in schema["properties"].values():
        field_schema.pop("default", None)
    instructions = SYSTEM_PROMPT + ("\n\n" + RETRY_PROMPT if retry else "")
    response = httpx.post(
        RESPONSES_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "instructions": instructions,
            "input": json.dumps(payload.model_dump(), ensure_ascii=False),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "task_card",
                    "strict": True,
                    "schema": schema,
                }
            },
            "max_output_tokens": 6_000,
            "store": False,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict) or body.get("status") != "completed":
        raise ValueError("AI не завершил формирование ответа")
    output = body.get("output")
    if not isinstance(output, list):
        raise ValueError("AI вернул ответ без содержимого")
    parts = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            raise ValueError("Некорректная структура AI-ответа")
        for part in content:
            if not isinstance(part, dict) or part.get("type") == "refusal":
                raise ValueError("AI не смог обработать описание")
            if part.get("type") == "output_text":
                if not isinstance(part.get("text"), str):
                    raise ValueError("AI вернул не текст")
                parts.append(part["text"])
    text = "".join(parts)
    if not text or len(text) > MAX_OUTPUT_CHARACTERS:
        raise ValueError("AI вернул пустой или слишком большой ответ")
    return text
