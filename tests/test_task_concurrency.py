"""Два параллельных кабинета не публикуют и не перезаписывают устаревшую версию."""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, load_models
from app.modules.rating.service import FIELD_WEIGHTS
from app.modules.tasks import service
from app.modules.tasks.schemas import DraftCreate, TaskPatch
from app.modules.users.models import User


@pytest.fixture
def concurrent_sessions():
    # Только собственная in-memory SQLite; рабочая БД и сервер не используются.
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    load_models()
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, autoflush=False, expire_on_commit=False)
    with sessions() as setup:
        setup.add(User(id=1, name="Владелец", role="business"))
        setup.commit()
        task = service.create_draft(setup, 1, DraftCreate(raw_text="Исходное описание задачи"))
        fields = {field: "Подробные сведения, которые владелец проверил и подтвердил." for field in FIELD_WEIGHTS}
        service.update_task(setup, task.id, 1, TaskPatch(**fields))
        service.confirm_task(setup, task.id, 1)
        task_id = task.id
    try:
        yield sessions, task_id
    finally:
        engine.dispose()


def change_from_second_session(sessions, task_id):
    with sessions() as editor:
        service.update_task(editor, task_id, 1, TaskPatch(data="Новый набор данных требует отдельной проверки владельцем."))


def assert_second_edit_unchanged(sessions, task_id):
    with sessions() as reader:
        task = service.to_read(service.get_task(reader, task_id))
        assert task["data"] == "Новый набор данных требует отдельной проверки владельцем."
        assert task["status"] == "draft"
        assert task["score"] == 80
        assert task["unconfirmed_fields"] == ["data"]


def test_stale_publish_cannot_publish_changed_card(concurrent_sessions):
    sessions, task_id = concurrent_sessions
    with sessions() as publisher:
        stale_card = service.get_task(publisher, task_id)
        assert stale_card.status == "confirmed"
        change_from_second_session(sessions, task_id)
        with pytest.raises(HTTPException) as error:
            service.publish_task(publisher, task_id, 1)
        assert error.value.status_code == 409
    assert_second_edit_unchanged(sessions, task_id)


@pytest.mark.parametrize("send_expected_version", [False, True])
def test_stale_confirmation_cannot_confirm_changed_card(concurrent_sessions, send_expected_version):
    sessions, task_id = concurrent_sessions
    with sessions() as reviewer:
        stale_card = service.get_task(reviewer, task_id)
        expected = stale_card.updated_at if send_expected_version else None
        change_from_second_session(sessions, task_id)
        with pytest.raises(HTTPException) as error:
            service.confirm_task(reviewer, task_id, 1, expected_updated_at=expected)
        assert error.value.status_code == 409
    assert_second_edit_unchanged(sessions, task_id)


def test_stale_patch_does_not_lose_other_editor_changes(concurrent_sessions):
    sessions, task_id = concurrent_sessions
    with sessions() as stale_editor:
        stale_card = service.get_task(stale_editor, task_id)
        assert stale_card.status == "confirmed"
        change_from_second_session(sessions, task_id)
        with pytest.raises(HTTPException) as error:
            service.update_task(stale_editor, task_id, 1, TaskPatch(data="Устаревший ответ из другого открытого окна."))
        assert error.value.status_code == 409
    assert_second_edit_unchanged(sessions, task_id)
