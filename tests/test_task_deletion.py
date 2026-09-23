"""Атомарное удаление карточки, подтверждения и прогресса без потери соседних данных."""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import db as database
from app.modules.proposals import service as proposals_service
from app.modules.proposals.models import Proposal, ProposalProgress, utc_now
from app.modules.tasks import service as tasks_service
from app.modules.tasks.models import Task, TaskVerification
from app.modules.tasks.schemas import TaskPatch
from app.modules.teams.models import Team
from app.modules.users.models import User


@pytest.fixture
def db():
    # Проверяем ту же защиту FK, которая включается на engine приложения.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    event.listen(engine, "connect", database._enable_sqlite_foreign_keys)
    database.load_models()
    database.Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)() as session:
        yield session
    engine.dispose()


@pytest.fixture
def actors(db):
    db.add_all(
        Team(id=i, name=f"Команда {i}", interests=[], skills=[], tech=[])
        for i in range(1, 4)
    )
    db.flush()
    db.add_all([
        User(id=1, name="Владелец", role="business"),
        User(id=2, name="Другой владелец", role="business"),
        *[User(id=i + 2, name=f"Участник {i}", role="team", team_id=i)
          for i in range(1, 4)],
    ])
    db.commit()
    return {i: {"X-User-Id": str(i)} for i in range(1, 6)}


def create_task(client, headers, status="published"):
    response = client.post(
        "/api/tasks/draft", headers=headers,
        json={"title": "Карточка для удаления", "raw_text": "Описание задачи бизнеса"},
    )
    assert response.status_code == 201
    task_id = response.json()["id"]
    if status != "draft":
        assert client.patch(f"/api/tasks/{task_id}", headers=headers, json={
            "context": "Полный контекст задачи, вручную проверенный владельцем."
        }).status_code == 200
        assert client.post(f"/api/tasks/{task_id}/confirm", headers=headers).status_code == 200
    if status == "published":
        assert client.post(f"/api/tasks/{task_id}/publish", headers=headers).status_code == 200
    return task_id


def create_proposal(client, headers, task_id):
    response = client.post("/api/proposals", headers=headers, json={
        "task_id": task_id, "idea": "Предлагаем прототип решения задачи",
        "plan": "Сначала изучим данные, затем реализуем прототип", "deadline": "2 недели",
    })
    assert response.status_code == 201
    return response.json()["id"]


def add_progress(db, proposal_ids, *, confirmed=False):
    """Прогресс может сохраниться у любого статуса после ручного пересмотра выбора."""
    for proposal_id in proposal_ids:
        proposal = db.get(Proposal, proposal_id)
        owner_id = db.get(Task, proposal.task_id).owner_id
        db.add(ProposalProgress(
            proposal_id=proposal_id,
            description="Создан работающий прототип и проверен на тестовых данных.",
            link="https://example.org/demo",
            points=10 if confirmed else 0,
            confirmed_at=utc_now() if confirmed else None,
            confirmed_by=owner_id if confirmed else None,
        ))
    db.commit()
    return ProposalProgress.__table__


@pytest.mark.parametrize("status", ["draft", "confirmed", "published"])
def test_owner_can_delete_any_task_status(client, db, actors, status):
    task_id = create_task(client, actors[1], status)
    response = client.delete(f"/api/tasks/{task_id}", headers=actors[1])
    assert response.status_code == 204
    assert response.content == b""
    assert db.get(Task, task_id) is None
    assert db.get(TaskVerification, task_id) is None
    assert client.get(f"/api/tasks/{task_id}").status_code == 404
    assert client.delete(f"/api/tasks/{task_id}", headers=actors[1]).status_code == 404


@pytest.mark.parametrize("user_id,expected", [(None, 401), (999, 401), (2, 403), (3, 403)])
def test_delete_checks_identity_role_and_owner(client, db, actors, user_id, expected):
    task_id = create_task(client, actors[1])
    proposal_id = create_proposal(client, actors[3], task_id)
    headers = {} if user_id is None else {"X-User-Id": str(user_id)}
    assert client.delete(f"/api/tasks/{task_id}", headers=headers).status_code == expected
    assert db.get(Task, task_id) is not None
    assert db.get(Proposal, proposal_id) is not None


def test_unknown_task_is_404(client, actors):
    assert client.delete("/api/tasks/999", headers=actors[1]).status_code == 404


@pytest.mark.parametrize("progress_state", [None, "submitted", "confirmed"])
def test_delete_cascades_all_statuses_and_preserves_other_records(
    client, db, actors, progress_state
):
    target = create_task(client, actors[1])
    same_owner = create_task(client, actors[1])
    other_owner = create_task(client, actors[2])
    removed = [create_proposal(client, actors[user], target) for user in (3, 4, 5)]
    kept = [create_proposal(client, actors[3], task) for task in (same_owner, other_owner)]
    assert client.post(f"/api/proposals/{removed[1]}/accept", headers=actors[1]).status_code == 200
    assert client.post(f"/api/proposals/{removed[2]}/reject", headers=actors[1]).status_code == 200
    progress = add_progress(db, removed + kept, confirmed=progress_state == "confirmed") if progress_state else None
    users_before = client.get("/api/users").json()
    teams_before = client.get("/api/teams").json()
    remaining_cards = {task: client.get(f"/api/tasks/{task}").json() for task in (same_owner, other_owner)}
    remaining_proposals = [dict(row) for row in db.execute(
        select(Proposal.__table__).where(Proposal.id.in_(kept)).order_by(Proposal.id)
    ).mappings()]
    remaining_progress = [dict(row) for row in db.execute(
        select(ProposalProgress.__table__).where(ProposalProgress.proposal_id.in_(kept)).order_by(ProposalProgress.id)
    ).mappings()]
    remaining_verifications = [dict(row) for row in db.execute(
        select(TaskVerification.__table__).where(TaskVerification.task_id != target).order_by(TaskVerification.task_id)
    ).mappings()]

    assert client.delete(f"/api/tasks/{target}", headers=actors[1]).status_code == 204

    db.expire_all()
    assert set(db.scalars(select(Proposal.id))) == set(kept)
    assert set(db.scalars(select(Task.id))) == {same_owner, other_owner}
    assert db.get(TaskVerification, target) is None
    assert client.get(f"/api/tasks/{target}/proposals", headers=actors[1]).status_code == 404
    assert {task["id"] for task in client.get("/api/catalog").json()} == {same_owner, other_owner}
    assert {task["id"] for task in client.get("/api/tasks", headers=actors[1]).json()} == {same_owner}
    for user_id in actors:
        assert all(p["task_id"] != target for p in client.get("/api/proposals", headers=actors[user_id]).json())
    assert client.get("/api/users").json() == users_before
    assert client.get("/api/teams").json() == teams_before
    assert {task: client.get(f"/api/tasks/{task}").json() for task in remaining_cards} == remaining_cards
    assert [dict(row) for row in db.execute(
        select(Proposal.__table__).where(Proposal.id.in_(kept)).order_by(Proposal.id)
    ).mappings()] == remaining_proposals
    if progress is not None:
        assert set(db.scalars(select(progress.c.proposal_id))) == set(kept)
    assert [dict(row) for row in db.execute(
        select(ProposalProgress.__table__).order_by(ProposalProgress.id)
    ).mappings()] == remaining_progress
    assert [dict(row) for row in db.execute(
        select(TaskVerification.__table__).order_by(TaskVerification.task_id)
    ).mappings()] == remaining_verifications
    assert db.connection().exec_driver_sql("PRAGMA foreign_key_check").all() == []


@pytest.mark.parametrize("confirmed", [False, True])
def test_failed_commit_restores_task_proposals_progress_and_verification(client, db, actors, monkeypatch, confirmed):
    task_id = create_task(client, actors[1])
    proposal_id = create_proposal(client, actors[3], task_id)
    progress = add_progress(db, [proposal_id], confirmed=confirmed)
    snapshot = dict(db.get(TaskVerification, task_id).values)

    def fail_commit():
        db.flush()  # Карточка и зависимые записи уже удалены внутри транзакции.
        assert db.connection().execute(select(Task.id)).all() == []
        assert db.connection().execute(select(Proposal.id)).all() == []
        assert db.connection().execute(select(progress.c.proposal_id)).all() == []
        assert db.connection().execute(select(TaskVerification.task_id)).all() == []
        raise RuntimeError("Ошибка фиксации транзакции")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="Ошибка фиксации"):
        client.delete(f"/api/tasks/{task_id}", headers=actors[1])
    assert db.get(Task, task_id) is not None
    assert db.get(Proposal, proposal_id) is not None
    assert db.scalar(select(progress.c.proposal_id)) == proposal_id
    assert db.get(TaskVerification, task_id).values == snapshot
    assert db.scalar(select(progress.c.points)) == (10 if confirmed else 0)


def test_proposal_deletion_helper_does_not_commit(client, db, actors):
    task_id = create_task(client, actors[1])
    proposal_id = create_proposal(client, actors[3], task_id)
    progress = add_progress(db, [proposal_id], confirmed=True)
    proposals_service.delete_for_task(db, task_id)
    db.rollback()
    assert db.get(Proposal, proposal_id) is not None
    assert db.scalar(select(progress.c.proposal_id)) == proposal_id


def test_stale_delete_preserves_other_session_edit(client, db, actors):
    task_id = create_task(client, actors[1])
    stale_task = tasks_service.get_task(db, task_id)
    with sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)() as editor:
        tasks_service.update_task(editor, task_id, 1, TaskPatch(context="Другой редактор обновил исходные сведения этой карточки."))
    with pytest.raises(HTTPException) as error:
        tasks_service.delete_task(db, stale_task.id, 1)
    assert error.value.status_code == 409
    db.expire_all()
    assert tasks_service.to_owner_read(db, db.get(Task, task_id))["context"] == "Другой редактор обновил исходные сведения этой карточки."
    assert db.get(TaskVerification, task_id) is not None


def test_sqlite_rejects_late_proposal_for_deleted_task(client, db, actors):
    assert event.contains(database.engine, "connect", database._enable_sqlite_foreign_keys)
    assert db.connection().exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    # Совместимость со старой схемой: FK по-прежнему не полагается на ON DELETE CASCADE.
    task_fk = next(fk for fk in inspect(db.connection()).get_foreign_keys("proposals")
                   if fk["constrained_columns"] == ["task_id"])
    assert task_fk["options"].get("ondelete") is None
    task_id = create_task(client, actors[1])
    tasks_service.delete_task(db, task_id, 1)
    db.add(Proposal(task_id=task_id, team_id=1, idea="Поздний отклик",
                    plan="План команды", deadline="2 недели", status="pending"))
    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        db.commit()
    db.rollback()
    assert list(db.scalars(select(Proposal.id))) == []
    assert client.post("/api/proposals", headers=actors[3], json={
        "task_id": task_id, "idea": "Предлагаем решение задачи",
        "plan": "Изучим данные и создадим прототип", "deadline": "2 недели",
    }).status_code == 404
