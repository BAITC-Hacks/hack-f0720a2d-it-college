"""Проверки личных кабинетов, доступа и ручных решений для рабочего интерфейса."""
import pytest
from app.modules.teams.models import Team
from app.modules.users.models import User


@pytest.fixture
def actors(db):
    db.add_all([Team(id=1, name="Одна", interests=[], skills=[], tech=[]),
                Team(id=2, name="Другая", interests=[], skills=[], tech=[])])
    db.flush()
    db.add_all([User(id=1, name="Владелец", role="business"),
                User(id=2, name="Другой владелец", role="business"),
                User(id=3, name="Команда 1", role="team", team_id=1),
                User(id=4, name="Команда 2", role="team", team_id=2)])
    db.commit()
    return {i: {"X-User-Id": str(i)} for i in range(1, 5)}


def publish(client, headers):
    response = client.post("/api/tasks/draft", headers=headers,
                           json={"title": "Тест", "raw_text": "Описание задачи"})
    task_id = response.json()["id"]
    assert client.post(f"/api/tasks/{task_id}/confirm", headers=headers).status_code == 200
    assert client.post(f"/api/tasks/{task_id}/publish", headers=headers).status_code == 200
    return task_id


def proposal_payload(task_id, **changes):
    return dict(task_id=task_id, idea="Идея решения бизнес-задачи",
                plan="Последовательный план нашей работы", deadline="2 недели",
                link="https://example.com/demo", **changes)


def test_lists_are_scoped_and_decisions_are_manual(client, actors):
    task_id = publish(client, actors[1])
    other_task = publish(client, actors[2])
    assert [t["id"] for t in client.get("/api/tasks", headers=actors[1]).json()] == [task_id]
    assert [t["id"] for t in client.get("/api/tasks", headers=actors[2]).json()] == [other_task]
    assert client.get("/api/tasks", headers=actors[3]).status_code == 403
    assert client.get("/api/tasks").status_code == 401
    p1 = client.post("/api/proposals", headers=actors[3], json=proposal_payload(task_id)).json()
    p2 = client.post("/api/proposals", headers=actors[4], json=proposal_payload(task_id)).json()
    assert p1["status"] == p2["status"] == "pending"
    assert len(client.get("/api/proposals", headers=actors[1]).json()) == 2
    assert client.get("/api/proposals", headers=actors[2]).json() == []
    assert [p["id"] for p in client.get("/api/proposals", headers=actors[3]).json()] == [p1["id"]]
    assert client.get("/api/proposals").status_code == 401
    assert client.post(f"/api/proposals/{p1['id']}/accept", headers=actors[2]).status_code == 403
    assert client.post(f"/api/proposals/{p1['id']}/accept", headers=actors[3]).status_code == 403
    assert client.post(f"/api/proposals/{p1['id']}/accept", headers=actors[1]).json()["status"] == "accepted"
    assert client.get("/api/proposals", headers=actors[4]).json()[0]["status"] == "pending"
    assert client.post(f"/api/proposals/{p1['id']}/reopen", headers=actors[2]).status_code == 403
    assert client.post(f"/api/proposals/{p1['id']}/reopen", headers=actors[1]).json()["status"] == "pending"
    assert client.post(f"/api/proposals/{p1['id']}/reject", headers=actors[1]).json()["status"] == "rejected"
    assert client.post(f"/api/proposals/{p2['id']}/accept", headers=actors[1]).status_code == 200
    catalog_task = next(t for t in client.get("/api/catalog").json() if t["id"] == task_id)
    assert catalog_task["score"] == 0
    assert catalog_task["proposals_count"] == 2
    assert client.post("/api/proposals", headers=actors[3], json=proposal_payload(task_id)).status_code == 409


@pytest.mark.parametrize("field,value", [("idea", "          "), ("plan", "   "), ("link", "javascript:alert(1)")])
def test_proposal_invalid_fields_are_422(client, actors, field, value):
    task_id = publish(client, actors[1])
    payload = proposal_payload(task_id)
    payload[field] = value
    response = client.post("/api/proposals", headers=actors[3], json=payload)
    assert response.status_code == 422
    assert response.json()["detail"] == "Некорректные входные данные"


def test_edited_card_requires_confirmation_again(client, actors):
    task = client.post("/api/tasks/draft", headers=actors[1], json={"raw_text": "Начальное описание"}).json()
    url = f"/api/tasks/{task['id']}"
    assert client.post(url + "/publish", headers=actors[1]).status_code == 409
    assert client.post(url + "/confirm", headers=actors[1]).status_code == 200
    response = client.patch(url, headers=actors[1], json={"context": "Новый контекст, содержащий более тридцати символов."})
    assert response.json()["status"] == "draft"
    assert response.json()["score"] == 0
    assert response.json()["potential_score"] == 10
    assert client.post(url + "/publish", headers=actors[1]).status_code == 409
    assert client.post(url + "/confirm", headers=actors[1]).json()["score"] == 10
