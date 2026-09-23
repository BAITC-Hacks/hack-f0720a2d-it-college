"""Приватность черновиков и подтверждение изменений опубликованной карточки."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import db as database
from app.modules.proposals.models import Proposal
from app.modules.tasks.models import Task, TaskRevision
from app.modules.teams.models import Team
from app.modules.users.models import User


@pytest.fixture
def db():
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
    db.add(Team(id=1, name="Команда", interests=[], skills=[], tech=[]))
    db.flush()
    db.add_all([
        User(id=1, name="Владелец", role="business"),
        User(id=2, name="Другой бизнес", role="business"),
        User(id=3, name="Команда", role="team", team_id=1),
    ])
    db.commit()
    return {i: {"X-User-Id": str(i)} for i in (1, 2, 3)}


def create_task(client, headers, status="published"):
    response = client.post("/api/tasks/draft", headers=headers, json={
        "title": "Подтверждённое название", "raw_text": "Описание задачи бизнеса",
        "industry": "Образование",
    })
    assert response.status_code == 201
    task_id = response.json()["id"]
    url = f"/api/tasks/{task_id}"
    if status != "draft":
        assert client.post(url + "/confirm", headers=headers).status_code == 200
    if status == "published":
        assert client.post(url + "/publish", headers=headers).status_code == 200
    return url


@pytest.mark.parametrize("status", ["draft", "confirmed"])
def test_unpublished_card_is_private(client, actors, status):
    url = create_task(client, actors[1], status)
    assert client.get(url).status_code == 401
    assert client.get(url, headers=actors[2]).status_code == 403
    assert client.get(url, headers=actors[3]).status_code == 403
    assert client.get(url, headers={"X-User-Id": "999"}).status_code == 401
    assert client.get(url, headers=actors[1]).json()["status"] == status
    assert client.get(url + "/edit", headers=actors[1]).status_code == 200
    assert client.get("/api/catalog").json() == []


def test_pending_fields_and_rating_are_visible_only_in_owner_preview(client, db, actors):
    url = create_task(client, actors[1])
    original = client.get(url).json()
    response = client.patch(url, headers=actors[1], json={
        "title": "Новое неподтверждённое название",
        "data": "Новые материалы, содержащие достаточное описание доступных данных.",
    })
    assert response.status_code == 200
    preview = response.json()
    assert preview["title"] != original["title"]
    assert preview["score"] == 20
    assert preview["status"] == "published"
    assert preview["has_pending_changes"] is True
    assert str(UUID(preview["revision_token"])) == preview["revision_token"]
    assert client.get(url + "/edit", headers=actors[1]).json() == preview

    for headers in ({}, actors[1], actors[2], actors[3]):
        assert client.get(url, headers=headers).json() == original
    catalog = client.get("/api/catalog").json()[0]
    assert catalog["title"] == original["title"]
    assert catalog["data"] is None
    assert catalog["score"] == original["score"] == 0
    own_card = client.get("/api/tasks", headers=actors[1]).json()[0]
    assert own_card["has_pending_changes"] is True
    assert own_card["revision_token"] is None
    assert own_card["title"] == original["title"]
    assert own_card["score"] == original["score"]
    db.expire_all()
    assert db.get(Task, original["id"]).data is None
    assert db.get(TaskRevision, original["id"]).payload["data"] == preview["data"]


def test_only_latest_revision_can_be_confirmed_once(client, db, actors):
    url = create_task(client, actors[1])
    first = client.patch(url, headers=actors[1], json={
        "data": "Данные, содержащие достаточно подробное описание материалов.",
    }).json()
    second = client.patch(url, headers=actors[1], json={
        "need": "Потребность, описанная владельцем задачи для совместной работы.",
    }).json()
    assert second["data"] == first["data"]
    assert second["score"] == 30
    assert second["revision_token"] != first["revision_token"]
    assert client.post(url + "/confirm-changes", headers=actors[1], json={
        "revision_token": first["revision_token"],
    }).status_code == 409
    assert client.get(url).json()["score"] == 0
    response = client.post(url + "/confirm-changes", headers=actors[1], json={
        "revision_token": second["revision_token"],
    })
    assert response.status_code == 200
    live = response.json()
    assert live["score"] == 30
    assert live["status"] == "published"
    assert live["has_pending_changes"] is False
    assert live["revision_token"] is None
    assert client.get(url).json() == live
    assert client.get(url + "/edit", headers=actors[1]).json() == live
    assert client.get("/api/catalog").json()[0]["score"] == 30
    assert db.get(TaskRevision, live["id"]) is None
    assert client.post(url + "/confirm-changes", headers=actors[1], json={
        "revision_token": second["revision_token"],
    }).status_code == 409
    assert client.post(url + "/confirm", headers=actors[1]).status_code == 409


@pytest.mark.parametrize("actor,expected", [(None, 401), (2, 403), (3, 403)])
def test_other_users_cannot_edit_read_preview_or_confirm(client, actors, actor, expected):
    url = create_task(client, actors[1])
    preview = client.patch(url, headers=actors[1], json={"title": "Частные изменения"}).json()
    headers = actors[actor] if actor else {}
    assert client.get(url + "/edit", headers=headers).status_code == expected
    assert client.patch(url, headers=headers, json={"title": "Чужое изменение"}).status_code == expected
    assert client.post(url + "/confirm-changes", headers=headers, json={
        "revision_token": preview["revision_token"],
    }).status_code == expected
    assert client.get(url + "/edit", headers=actors[1]).json() == preview


def test_revert_and_recreate_revision_does_not_reuse_token(client, db, actors):
    url = create_task(client, actors[1])
    change = {"data": "Первое описание доступных материалов, ещё не подтверждённое."}
    first = client.patch(url, headers=actors[1], json=change).json()
    unchanged = client.patch(url, headers=actors[1], json=change).json()
    assert unchanged["revision_token"] == first["revision_token"]
    reverted = client.patch(url, headers=actors[1], json={"data": None}).json()
    assert reverted["has_pending_changes"] is False
    assert db.get(TaskRevision, reverted["id"]) is None
    recreated = client.patch(url, headers=actors[1], json=change).json()
    assert recreated["revision_token"] != first["revision_token"]
    assert client.post(url + "/confirm-changes", headers=actors[1], json={
        "revision_token": first["revision_token"],
    }).status_code == 409


@pytest.mark.parametrize("status", ["draft", "confirmed", "published"])
def test_confirmation_without_pending_revision_is_rejected(client, actors, status):
    url = create_task(client, actors[1], status)
    assert client.post(url + "/confirm-changes", headers=actors[1], json={
        "revision_token": str(uuid4()),
    }).status_code == 409


@pytest.mark.parametrize("body", [{}, {"revision_token": "invalid"}, {"revision_token": None}])
def test_revision_token_is_required_and_validated(client, actors, body):
    url = create_task(client, actors[1])
    assert client.post(url + "/confirm-changes", headers=actors[1], json=body).status_code == 422


def test_draft_patch_still_saves_directly_and_requires_confirmation(client, db, actors):
    url = create_task(client, actors[1], "confirmed")
    response = client.patch(url, headers=actors[1], json={
        "context": "Подробное описание контекста, добавленное представителем бизнеса.",
    })
    task = response.json()
    assert response.status_code == 200
    assert task["status"] == "draft"
    assert task["score"] == 10
    assert task["has_pending_changes"] is False
    assert db.get(TaskRevision, task["id"]) is None
    assert client.get(url, headers=actors[1]).json() == task
    assert client.post(url + "/publish", headers=actors[1]).status_code == 409


def test_delete_task_also_removes_pending_revision_and_proposals(client, db, actors):
    url = create_task(client, actors[1])
    task = client.patch(url, headers=actors[1], json={"title": "Изменённая карточка"}).json()
    response = client.post("/api/proposals", headers=actors[3], json={
        "task_id": task["id"], "idea": "Создадим подходящее решение", "plan": "Уточним и реализуем требования",
        "deadline": "2 недели",
    })
    assert response.status_code == 201
    assert client.delete(url, headers=actors[1]).status_code == 204
    assert db.get(Task, task["id"]) is None
    assert db.get(TaskRevision, task["id"]) is None
    assert list(db.scalars(select(Proposal.id))) == []
    assert client.get(url + "/edit", headers=actors[1]).status_code == 404


def test_failed_confirmation_restores_revision_and_live_card(client, db, actors, monkeypatch):
    url = create_task(client, actors[1])
    original = client.get(url).json()
    preview = client.patch(url, headers=actors[1], json={
        "data": "Новые материалы, которые не должны попасть в каталог при сбое.",
    }).json()

    def fail_commit():
        db.flush()
        raise RuntimeError("Сбой фиксации подтверждения")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="Сбой фиксации"):
        client.post(url + "/confirm-changes", headers=actors[1], json={
            "revision_token": preview["revision_token"],
        })
    assert client.get(url).json() == original
    assert client.get(url + "/edit", headers=actors[1]).json() == preview


def test_failed_deletion_restores_revision(client, db, actors, monkeypatch):
    url = create_task(client, actors[1])
    preview = client.patch(url, headers=actors[1], json={"title": "Новая карточка"}).json()

    def fail_commit():
        db.flush()
        raise RuntimeError("Сбой удаления")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="Сбой удаления"):
        client.delete(url, headers=actors[1])
    assert client.get(url + "/edit", headers=actors[1]).json() == preview


def test_new_revision_table_preserves_existing_task_schema_and_data():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    event.listen(engine, "connect", database._enable_sqlite_foreign_keys)
    database.load_models()
    database.Base.metadata.create_all(engine, tables=[Team.__table__, User.__table__, Task.__table__])
    with sessionmaker(bind=engine)() as db:
        db.add(User(id=1, name="Владелец", role="business"))
        db.flush()
        db.add(Task(id=1, owner_id=1, title="Существующая карточка", raw_text="Существующие данные"))
        db.commit()
        old_schema = db.scalar(text("SELECT sql FROM sqlite_master WHERE name = 'tasks'"))
    assert not inspect(engine).has_table("task_revisions")
    database.Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        assert db.scalar(text("SELECT sql FROM sqlite_master WHERE name = 'tasks'")) == old_schema
        assert db.get(Task, 1).raw_text == "Существующие данные"
        db.add(TaskRevision(task_id=1, payload={"title": "Изменение"}, token=str(uuid4())))
        db.commit()
        assert db.get(TaskRevision, 1).payload == {"title": "Изменение"}
    engine.dispose()
