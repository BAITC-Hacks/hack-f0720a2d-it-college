"""Проверки минимального результата этапа: только выбор бизнеса и одно начисление."""

import pytest
from sqlalchemy import create_engine, inspect

from app.db import Base
from app.modules.proposals.models import ProposalProgress
from app.modules.tasks.models import Task
from app.modules.teams.models import Team
from app.modules.users.models import User


@pytest.fixture
def progress_actors(client, db):
    db.add_all([
        Team(id=1, name="Команда результата", interests=[], skills=[], tech=[]),
        Team(id=2, name="Другая команда", interests=[], skills=[], tech=[]),
    ])
    db.flush()
    db.add_all([
        User(id=1, name="Владелец", role="business"),
        User(id=2, name="Посторонний бизнес", role="business"),
        User(id=3, name="Исполнитель", role="team", team_id=1),
        User(id=4, name="Посторонняя команда", role="team", team_id=2),
    ])
    db.add(Task(id=1, owner_id=1, title="Задача", raw_text="Описание задачи",
                status="published", score=0, level="draft", breakdown={}))
    db.commit()
    headers = {i: {"X-User-Id": str(i)} for i in range(1, 5)}
    response = client.post("/api/proposals", headers=headers[3], json={
        "task_id": 1, "idea": "Предлагаем реализовать прототип решения",
        "plan": "Уточним требования и проверим рабочий прототип", "deadline": "2 недели",
    })
    assert response.status_code == 201
    return headers, response.json()["id"]


def result_payload():
    return {"description": "Собран рабочий прототип формы, проверены три сценария ввода.",
            "link": "https://example.com/working-prototype"}


def test_progress_requires_selection_and_manual_confirmation_once(client, progress_actors):
    headers, proposal_id = progress_actors
    url = f"/api/proposals/{proposal_id}"
    assert client.post(url + "/progress", headers=headers[3], json=result_payload()).status_code == 409
    selected = client.post(url + "/accept", headers=headers[1]).json()
    assert selected["progress"] is None
    assert client.post(url + "/progress/confirm", headers=headers[1]).status_code == 409

    submitted = client.post(url + "/progress", headers=headers[3], json=result_payload())
    assert submitted.status_code == 200
    progress = submitted.json()["progress"]
    assert progress["status"] == "submitted"
    assert progress["points"] == 0
    assert progress["confirmed_at"] is None
    assert progress["confirmed_by"] is None

    changed = result_payload() | {"description": "Прототип дополнен: проверены четыре сценария ввода данных."}
    revised = client.post(url + "/progress", headers=headers[3], json=changed).json()["progress"]
    assert revised["id"] == progress["id"]
    assert revised["description"] == changed["description"]
    assert revised["points"] == 0

    confirmed = client.post(url + "/progress/confirm", headers=headers[1])
    assert confirmed.status_code == 200
    progress = confirmed.json()["progress"]
    assert progress["status"] == "confirmed"
    assert progress["points"] == 10
    assert progress["confirmed_by"] == 1
    assert progress["confirmed_at"]
    assert client.get("/api/proposals", headers=headers[3]).json()[0]["progress"] == progress
    assert client.post(url + "/progress/confirm", headers=headers[1]).status_code == 409
    assert client.post(url + "/progress", headers=headers[3], json=result_payload()).status_code == 409

    # Ручная отмена выбора не стирает фактический результат и не даёт повторить награду.
    assert client.post(url + "/reopen", headers=headers[1]).status_code == 200
    assert client.post(url + "/progress/confirm", headers=headers[1]).status_code == 409
    assert client.post(url + "/accept", headers=headers[1]).status_code == 200
    assert client.post(url + "/progress/confirm", headers=headers[1]).status_code == 409
    assert client.get("/api/proposals", headers=headers[3]).json()[0]["progress"] == progress


def test_progress_is_scoped_to_selected_team_and_owner(client, progress_actors):
    headers, proposal_id = progress_actors
    url = f"/api/proposals/{proposal_id}"
    assert client.post(url + "/accept", headers=headers[1]).status_code == 200
    for actor in (1, 2, 4):
        assert client.post(url + "/progress", headers=headers[actor], json=result_payload()).status_code == 403
    assert client.post(url + "/progress", json=result_payload()).status_code == 401
    assert client.post(url + "/progress", headers=headers[3], json=result_payload()).status_code == 200
    for actor in (2, 3, 4):
        assert client.post(url + "/progress/confirm", headers=headers[actor]).status_code == 403
    assert client.post(url + "/progress/confirm").status_code == 401
    assert client.get("/api/proposals", headers=headers[2]).json() == []
    assert client.get("/api/proposals", headers=headers[4]).json() == []
    assert client.get("/api/proposals", headers=headers[3]).json()[0]["progress"]["points"] == 0
    assert client.post("/api/proposals/999/progress", headers=headers[3], json=result_payload()).status_code == 404


@pytest.mark.parametrize("changes", [
    {"description": " " * 40}, {"description": "Слишком коротко"},
    {"link": "javascript:alert(1)"}, {"points": 999}, {"confirmed_by": 1},
])
def test_progress_validates_input_and_forbids_client_points(client, progress_actors, changes):
    headers, proposal_id = progress_actors
    url = f"/api/proposals/{proposal_id}"
    assert client.post(url + "/accept", headers=headers[1]).status_code == 200
    response = client.post(url + "/progress", headers=headers[3], json=result_payload() | changes)
    assert response.status_code == 422
    assert response.json()["detail"] == "Некорректные входные данные"
    assert client.get("/api/proposals", headers=headers[3]).json()[0]["progress"] is None


def test_unselected_team_cannot_confirm_previously_submitted_progress(client, progress_actors):
    headers, proposal_id = progress_actors
    url = f"/api/proposals/{proposal_id}"
    client.post(url + "/accept", headers=headers[1])
    client.post(url + "/progress", headers=headers[3], json=result_payload())
    client.post(url + "/reopen", headers=headers[1])
    assert client.post(url + "/progress/confirm", headers=headers[1]).status_code == 409
    client.post(url + "/reject", headers=headers[1])
    assert client.post(url + "/progress", headers=headers[3], json=result_payload()).status_code == 409
    assert client.post(url + "/progress/confirm", headers=headers[1]).status_code == 409
    assert client.get("/api/proposals", headers=headers[3]).json()[0]["progress"]["points"] == 0


def test_progress_adds_a_table_without_altering_existing_columns():
    # Отдельная пустая in-memory БД имитирует схему до добавления результата этапа.
    engine = create_engine("sqlite://")
    try:
        existing = [table for table in Base.metadata.sorted_tables if table is not ProposalProgress.__table__]
        Base.metadata.create_all(engine, tables=existing)
        before = {table.name: inspect(engine).get_columns(table.name) for table in existing}
        Base.metadata.create_all(engine)
        after = {table.name: inspect(engine).get_columns(table.name) for table in existing}
        assert {name: [column["name"] for column in columns] for name, columns in before.items()} == {
            name: [column["name"] for column in columns] for name, columns in after.items()
        }
        assert "proposal_progress" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
