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


def test_many_teams_can_propose_and_owner_can_select_several(client, db):
    db.add_all([User(id=1, name="Владелец", role="business"),
                User(id=2, name="Посторонний бизнес", role="business")])
    db.add_all([Team(id=i, name=f"Команда {i}", interests=[], skills=[], tech=[])
                for i in range(1, 13)])
    db.flush()
    db.add_all([User(id=100 + i, name=f"Представитель {i}", role="team", team_id=i)
                for i in range(1, 13)])
    db.add(Task(id=1, owner_id=1, raw_text="Слабая задача", status="published",
                score=0, level="draft", breakdown={}))
    db.commit()
    ids = []
    for team_id in range(1, 13):
        response = client.post("/api/proposals", headers={"X-User-Id": str(100 + team_id)}, json={
            "task_id": 1, "idea": "Идея самостоятельного решения",
            "plan": "Согласуем и проверим прототип решения", "deadline": "Две недели",
        })
        assert response.status_code == 201
        assert response.json()["status"] == "pending"
        ids.append(response.json()["id"])
    owner = {"X-User-Id": "1"}
    for decision in ("accept", "reject"):
        assert client.post(f"/api/proposals/{ids[0]}/{decision}", headers={"X-User-Id": "2"}).status_code == 403
        assert client.post(f"/api/proposals/{ids[0]}/{decision}", headers={"X-User-Id": "101"}).status_code == 403
    for proposal_id in ids[:2]:
        assert client.post(f"/api/proposals/{proposal_id}/accept", headers=owner).status_code == 200
    assert client.post(f"/api/proposals/{ids[2]}/reject", headers=owner).status_code == 200
    statuses = [proposal["status"] for proposal in client.get("/api/tasks/1/proposals", headers=owner).json()]
    assert statuses.count("accepted") == 2
    assert statuses.count("rejected") == 1
    assert statuses.count("pending") == 9
    assert client.get("/api/catalog?level=draft").json()[0]["proposals_count"] == 12
