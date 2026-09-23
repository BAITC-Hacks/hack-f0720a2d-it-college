"""Smoke-тест сортировки каталога и видимости низкого рейтинга."""

from app.modules.tasks.models import Task


def test_catalog_keeps_low_score_and_sorts(client, db):
    low = Task(
        owner_id=1,
        title="Неполная задача",
        raw_text="Краткое описание",
        context="Подтверждённый контекст длиной больше тридцати символов.",
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
    for field in ("need", "data", "expected_result", "success_criteria", "constraints", "users", "contact"):
        setattr(high, field, "Подтверждённое описание длиной больше тридцати символов.")
    db.add_all([low, high])
    db.commit()

    response = client.get("/api/catalog")
    assert response.status_code == 200
    tasks = response.json()
    assert [task["title"] for task in tasks] == ["Полная задача", "Неполная задача"]

    response = client.get("/api/catalog?level=draft")
    assert response.status_code == 200
    assert response.json()[0]["title"] == "Неполная задача"


def test_catalog_legacy_cache_does_not_change_actual_order_or_filter(client, db):
    from app.modules.rating.service import FIELD_WEIGHTS
    high = Task(owner_id=1, raw_text="Старая карточка", status="published", score=0, level="draft",
                **{field: "Подтверждённое подробное описание длиной более тридцати символов." for field in FIELD_WEIGHTS})
    db.add_all([high, Task(owner_id=1, raw_text="Другая карточка", status="published",
                          data="Подробно описанный источник данных для задачи.", score=20, level="draft")])
    db.commit()
    all_tasks = client.get("/api/catalog").json()
    assert all_tasks[0]["id"] == high.id and all_tasks[0]["score"] == 100
    filtered = client.get("/api/catalog?level=priority").json()
    assert [task["id"] for task in filtered] == [high.id]


def test_catalog_filters_topic_and_level_without_exposing_unpublished_drafts(client, db):
    db.add_all([
        Task(owner_id=1, title="Нужны уточнения", industry="Образование", raw_text="Описание",
             status="published", score=0, level="draft", breakdown={}),
        Task(owner_id=1, title="Иная отрасль", industry="Торговля", raw_text="Описание",
             status="published", score=0, level="draft", breakdown={}),
        Task(owner_id=1, title="Личный черновик", industry="Образование", raw_text="Описание",
             status="draft", score=0, level="draft", breakdown={}),
    ])
    db.commit()
    response = client.get("/api/catalog", params={"industry": "Образование", "level": "draft"})
    assert response.status_code == 200
    assert [task["title"] for task in response.json()] == ["Нужны уточнения"]
    assert response.json()[0]["status"] == "published"
    assert response.json()[0]["score"] == 0
    assert client.get("/api/catalog?level=unknown").status_code == 422
