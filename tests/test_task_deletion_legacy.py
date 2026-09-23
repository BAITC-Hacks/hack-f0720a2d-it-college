"""Удаление в изолированной старой SQLite: без таблицы прогресса или с percent/comment."""

from datetime import datetime

import pytest
from sqlalchemy import MetaData, Table, create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import db as database
from app.modules.proposals import service as proposals_service
from app.modules.proposals.models import Proposal
from app.modules.tasks import service as tasks_service
from app.modules.tasks.models import Task, TaskVerification
from app.modules.teams.models import Team
from app.modules.users.models import User


@pytest.fixture(params=[False, True], ids=["without_progress", "legacy_progress"])
def legacy_database(request):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", database._enable_sqlite_foreign_keys)
    database.load_models()
    # Не подменяем общую metadata и не удаляем существующие таблицы: эта БД только для теста.
    tables = [table for table in database.Base.metadata.sorted_tables if table.name != "proposal_progress"]
    database.Base.metadata.create_all(engine, tables=tables)
    progress = None
    with engine.begin() as connection:
        if request.param:
            connection.exec_driver_sql("""
                CREATE TABLE proposal_progress (
                    proposal_id INTEGER PRIMARY KEY REFERENCES proposals(id),
                    percent INTEGER NOT NULL,
                    comment TEXT NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """)
            progress = Table("proposal_progress", MetaData(), autoload_with=connection)
        connection.execute(Team.__table__.insert(), {"id": 1, "name": "Команда", "interests": [], "skills": [], "tech": []})
        connection.execute(User.__table__.insert(), {"id": 1, "name": "Владелец", "role": "business"})
        for task_id in (1, 2):
            connection.execute(Task.__table__.insert(), {
                "id": task_id, "owner_id": 1, "raw_text": "Исходное описание",
                "status": "published", "context": "Подтверждённый контекст старой карточки.",
            })
            connection.execute(TaskVerification.__table__.insert(), {
                "task_id": task_id, "values": {"context": "Подтверждённый контекст старой карточки."},
            })
            connection.execute(Proposal.__table__.insert(), {
                "id": task_id, "task_id": task_id, "team_id": 1,
                "idea": "Идея решения", "plan": "План работы", "deadline": "2 недели", "status": "accepted",
            })
            if progress is not None:
                connection.execute(progress.insert(), {
                    "proposal_id": task_id, "percent": 50, "comment": "Старый результат",
                    "updated_at": datetime(2026, 9, 23),
                })
    try:
        with sessionmaker(engine, autoflush=False, expire_on_commit=False)() as db:
            yield db, progress
    finally:
        engine.dispose()


def assert_ids(db, progress, task_ids, proposal_ids):
    assert list(db.scalars(select(Task.id).order_by(Task.id))) == task_ids
    assert list(db.scalars(select(TaskVerification.task_id).order_by(TaskVerification.task_id))) == task_ids
    assert list(db.scalars(select(Proposal.id).order_by(Proposal.id))) == proposal_ids
    if progress is not None:
        assert list(db.scalars(select(progress.c.proposal_id).order_by(progress.c.proposal_id))) == proposal_ids
    assert db.connection().exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_delete_supports_legacy_without_loading_new_progress_model(legacy_database):
    db, progress = legacy_database
    tasks_service.delete_task(db, 1, 1)
    assert_ids(db, progress, [2], [2])


def test_legacy_helper_keeps_commit_with_caller(legacy_database):
    db, progress = legacy_database
    proposals_service.delete_for_task(db, 1)
    db.rollback()
    assert_ids(db, progress, [1, 2], [1, 2])


def test_legacy_failed_commit_restores_all_rows(legacy_database, monkeypatch):
    db, progress = legacy_database

    def fail_commit():
        db.flush()
        assert_ids(db, progress, [2], [2])
        raise RuntimeError("Ошибка фиксации тестовой транзакции")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="Ошибка фиксации"):
        tasks_service.delete_task(db, 1, 1)
    assert_ids(db, progress, [1, 2], [1, 2])
