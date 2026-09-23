"""Smoke-тест сортировки каталога и видимости низкого рейтинга."""

from app.modules.tasks.models import Task


def test_catalog_keeps_low_score_and_sorts(client, db):
    low = Task(
        owner_id=1,
        title="Неполная задача",
        raw_text="Краткое описание",
        status="published",
        score=10,
        level="draft",
        breakdown={},
    )
    high = Task(
        owner_id=1,
        title="Полная задача",
        raw_text="Подробное описание",
        status="published",
        score=90,
        level="priority",
        breakdown={},
    )
    db.add_all([low, high])
    db.commit()

    response = client.get("/api/catalog")
    assert response.status_code == 200
    tasks = response.json()
    assert [task["title"] for task in tasks] == ["Полная задача", "Неполная задача"]

    response = client.get("/api/catalog?level=draft")
    assert response.status_code == 200
    assert response.json()[0]["title"] == "Неполная задача"
