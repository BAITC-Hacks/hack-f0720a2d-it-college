"""Совместимость данных и правил после объединения AI-версии с main."""

import pytest
import hashlib
import json
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.modules.proposals.models import Proposal, ProposalMilestone, utc_now
from app.modules.tasks import service as tasks_service
from app.modules.tasks.schemas import TaskPatch
from app.modules.teams.models import Team
from app.modules.users.models import User
from app.modules.ai import service as ai_service
from app.modules.ai.models import AIAnalysis


@pytest.fixture
def merged_workspace(client, db):
    db.add(Team(id=1, name="Команда", interests=[], skills=[], tech=[]))
    db.flush()
    db.add_all([User(id=1, name="Владелец", role="business"),
                User(id=2, name="Команда", role="team", team_id=1)])
    db.commit()
    owner, team = {"X-User-Id": "1"}, {"X-User-Id": "2"}
    task = client.post("/api/tasks/draft", headers=owner, json={"raw_text": "Описание задачи для студенческой команды."}).json()
    url = f"/api/tasks/{task['id']}"
    client.post(url + "/confirm", headers=owner)
    client.post(url + "/publish", headers=owner)
    proposal = client.post("/api/proposals", headers=team, json={"task_id": task["id"],
        "idea": "Создадим рабочий прототип", "plan": "Проверим данные и подготовим решение", "deadline": "2 недели"}).json()
    client.post(f"/api/proposals/{proposal['id']}/accept", headers=owner)
    return url, proposal["id"], owner, team


@pytest.mark.parametrize("confirmed", [False, True])
def test_existing_local_milestone_survives_merge_and_cannot_earn_twice(client, db, merged_workspace, confirmed):
    url, proposal_id, owner, team = merged_workspace
    db.add(ProposalMilestone(proposal_id=proposal_id, summary="Результат, сохранённый до обновления из Git.",
        points=10 if confirmed else 0, confirmed_at=utc_now() if confirmed else None))
    db.commit()
    db.expire_all()
    progress = client.get("/api/proposals", headers=team).json()[0]["progress"]
    assert progress["description"] == progress["summary"] == "Результат, сохранённый до обновления из Git."
    base = f"/api/proposals/{proposal_id}/progress"
    response = client.post(base + "/confirm", headers=owner)
    assert response.status_code == (409 if confirmed else 200)
    assert client.post(base + "/confirm", headers=owner).status_code == 409
    assert client.post(base, headers=team, json={"description": "Повторно отправленный результат не должен давать баллы."}).status_code == 409
    assert client.get("/api/proposals", headers=team).json()[0]["progress"]["points"] == 10
    assert client.delete(url, headers=owner).status_code == 204
    assert db.get(ProposalMilestone, proposal_id) is None
    assert db.get(Proposal, proposal_id) is None


def test_progress_return_for_revision_keeps_upstream_editing_contract(client, merged_workspace):
    _, proposal_id, owner, team = merged_workspace
    base = f"/api/proposals/{proposal_id}/progress"
    evidence = {"description": "Результат готов, проведены испытания основных сценариев."}
    assert client.post(base, headers=team, json=evidence).status_code == 200
    assert client.post(base + "/reject", headers=team).status_code == 403
    assert client.post(base + "/reject", headers=owner).json()["progress"] is None
    assert client.post(base, headers=team, json=evidence).status_code == 200
    assert client.post(base + "/confirm", headers=owner).json()["progress"]["points"] == 10
    assert client.post(base + "/reject", headers=owner).status_code == 409


def test_published_revision_changes_version_and_cannot_be_confirmed_from_stale_screen(client, db, merged_workspace):
    url, _, owner, _ = merged_workspace
    before = client.get(url, headers=owner).json()
    changed = client.patch(url, headers=owner, json={"data": "Подготовлен новый набор обезличенных материалов для команды."}).json()
    assert changed["updated_at"] != before["updated_at"]
    assert changed["score"] == 0 and changed["potential_score"] == 20
    assert client.post(url + "/confirm", headers=owner, json={"expected_updated_at": before["updated_at"]}).status_code == 409
    assert client.get(url).json()["data"] is None
    assert client.post(url + "/confirm", headers=owner, json={"expected_updated_at": changed["updated_at"]}).json()["score"] == 20


def test_stale_session_cannot_overwrite_published_revision(client, db, merged_workspace):
    url, _, owner, _ = merged_workspace
    task_id = int(url.rsplit("/", 1)[1])
    stale = tasks_service.get_task(db, task_id)
    with sessionmaker(db.get_bind(), autoflush=False, expire_on_commit=False)() as editor:
        tasks_service.update_task(editor, task_id, 1, TaskPatch(data="Другой редактор сохранил новое описание доступных материалов."))
    with pytest.raises(HTTPException) as error:
        tasks_service.confirm_task(db, stale.id, 1)
    assert error.value.status_code == 409
    assert client.get(url).json()["data"] is None
    assert client.get(url, headers=owner).json()["has_pending_changes"]


def test_old_source_policy_cache_is_reanalyzed(client, db, merged_workspace, fake_ai):
    url, _, owner, _ = merged_workspace
    task = client.get(url, headers=owner).json()
    connection = ai_service.get_connection(db, 1)
    old_fingerprint = hashlib.sha256(json.dumps([task["raw_text"], {}, connection.base_url, connection.model,
        connection.response_format, hashlib.sha256(connection.api_key.encode()).hexdigest()],
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    db.add(AIAnalysis(task_id=task["id"], fingerprint=old_fingerprint, payload={
        "missing_fields": [], "questions": [{"field": name, "text": "Проверьте прежние сведения"}
            for name in ["context", "data", "contact"]], "detected_fields": {"contact": "Старый непроверенный фрагмент"}}))
    db.commit()
    response = client.post(url + "/questions", headers=owner)
    assert response.status_code == 200
    assert response.json()["detected_fields"]["contact"] is None
    assert any(request.method == "POST" for request in fake_ai["requests"])
