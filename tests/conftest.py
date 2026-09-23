"""Общая изолированная SQLite-база и HTTP-клиент для smoke-тестов."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db, load_models
from app.main import app


@pytest.fixture(autouse=True)
def no_external_ai(monkeypatch):
    """Обычный pytest не расходует ключ разработчика из .env."""
    from app.config import Settings
    from app.modules.ai import service
    monkeypatch.setattr(service, "get_settings", lambda: Settings(openai_api_key=None))


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
