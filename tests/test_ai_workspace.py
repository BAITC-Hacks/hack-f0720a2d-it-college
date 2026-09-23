"""Интеграция AI, видимость черновиков, подтверждение дополнений и прогресс команд."""

import httpx
import json
import pytest

from app.modules.users.models import User
from app.modules.teams.models import Team
from app.modules.ai.models import AIAnalysis
from app.modules.tasks.models import TaskRevision
from app.modules.tasks.models import Task, utc_now
from app.modules.ai import service as ai_service
from app.modules.ai.schemas import CARD_FIELDS


@pytest.fixture
def actors(db):
    db.add_all([Team(id=1, name="Первая", interests=[], skills=[], tech=[]), Team(id=2, name="Вторая", interests=[], skills=[], tech=[])])
    db.flush()
    db.add_all([User(id=1, name="Бизнес", role="business"), User(id=2, name="Другой", role="business"),
                User(id=3, name="Команда", role="team", team_id=1), User(id=4, name="Другая команда", role="team", team_id=2)])
    db.commit()
    return {i: {"X-User-Id": str(i)} for i in range(1, 5)}


def draft(client, actors):
    return client.post("/api/tasks/draft", headers=actors[1], json={"raw_text": "Исходное описание бизнес-задачи для анализа", "title": "Карточка"}).json()["id"]


def publish(client, actors, task_id):
    assert client.post(f"/api/tasks/{task_id}/confirm", headers=actors[1]).status_code == 200
    assert client.post(f"/api/tasks/{task_id}/publish", headers=actors[1]).status_code == 200


def test_drafts_private_published_public(client, actors):
    url = f"/api/tasks/{draft(client, actors)}"
    assert client.get(url).status_code == 404
    assert client.get(url, headers=actors[2]).status_code == 404
    assert client.get(url, headers=actors[3]).status_code == 404
    assert client.get(url, headers=actors[1]).status_code == 200
    publish(client, actors, int(url.rsplit("/", 1)[1]))
    assert client.get(url).status_code == 200


def test_unknown_answer_is_422_without_provider_request(client, actors, fake_ai):
    url = f"/api/tasks/{draft(client, actors)}/card"
    response = client.post(url, headers=actors[1], json={"answers": {"unexpected": "value"}})
    assert response.status_code == 422
    assert not fake_ai["requests"]
    assert client.post(url, headers=actors[1], json={"answers": {"title": "x" * 241}}).status_code == 422
    assert not fake_ai["requests"]


def test_build_preserves_previously_extracted_facts(client, actors, fake_ai):
    url = f"/api/tasks/{draft(client, actors)}"
    assert client.post(url + "/questions", headers=actors[1]).status_code == 200
    fake_ai["reply"] = lambda request: httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(dict.fromkeys(CARD_FIELDS, []))}, "finish_reason": "stop"}]}) if request.method == "POST" else None
    built = client.post(url + "/card", headers=actors[1], json={"answers": {}})
    assert built.status_code == 200
    assert built.json()["context"] == "Исходное описание бизнес-задачи для анализа"


def test_invalid_secret_is_not_echoed(client, actors):
    response = client.put("/api/ai/settings", headers=actors[1], json={"api_key": "sensitive-secret\nnewline"})
    assert response.status_code == 422
    assert "sensitive-secret" not in response.text


def test_analysis_cached_and_invalidated_on_edit(client, db, actors, fake_ai):
    task_id = draft(client, actors)
    url = f"/api/tasks/{task_id}"
    assert client.post(url + "/questions", headers=actors[1]).status_code == 200
    calls = len(fake_ai["requests"])
    assert client.post(url + "/questions", headers=actors[1]).status_code == 200
    assert len(fake_ai["requests"]) == calls
    client.patch(url, headers=actors[1], json={"data": "Есть выгрузка"})
    assert client.post(url + "/questions", headers=actors[1]).status_code == 200
    assert len(fake_ai["requests"]) > calls
    assert db.get(AIAnalysis, task_id)
    assert client.delete(url, headers=actors[1]).status_code == 204
    assert db.get(AIAnalysis, task_id) is None


def test_ai_failure_does_not_mutate_card(client, actors, fake_ai):
    url = f"/api/tasks/{draft(client, actors)}"
    before = client.get(url, headers=actors[1]).json()
    fake_ai["reply"] = lambda request: httpx.Response(200, json={"choices": []}) if request.method == "POST" else None
    response = client.post(url + "/card", headers=actors[1], json={"answers": {"data": "Таблица"}})
    assert response.status_code == 502
    assert client.get(url, headers=actors[1]).json() == before


def test_concurrent_edit_is_not_overwritten_by_slow_ai(client, db, actors, monkeypatch):
    task_id = draft(client, actors)
    url = f"/api/tasks/{task_id}"
    def concurrent_change(*args):
        task = db.get(Task, task_id)
        task.context = "Более новое ручное изменение"
        task.updated_at = utc_now()
        db.commit()
        return {"context": "Устаревший ответ модели"}
    monkeypatch.setattr(ai_service, "build_card_for_task", concurrent_change)
    response = client.post(url + "/card", headers=actors[1], json={"answers": {}})
    assert response.status_code == 409
    assert client.get(url, headers=actors[1]).json()["context"] == "Более новое ручное изменение"


def test_card_fields_have_consistent_input_limits(client, actors, fake_ai):
    url = f"/api/tasks/{draft(client, actors)}"
    assert client.patch(url, headers=actors[1], json={"data": "x" * 10001}).status_code == 422
    assert client.post(url + "/card", headers=actors[1], json={"answers": {"data": "x" * 10001}}).status_code == 422
    assert not fake_ai["requests"]


def test_settings_keys_are_private_and_not_reused_for_new_host(client, actors, fake_ai):
    payload = {"base_url": "https://llm.example.org/v1", "api_key": "test-secret", "model": "demo-model"}
    response = client.put("/api/ai/settings", headers=actors[1], json=payload)
    assert response.status_code == 200
    assert response.json()["has_api_key"] is True
    assert "test-secret" not in response.text
    assert client.get("/api/ai/settings", headers=actors[2]).json()["base_url"] != payload["base_url"]
    assert client.get("/api/ai/settings", headers=actors[3]).status_code == 403
    assert client.get("/api/ai/settings").status_code == 401
    assert client.get("/api/ai/models", headers=actors[1]).status_code == 200
    assert fake_ai["requests"][-1].headers["authorization"] == "Bearer test-secret"
    assert client.post("/api/ai/models", headers=actors[1], json={"base_url": "https://other.example.org/v1"}).status_code == 200
    assert "authorization" not in fake_ai["requests"][-1].headers
    assert client.put("/api/ai/settings", headers=actors[1], json={"base_url": payload["base_url"], "clear_api_key": True}).json()["has_api_key"] is False


def test_published_edits_need_confirmation_and_keep_old_catalog(client, db, actors):
    task_id = draft(client, actors)
    url = f"/api/tasks/{task_id}"
    publish(client, actors, task_id)
    before = client.get(url).json()
    changed = client.patch(url, headers=actors[1], json={"data": "Подробное описание доступных материалов для команды"}).json()
    assert changed["has_pending_changes"] and changed["potential_score"] > before["score"]
    assert changed["score"] == before["score"]
    assert client.get(url).json()["data"] is None
    assert client.get("/api/catalog").json()[0]["score"] == before["score"]
    assert client.get(url, headers=actors[1]).json()["data"] == changed["data"]
    assert client.post(url + "/confirm", headers=actors[2]).status_code == 403
    confirmed = client.post(url + "/confirm", headers=actors[1]).json()
    assert confirmed["status"] == "published"
    assert client.get(url).json()["score"] == changed["potential_score"]
    assert db.get(TaskRevision, task_id) is None
    assert client.post(url + "/confirm", headers=actors[1]).json()["score"] == confirmed["score"]


def test_progress_only_after_manual_acceptance_and_confirmation(client, actors):
    task_id = draft(client, actors)
    publish(client, actors, task_id)
    proposal = client.post("/api/proposals", headers=actors[3], json={"task_id": task_id, "idea": "Наша идея решения задачи", "plan": "Наш подробный план работы", "deadline": "2 недели"}).json()
    url = f"/api/proposals/{proposal['id']}"
    evidence = {"summary": "Собрали прототип и проверили сценарий на тестовой выборке", "link": "https://example.com/result"}
    assert client.post(url + "/progress", headers=actors[3], json=evidence).status_code == 409
    assert client.post(url + "/accept", headers=actors[1]).status_code == 200
    assert client.post(url + "/progress", headers=actors[4], json=evidence).status_code == 403
    result = client.post(url + "/progress", headers=actors[3], json=evidence).json()
    assert result["progress"]["points"] == 0
    assert client.post(url + "/progress/confirm", headers=actors[2]).status_code == 403
    assert client.post(url + "/progress/confirm", headers=actors[3]).status_code == 403
    assert client.post(url + "/progress/reject", headers=actors[1]).json()["progress"] is None
    assert client.post(url + "/progress", headers=actors[3], json=evidence).status_code == 200
    confirmed = client.post(url + "/progress/confirm", headers=actors[1]).json()
    assert confirmed["progress"]["points"] == 10
    assert confirmed["progress"]["confirmed_at"]
    assert client.post(url + "/progress/confirm", headers=actors[1]).status_code == 409
    assert client.post(url + "/progress", headers=actors[3], json=evidence).status_code == 409
    assert client.get("/api/proposals", headers=actors[3]).json()[0]["progress"]["points"] == 10
    assert client.delete(f"/api/tasks/{task_id}", headers=actors[1]).status_code == 204
