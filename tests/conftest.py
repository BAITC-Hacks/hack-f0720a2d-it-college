"""Общая изолированная SQLite-база и HTTP-клиент для smoke-тестов."""

import pytest
import httpx
import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db, load_models
from app.main import app


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch):
    """Сетевой контракт тестируется через HTTP transport; реальные серверы не вызываются."""
    from app.modules.ai import provider
    from app.modules.ai.schemas import CARD_FIELDS
    state = {"requests": [], "reply": None, "models": ["demo-model"]}

    def handler(request):
        state["requests"].append(request)
        if state["reply"]:
            custom = state["reply"](request)
            if custom is not None:
                return custom
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": name} for name in state["models"]]})
        body = json.loads(request.content)
        data = json.loads(body["messages"][1]["content"])
        fields = {key: [] for key in CARD_FIELDS}
        fields["context"] = [data["raw_text"]]
        for key, value in {**data.get("known_fields", {}), **data.get("answers", {})}.items():
            if value:
                fields[key] = [value]
        if "answers" not in data:
            result = {"card": fields, "missing_fields": [key for key, value in fields.items() if not value],
                      "questions": [{"field": key, "text": text} for key, text in (
                          ("need", "Какую потребность нужно решить?"),
                          ("data", "Какие материалы доступны команде?"),
                          ("success_criteria", "Как будет проверяться успешность результата?"))]}
        else:
            result = fields
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(result)}, "finish_reason": "stop"}]})

    def factory(connection, **kwargs):
        return httpx.Client(base_url=connection.base_url.rstrip("/") + "/", transport=httpx.MockTransport(handler),
                            headers={"Authorization": "Bearer " + connection.api_key} if connection.api_key else {})
    monkeypatch.setattr(provider, "_client", factory)
    return state


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    load_models()
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db: Session):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.clear()
