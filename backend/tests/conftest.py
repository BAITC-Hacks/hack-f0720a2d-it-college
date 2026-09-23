import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings(database_path=tmp_path / "test.sqlite3", ai_provider="mock")


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def complete_card():
    return {
        "title": "Учёт заявок мастерской",
        "description": "Нужен сервис учёта заявок на ремонт оборудования.",
        "topic": "Автоматизация",
        "context": "Мастерская ведёт заявки в таблице, заявки иногда теряются.",
        "need": "Собрать заявки и статусы ремонта в одном месте.",
        "users": "Диспетчер и мастера ремонтной мастерской.",
        "data": "Обезличенный CSV с 100 примерами заявок и перечень статусов.",
        "constraints": "Две недели, веб-приложение, без доступа к персональным данным.",
        "expected_result": "Работающий прототип журнала заявок с фильтрацией.",
        "success_criteria": "Все 100 заявок импортируются; поиск по номеру занимает до 2 секунд.",
        "contact": "Демо-координатор, coordinator@example.com",
        "interaction_format": "Консультация дважды в неделю, обратная связь по демонстрации.",
    }


@pytest.fixture
def proposal_payload():
    return {
        "team_id": "team-1", "team_name": "IT College",
        "idea": "Разработать журнал заявок и поиск по номеру.",
        "plan": "Уточнить формат CSV, реализовать импорт, проверить поиск.",
        "timeframe": "Две недели", "prototype_url": "https://example.com/prototype",
    }
