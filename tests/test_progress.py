"""Этапы, ручная проверка, права и баллы без повторного начисления."""

import pytest
from sqlalchemy import func, select

from app.modules.proposals.models import Proposal, ProposalMilestone
from app.modules.tasks.models import Task
from app.modules.teams.models import Team
from app.modules.users.models import User


@pytest.fixture
def progress_data(db):
    db.add_all([Team(id=1, name="Первая"), Team(id=2, name="Другая")])
    db.flush()
    db.add_all([
        User(id=1, name="Владелец", role="business"),
        User(id=2, name="Чужой бизнес", role="business"),
        User(id=3, name="Своя команда", role="team", team_id=1),
        User(id=4, name="Чужая команда", role="team", team_id=2),
        User(id=5, name="Коллега", role="team", team_id=1),
        User(id=6, name="Без команды", role="team"),
    ])
    db.flush()
    db.add_all([
        Task(id=i, owner_id=1, title=f"Задача {i}", raw_text="Описание задачи", status="published")
        for i in (1, 2, 3)
    ])
    db.flush()
    db.add_all([
        Proposal(id=1, task_id=1, team_id=1, idea="Идея решения", plan="План решения", deadline="2 недели", status="accepted"),
        Proposal(id=2, task_id=2, team_id=1, idea="Идея решения", plan="План решения", deadline="2 недели", status="accepted"),
        Proposal(id=3, task_id=3, team_id=2, idea="Идея решения", plan="План решения", deadline="2 недели", status="accepted"),
    ])
    db.commit()


def headers(user_id):
    return {"X-User-Id": str(user_id)}


def submit(client, stage="research", proposal_id=1, user_id=3, **changes):
    payload = {"stage": stage, "description": "Отчёт о выполнении этапа с проверяемым результатом.", "link": "https://example.com/result"}
    payload.update(changes)
    return client.post(f"/api/proposals/{proposal_id}/progress", headers=headers(user_id), json=payload)


def review(client, snapshot, stage="research", decision="confirm", user_id=1, **changes):
    item = next(item for item in snapshot["stages"] if item["stage"] == stage)
    payload = {"submission_token": item["submission_token"], "comment": "Результат проверен"}
    payload.update(changes)
    return client.post(
        f"/api/proposals/{snapshot['proposal_id']}/progress/{stage}/{decision}",
        headers=headers(user_id), json=payload,
    )


def test_progress_is_sequential_and_points_are_not_duplicated(client, db, progress_data):
    initial = client.get("/api/proposals/1/progress", headers=headers(3)).json()
    assert initial["earned_points"] == initial["team_points"] == initial["completion_percent"] == 0
    assert [item["points"] for item in initial["stages"]] == [20, 30, 50]
    assert all(item["status"] == "not_started" and item["submission_token"] is None for item in initial["stages"])
    assert submit(client, "prototype").status_code == 409
    assert submit(client, "final").status_code == 409

    points = 0
    for stage, weight in (("research", 20), ("prototype", 30), ("final", 50)):
        sent = submit(client, stage)
        assert sent.status_code == 200
        assert sent.json()["earned_points"] == points
        assert submit(client, stage).status_code == 409
        reviewed = review(client, sent.json(), stage)
        assert reviewed.status_code == 200
        points += weight
        assert reviewed.json()["earned_points"] == reviewed.json()["team_points"] == points
        assert reviewed.json()["completion_percent"] == points
        assert review(client, sent.json(), stage).status_code == 409
        assert review(client, sent.json(), stage, "reject").status_code == 409
        assert submit(client, stage).status_code == 409

    assert db.scalar(select(func.count()).select_from(ProposalMilestone)) == 3
    assert client.get("/api/proposals/1/progress", headers=headers(5)).json()["team_points"] == 100


def test_rejected_stage_can_be_resubmitted_and_old_token_cannot_review_it(client, progress_data):
    first = submit(client).json()
    assert submit(client, "prototype").status_code == 409
    rejected = review(client, first, decision="reject", comment="Добавьте интервью с пользователями")
    assert rejected.status_code == 200
    assert rejected.json()["earned_points"] == 0
    assert rejected.json()["stages"][0]["review_comment"] == "Добавьте интервью с пользователями"
    assert submit(client, "prototype").status_code == 409
    second = submit(client, description="Дополненный отчёт с интервью и выводами.").json()
    assert second["stages"][0]["submission_token"] != first["stages"][0]["submission_token"]
    assert second["stages"][0]["review_comment"] is None
    assert second["stages"][0]["reviewed_at"] is None
    assert review(client, first).status_code == 409
    assert review(client, second).json()["earned_points"] == 20


def test_reopening_preserves_points_and_blocks_progress_until_reaccepted(client, progress_data):
    first = submit(client).json()
    assert review(client, first).json()["earned_points"] == 20
    pending_prototype = submit(client, "prototype").json()
    assert client.post("/api/proposals/1/reopen", headers=headers(1)).status_code == 200
    unchanged = client.get("/api/proposals/1/progress", headers=headers(3)).json()
    assert unchanged["earned_points"] == 20
    assert unchanged["stages"][1]["status"] == "pending"
    assert submit(client, "final").status_code == 409
    assert review(client, pending_prototype, "prototype").status_code == 409
    assert client.post("/api/proposals/1/accept", headers=headers(1)).status_code == 200
    assert review(client, pending_prototype, "prototype").json()["earned_points"] == 50


def test_team_points_sum_own_proposals_and_deleted_tasks_remove_points(client, db, progress_data):
    for proposal_id, user_id in ((1, 3), (2, 3), (3, 4)):
        sent = submit(client, proposal_id=proposal_id, user_id=user_id).json()
        assert review(client, sent).status_code == 200
    mine = client.get("/api/proposals/1/progress", headers=headers(3)).json()
    assert mine["earned_points"] == 20
    assert mine["team_points"] == 40
    assert client.get("/api/proposals/3/progress", headers=headers(4)).json()["team_points"] == 20
    assert client.delete("/api/tasks/1", headers=headers(1)).status_code == 204
    assert db.scalar(select(func.count()).select_from(ProposalMilestone).where(ProposalMilestone.proposal_id == 1)) == 0
    assert client.get("/api/proposals/1/progress", headers=headers(3)).status_code == 404
    assert client.get("/api/proposals/2/progress", headers=headers(3)).json()["team_points"] == 20


@pytest.mark.parametrize("user_id,status", [(None, 401), (999, 401), (2, 403), (4, 403), (6, 403), (1, 200), (3, 200), (5, 200)])
def test_progress_read_permissions(client, progress_data, user_id, status):
    response = client.get("/api/proposals/1/progress", headers=headers(user_id) if user_id is not None else {})
    assert response.status_code == status


def test_progress_mutation_permissions(client, progress_data):
    assert submit(client, user_id=1).status_code == 403
    assert submit(client, user_id=4).status_code == 403
    assert submit(client, user_id=6).status_code == 403
    sent = submit(client).json()
    assert review(client, sent, user_id=2).status_code == 403
    assert review(client, sent, user_id=3).status_code == 403


@pytest.mark.parametrize("changes", [
    {"description": "   "}, {"description": "short"}, {"description": "x" * 5001},
    {"stage": "invented"}, {"link": "javascript:alert(1)"}, {"link": "file:///secret"},
    {"extra": "unexpected"},
])
def test_progress_submission_validation(client, progress_data, changes):
    assert submit(client, **changes).status_code == 422


def test_review_validation(client, progress_data):
    sent = submit(client).json()
    assert review(client, sent, submission_token="invalid").status_code == 422
    assert review(client, sent, comment="x" * 2001).status_code == 422
    assert review(client, sent, comment=None).status_code == 200
