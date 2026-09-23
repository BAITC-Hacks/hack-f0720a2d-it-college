"""Раздельные настройки фиксированного OpenAI и совместимых серверов."""

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modules.ai import compatible_provider, provider
from app.modules.ai.compatible_provider import Connection
from app.modules.ai.errors import AIServiceError
from app.modules.ai.models import AIConnection
from app.modules.ai.schemas import (
    ConnectionInput, ConnectionRead, INHERIT_SERVER_KEY, ModelsRead, OPENAI_BASE_URL,
)


def _secret(value) -> str:
    return value.get_secret_value() if value is not None else ""


def default_connection() -> Connection:
    settings = get_settings()
    selected = settings.ai_provider
    if selected == "auto":
        selected = "openai" if _secret(settings.openai_api_key) else "stub"
    if selected == "openai":
        return Connection(OPENAI_BASE_URL, settings.openai_model, _secret(settings.openai_api_key),
                          "json_schema", settings.ai_timeout_seconds, settings.openai_max_output_tokens, "openai")
    if selected == "compatible":
        try:
            config = ConnectionInput(provider="compatible", base_url=settings.ai_base_url,
                                     model=settings.ai_model, response_format=settings.ai_response_format)
        except ValidationError:
            raise AIServiceError(503, "Проверьте AI_BASE_URL и AI_RESPONSE_FORMAT на сервере.") from None
        return Connection(config.base_url, config.model, _secret(settings.ai_api_key), config.response_format,
                          settings.ai_timeout, settings.ai_max_tokens, "compatible")
    return Connection("", provider="stub")


def get_connection(db: Session, user_id: int) -> Connection:
    stored = db.get(AIConnection, user_id)
    if stored is None:
        return default_connection()
    settings = get_settings()
    if stored.provider == "stub":
        return Connection("", provider="stub")
    if stored.provider == "openai":
        key = _secret(settings.openai_api_key) if stored.api_key == INHERIT_SERVER_KEY else stored.api_key
        return Connection(OPENAI_BASE_URL, stored.model or settings.openai_model, key, "json_schema",
                          settings.ai_timeout_seconds, settings.openai_max_output_tokens, "openai")
    try:
        config = ConnectionInput(provider="compatible", base_url=stored.base_url,
                                 model=stored.model, response_format=stored.response_format)
    except ValidationError:
        raise AIServiceError(503, "Проверьте сохранённый адрес AI-сервера в настройках AI.") from None
    # Даже повреждённая старая запись не должна передать ключ OpenAI произвольному адресу.
    key = "" if stored.api_key == INHERIT_SERVER_KEY else stored.api_key
    return Connection(config.base_url, config.model, key, config.response_format,
                      settings.ai_timeout, settings.ai_max_tokens, "compatible")


def _public(connection: Connection, choice: str) -> ConnectionRead:
    return ConnectionRead(provider=choice, effective_provider=connection.provider, base_url=connection.base_url,
                          model=connection.model, has_api_key=bool(connection.api_key),
                          response_format=connection.response_format)


def read_settings(db: Session, user_id: int) -> ConnectionRead:
    row = db.get(AIConnection, user_id)
    return _public(get_connection(db, user_id), row.provider if row else "auto")


def _configured(db: Session, user_id: int, payload: ConnectionInput) -> tuple[Connection, str]:
    if payload.provider == "auto":
        return default_connection(), ""
    if payload.provider == "stub":
        return Connection("", provider="stub"), ""
    settings = get_settings()
    row = db.get(AIConnection, user_id)
    current = get_connection(db, user_id)
    key = ""
    if current.provider == payload.provider and current.base_url == payload.base_url:
        key = row.api_key if row else (INHERIT_SERVER_KEY if payload.provider == "openai" else current.api_key)
    elif payload.provider == "openai":
        key = INHERIT_SERVER_KEY
    if payload.clear_api_key:
        key = ""
    if payload.api_key is not None and payload.api_key.get_secret_value().strip():
        key = payload.api_key.get_secret_value().strip()
    if payload.provider == "openai":
        actual_key = _secret(settings.openai_api_key) if key == INHERIT_SERVER_KEY else key
        connection = Connection(OPENAI_BASE_URL, payload.model or settings.openai_model, actual_key,
                                "json_schema", settings.ai_timeout_seconds, settings.openai_max_output_tokens, "openai")
    else:
        connection = Connection(payload.base_url, payload.model, key, payload.response_format,
                                settings.ai_timeout, settings.ai_max_tokens, "compatible")
    return connection, key


def save_settings(db: Session, user_id: int, payload: ConnectionInput) -> ConnectionRead:
    connection, stored_key = _configured(db, user_id, payload)
    row = db.get(AIConnection, user_id)
    if payload.provider == "auto":
        if row is not None:
            db.delete(row)
    else:
        row = row or AIConnection(user_id=user_id)
        for name in ("provider", "base_url", "model", "response_format"):
            setattr(row, name, getattr(connection, name))
        row.api_key = stored_key
        db.add(row)
    db.commit()
    return _public(connection, payload.provider)


def available_models(db: Session, user_id: int, payload: ConnectionInput | None = None) -> ModelsRead:
    connection = _configured(db, user_id, payload)[0] if payload else get_connection(db, user_id)
    if connection.provider == "stub":
        return ModelsRead(models=[], selected_model=None)
    models = (provider.list_models(connection.api_key, connection.timeout)
              if connection.provider == "openai" else compatible_provider.list_models(connection))
    selected = connection.model if any(model.id == connection.model for model in models) else None
    if not connection.model:
        selected = next((model.id for model in models if model.chat_candidate), None)
    return ModelsRead(models=models, selected_model=selected)
