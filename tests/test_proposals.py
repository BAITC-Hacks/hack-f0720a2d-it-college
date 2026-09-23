"""Smoke-тест самостоятельного отклика и ручного решения владельца."""

from app.modules.tasks.models import Task
from app.modules.teams.models import Team
from app.modules.users.models import User


def test_proposal_manual_accept(client, db):
    team = Team(id=1, name="Команда", interests=[], skills=[], tech=["Python"])
    db.add(team)
    db.flush()
    db.add_all(
        [
            User(id=1, name="Бизнес", role="business"),
            User(id=2, name="Участник", role="team", team_id=1),
        ]
    )
    task = Task(
        id=1,
        owner_id=1,
        title="Открытая задача",
        raw_text="Описание опубликованной задачи",
        status="published",
        score=20,
        level="draft",
        breakdown={},
    )
    db.add(task)
    db.commit()

    response = client.post(
        "/api/proposals",
        headers={"X-User-Id": "2"},
        json={
            "task_id": 1,
            "idea": "Предлагаем собрать простой прототип решения задачи.",
            "plan": "Уточним требования, реализуем и проверим сценарий.",
            "deadline": "две недели",
            "link": "https://example.com/prototype",
        },
    )
    assert response.status_code == 201
    proposal_id = response.json()["id"]
    assert response.json()["status"] == "pending"

    response = client.get("/api/tasks/1/proposals", headers={"X-User-Id": "1"})
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.post(
        f"/api/proposals/{proposal_id}/accept",
        headers={"X-User-Id": "1"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
