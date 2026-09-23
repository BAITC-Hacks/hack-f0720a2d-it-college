"""Подготовленный пример README: точные баллы и все восемь шагов кейса."""

import json
from pathlib import Path

from app.modules.teams.models import Team
from app.modules.users.models import User


def test_readme_demo(client, db):
    demo = json.loads((Path(__file__).resolve().parents[1] / "docs/DEMO.json").read_text(encoding="utf-8"))
    db.add_all([Team(id=1, name="Команда 1", interests=[], skills=[], tech=[]),
                Team(id=2, name="Команда 2", interests=[], skills=[], tech=[])])
    db.flush()
    db.add_all([User(id=1, name="Алия", role="business"),
                User(id=2, name="Тимур", role="business"),
                User(id=3, name="Представитель 1", role="team", team_id=1),
                User(id=4, name="Представитель 2", role="team", team_id=2)])
    db.commit()
    business = {"X-User-Id": "1"}
    draft = client.post("/api/tasks/draft", headers=business, json=demo["draft"]).json()
    url = f"/api/tasks/{draft['id']}"
    assert draft["score"] == 0
    questions = client.post(url + "/questions", headers=business).json()
    assert len(questions["questions"]) >= 3
    weak = client.post(url + "/card", headers=business, json={"answers": {"need": ""}}).json()
    assert weak["score"] == 0 and weak["potential_score"] == 5
    assert client.post(url + "/confirm", headers=business).json()["score"] == 5
    full = client.patch(url, headers=business, json=demo["answers"]).json()
    assert full["score"] == 0 and full["potential_score"] == 100
    assert client.post(url + "/publish", headers=business).status_code == 409
    assert client.post(url + "/confirm", headers=business).json()["score"] == 100
    published = client.post(url + "/publish", headers=business).json()
    assert published["status"] == "published" and published["score"] == 100
    assert client.get("/api/catalog").json()[0]["id"] == draft["id"]
    proposals = []
    for user in (3, 4):
        response = client.post("/api/proposals", headers={"X-User-Id": str(user)},
                               json={**demo["proposal"], "task_id": draft["id"]})
        assert response.status_code == 201
        proposals.append(response.json()["id"])
    first = f"/api/proposals/{proposals[0]}"
    assert client.post(first + "/accept", headers={"X-User-Id": "2"}).status_code == 403
    assert client.post(first + "/accept", headers=business).json()["status"] == "accepted"
    assert client.post(f"/api/proposals/{proposals[1]}/reject", headers=business).json()["status"] == "rejected"
    progress = client.post(first + "/progress", headers={"X-User-Id": "3"}, json=demo["progress"]).json()["progress"]
    assert progress["points"] == 0 and progress["status"] == "submitted"
    progress = client.post(first + "/progress/confirm", headers=business).json()["progress"]
    assert progress["points"] == 10 and progress["status"] == "confirmed"
    assert client.post(first + "/progress/confirm", headers=business).status_code == 409
    assert client.get("/api/proposals", headers={"X-User-Id": "3"}).json()[0]["progress"]["points"] == 10
