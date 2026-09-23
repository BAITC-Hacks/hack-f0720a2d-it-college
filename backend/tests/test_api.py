from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

PREFIX = "/api/v1"


def create_task(client, **fields):
    payload = {
        "description": "Нужно автоматизировать приём заявок.", "title": "Заявки", **fields,
    }
    response = client.post(PREFIX + "/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def finalize(client, task):
    response = client.post(
        f"{PREFIX}/tasks/{task['id']}/evaluation",
        json={"confirmed": True, "expected_version": task["version"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_create_read_update_delete_draft(client):
    task = create_task(client)
    path = f"{PREFIX}/tasks/{task['id']}"
    assert task["status"] == "draft" and task["score"] is None
    assert client.get(path).json() == task
    assert client.get(PREFIX + "/tasks").json()["total"] == 0
    assert client.get(PREFIX + "/tasks?status=draft").json()["total"] == 1
    updated = client.patch(path, json={"expected_version": 1, "context": "Текущий процесс"})
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["title"] == "Заявки"
    stale = client.patch(path, json={"expected_version": 1, "title": "Устаревшее изменение"})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "version_conflict"
    assert client.delete(path).status_code == 204
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("payload", [
    {"description": "   "}, {"description": "Слишком коротко", "unknown": True},
    {"description": "Нормальное описание", "score": 100},
    {"description": "Нормальное описание", "status": "finalized"},
])
def test_reject_invalid_or_server_managed_create_fields(client, payload):
    assert client.post(PREFIX + "/tasks", json=payload).status_code == 422


@pytest.mark.parametrize("changes", [
    {"expected_version": 1, "context": None}, {"expected_version": 1},
    {"expected_version": 1, "score": 100}, {"title": "Без версии"},
])
def test_patch_validation(client, changes):
    task = create_task(client)
    assert client.patch(f"{PREFIX}/tasks/{task['id']}", json=changes).status_code == 422


def test_finalization_requires_confirmation_title_and_current_version(client):
    task = create_task(client, title="")
    path = f"{PREFIX}/tasks/{task['id']}"
    for confirmed in [False, "true", 1, None]:
        assert client.post(path + "/evaluation", json={
            "confirmed": confirmed, "expected_version": 1,
        }).status_code == 422
    assert client.post(path + "/evaluation", json={
        "confirmed": True, "expected_version": 1,
    }).json()["error"]["code"] == "title_required"
    updated = client.patch(path, json={"expected_version": 1, "title": "Подтверждённая задача"}).json()
    assert client.post(path + "/evaluation", json={
        "confirmed": True, "expected_version": 1,
    }).status_code == 409
    assert client.get(path + "/evaluation").status_code == 404
    assert finalize(client, updated)["score"] == 0


def test_evaluation_is_idempotent_and_freezes_snapshot(client, complete_card):
    task = create_task(client, **complete_card)
    path = f"{PREFIX}/tasks/{task['id']}"
    first = finalize(client, task)
    assert first["score"] == 100 and first["readiness"] == "priority"
    assert first["card_snapshot"] == complete_card
    assert first["missing_fields"] == []
    assert sum(item["points"] for item in first["criteria"]) == 100
    assert finalize(client, task) == first
    assert client.get(path + "/evaluation").json() == first
    final_task = client.get(path).json()
    assert final_task["status"] == "finalized" and final_task["finalized_at"] is not None
    assert client.patch(path, json={"expected_version": 1, "context": ""}).status_code == 409
    assert client.delete(path).status_code == 409
    assert client.get(path).json() == final_task


def test_catalog_ranking_filtering_pagination_and_low_score_visibility(client, complete_card):
    low = create_task(client, topic="Автоматизация")
    high = create_task(client, **complete_card)
    create_task(client, title="Ещё не опубликована")
    finalize(client, low)
    finalize(client, high)
    catalog = client.get(PREFIX + "/tasks").json()
    assert [item["id"] for item in catalog["items"]] == [high["id"], low["id"]]
    assert catalog["total"] == 2
    assert client.get(PREFIX + "/tasks?readiness=draft").json()["items"][0]["id"] == low["id"]
    assert client.get(PREFIX + "/tasks", params={"topic": "Автоматизация"}).json()["total"] == 2
    assert client.get(PREFIX + "/tasks", params={"topic": "' OR 1=1 --"}).json()["total"] == 0
    page = client.get(PREFIX + "/tasks?limit=1&offset=1").json()
    assert page["total"] == 2 and page["items"][0]["id"] == low["id"]
    assert client.get(PREFIX + "/tasks?limit=101").status_code == 422


def test_proposals_and_manual_selection_of_multiple_teams(client, proposal_payload):
    task = create_task(client)
    path = f"{PREFIX}/tasks/{task['id']}/proposals"
    assert client.post(path, json=proposal_payload).status_code == 409
    assert finalize(client, task)["score"] == 0
    proposals = []
    for number in range(3):
        response = client.post(path, json={**proposal_payload, "team_id": f"team-{number}"})
        assert response.status_code == 201
        proposal = response.json()
        assert proposal["status"] == "pending"
        assert proposal["decided_at"] is None
        assert client.get(f"{PREFIX}/proposals/{proposal['id']}").json() == proposal
        proposals.append(proposal)
    for proposal in proposals[:2]:
        decision = client.patch(f"{PREFIX}/proposals/{proposal['id']}/decision", json={
            "status": "accepted", "business_comment": "Приглашаем к работе",
        })
        assert decision.status_code == 200
        assert decision.json()["decided_at"] is not None
    assert client.patch(f"{PREFIX}/proposals/{proposals[2]['id']}/decision", json={
        "status": "rejected",
    }).status_code == 200
    assert client.get(path + "?status=accepted").json()["total"] == 2
    assert client.get(path + "?team_id=team-2").json()["items"][0]["status"] == "rejected"
    assert client.get(path + "?limit=1&offset=1").json()["total"] == 3


def test_proposal_validation(client, proposal_payload):
    task = create_task(client)
    finalize(client, task)
    path = f"{PREFIX}/tasks/{task['id']}/proposals"
    for changes in [{"prototype_url": "javascript:alert(1)"}, {"plan": ""}, {"status": "accepted"}]:
        assert client.post(path, json={**proposal_payload, **changes}).status_code == 422


def test_storage_survives_app_restart(settings, complete_card, proposal_payload):
    with TestClient(create_app(settings)) as first:
        task = create_task(first, **complete_card)
        evaluation = finalize(first, task)
        proposal = first.post(f"{PREFIX}/tasks/{task['id']}/proposals", json=proposal_payload).json()
    with TestClient(create_app(settings)) as second:
        assert second.get(f"{PREFIX}/tasks/{task['id']}").json()["score"] == 100
        assert finalize(second, task) == evaluation
        assert second.get(f"{PREFIX}/proposals/{proposal['id']}").json() == proposal


def test_unknown_resources_and_health(client):
    assert client.get("/health").json() == {"status": "ok", "ai_provider": "mock"}
    assert client.get(PREFIX + "/tasks/not-a-uuid").status_code == 422
    unknown = str(uuid4())
    for path in [f"/tasks/{unknown}", f"/tasks/{unknown}/evaluation", f"/tasks/{unknown}/proposals", f"/proposals/{unknown}"]:
        assert client.get(PREFIX + path).status_code == 404
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert PREFIX + "/ai/analyze" in schema.json()["paths"]


def test_mock_analysis_questions_and_user_answers_do_not_mutate_storage(client):
    request = {
        "description": "Нужно автоматизировать приём заявок.",
        "answers": [{"field": "users", "answer": "Диспетчеры мастерской"}],
    }
    response = client.post(PREFIX + "/ai/analyze", json=request)
    assert response.status_code == 200, response.text
    analysis = response.json()
    assert analysis["is_mock"] is True
    assert len(analysis["questions"]) >= 3
    assert analysis["suggested_card"]["users"] == "Диспетчеры мастерской"
    assert analysis["suggested_card"]["data"] == ""
    assert "users" not in analysis["missing_fields"]
    assert client.get(PREFIX + "/tasks?status=all").json()["total"] == 0


def test_mock_analysis_of_complete_card_and_invalid_answer(client, complete_card):
    card = {key: value for key, value in complete_card.items() if key not in {"description", "topic"}}
    response = client.post(PREFIX + "/ai/analyze", json={
        "description": complete_card["description"], "card": card,
    })
    assert response.status_code == 200
    assert response.json()["missing_fields"] == []
    assert len(response.json()["questions"]) >= 3
    assert client.post(PREFIX + "/ai/analyze", json={
        "description": complete_card["description"],
        "answers": [{"field": "title", "answer": "a" * 201}],
    }).status_code == 422
