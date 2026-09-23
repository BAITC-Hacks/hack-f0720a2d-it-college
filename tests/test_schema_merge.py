"""Legacy schemas are archived and converted without losing revisions or rewards."""

import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.orm import sessionmaker

from app import db as database
from app.modules.ai.models import AIConnection
from app.modules.proposals.models import Proposal, ProposalMilestone, ProposalProgress
from app.modules.tasks import service as tasks_service
from app.modules.tasks.models import Task, TaskRevision
from app.modules.teams.models import Team
from app.modules.users.models import User


@pytest.fixture
def legacy_engine(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    event.listen(engine, "connect", database._enable_sqlite_foreign_keys)
    database.load_models()
    database.Base.metadata.create_all(engine, tables=[Team.__table__, User.__table__, Task.__table__])
    with engine.begin() as connection:
        connection.execute(Team.__table__.insert(), {"id": 1, "name": "Команда"})
        connection.execute(User.__table__.insert(), {"id": 1, "name": "Владелец", "role": "business"})
        connection.execute(Task.__table__.insert(), [
            {"id": number, "owner_id": 1, "raw_text": "Описание", "status": "published"}
            for number in (1, 2)
        ])
        connection.exec_driver_sql("""CREATE TABLE proposals (
            id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id),
            team_id INTEGER NOT NULL REFERENCES teams(id), idea TEXT NOT NULL,
            plan TEXT NOT NULL, deadline VARCHAR(120) NOT NULL, link VARCHAR(500),
            status VARCHAR(20) NOT NULL, created_at DATETIME NOT NULL
        )""")
        for number in (1, 2):
            connection.exec_driver_sql(
                "INSERT INTO proposals VALUES (?, ?, 1, 'Idea', 'Plan', 'Week', NULL, 'accepted', '2026-09-20 10:00:00')",
                (number, number),
            )
        connection.exec_driver_sql("""CREATE TABLE task_revisions (
            task_id INTEGER PRIMARY KEY REFERENCES tasks(id), payload JSON NOT NULL, token VARCHAR(36) NOT NULL
        )""")
        connection.exec_driver_sql("INSERT INTO task_revisions VALUES (?, ?, ?)", (
            1, json.dumps({"data": "Неопубликованные материалы", "contact": None}), "old-revision-token",
        ))
        connection.exec_driver_sql("""CREATE TABLE proposal_milestones (
            id INTEGER PRIMARY KEY, proposal_id INTEGER NOT NULL REFERENCES proposals(id),
            stage VARCHAR(20) NOT NULL, status VARCHAR(20) NOT NULL, description TEXT NOT NULL,
            link VARCHAR(500), submission_token VARCHAR(36) NOT NULL, review_comment TEXT,
            submitted_at DATETIME NOT NULL, reviewed_at DATETIME, UNIQUE(proposal_id, stage)
        )""")
        connection.exec_driver_sql("INSERT INTO proposal_milestones VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
            (1, 1, "research", "confirmed", "Подтверждённое исследование", "https://example.com/research", "token-1", "Проверено", "2026-09-20 12:00:00", "2026-09-21 12:00:00"),
            (2, 1, "prototype", "confirmed", "Подтверждённый прототип", "https://example.com/prototype", "token-2", None, "2026-09-21 13:00:00", "2026-09-22 12:00:00"),
            (3, 1, "final", "pending", "Финальный отчёт ожидает проверки", "https://example.com/final", "token-3", None, "2026-09-22 13:00:00", None),
            (4, 2, "research", "rejected", "Отчёт возвращён команде", None, "token-4", "Уточните данные", "2026-09-22 14:00:00", "2026-09-23 10:00:00"),
        ])
        connection.exec_driver_sql("""CREATE TABLE proposal_progress (
            proposal_id INTEGER PRIMARY KEY REFERENCES proposals(id), percent INTEGER NOT NULL,
            comment TEXT NOT NULL, updated_at DATETIME NOT NULL
        )""")
        connection.exec_driver_sql("INSERT INTO proposal_progress VALUES (2, 75, 'Черновой комментарий старой версии', '2026-09-23 11:00:00')")
        connection.exec_driver_sql("""CREATE TABLE ai_connections (
            user_id INTEGER PRIMARY KEY REFERENCES users(id), base_url TEXT NOT NULL,
            model VARCHAR(240) NOT NULL, api_key TEXT NOT NULL, response_format VARCHAR(20) NOT NULL
        )""")
        connection.exec_driver_sql("INSERT INTO ai_connections VALUES (1, 'http://localhost:1234/v1', 'local-model', 'synthetic-test-key', 'auto')")
    monkeypatch.setattr(database, "engine", engine)
    try:
        yield engine
    finally:
        engine.dispose()


def all_rows(engine, name):
    with engine.connect() as connection:
        return connection.exec_driver_sql(f'SELECT * FROM "{name}"').all()


def test_legacy_revisions_and_all_progress_are_preserved_idempotently(legacy_engine):
    originals = {name: all_rows(legacy_engine, name) for name in (
        "task_revisions", "proposal_milestones", "proposal_progress",
    )}
    database.create_tables()
    database.create_tables()
    for name, rows in originals.items():
        assert all_rows(legacy_engine, f"legacy_{name}_v1") == rows
    assert not any(name.endswith("_v1_2") for name in inspect(legacy_engine).get_table_names())
    with sessionmaker(legacy_engine)() as db:
        assert db.get(TaskRevision, 1).values == {"data": "Неопубликованные материалы", "contact": None}
        assert db.get(Task, 1).data is None
        first = db.get(Proposal, 1)
        assert first.version == 1
        assert first.progress.points == 50
        assert first.progress.status == "confirmed"
        for fragment in ("Подтверждённое исследование", "Подтверждённый прототип", "Финальный отчёт ожидает проверки", "Проверено", "https://example.com/research", "https://example.com/final"):
            assert fragment in first.progress.description
        assert first.progress.confirmed_at.isoformat() == "2026-09-22T12:00:00"
        second = db.get(Proposal, 2).progress
        assert second.points == 0
        assert second.confirmed_at is None
        assert "Отчёт возвращён команде" in second.description
        assert "Уточните данные" in second.description
        assert "75%" in second.description
        assert "Черновой комментарий старой версии" in second.description
        assert db.get(AIConnection, 1).provider == "compatible"
        assert db.get(AIConnection, 1).api_key == "synthetic-test-key"
        assert list(db.scalars(select(ProposalProgress))) == []
        assert db.connection().exec_driver_sql("PRAGMA foreign_key_check").all() == []
        # Old NOT NULL payload/token columns must not prevent future canonical inserts.
        db.add(TaskRevision(task_id=2, values={"title": "Новый черновик"}))
        db.commit()
        assert db.get(TaskRevision, 2).values["title"] == "Новый черновик"


def test_migration_failure_rolls_back_schema_and_data(legacy_engine, monkeypatch):
    original_names = set(inspect(legacy_engine).get_table_names())
    original_rows = all_rows(legacy_engine, "proposal_milestones")

    def fail_copy(*_args):
        raise RuntimeError("migration copy failed")

    monkeypatch.setattr(database, "_restore_legacy_progress", fail_copy)
    with pytest.raises(RuntimeError, match="migration copy failed"):
        database.create_tables()
    assert set(inspect(legacy_engine).get_table_names()) == original_names
    assert all_rows(legacy_engine, "proposal_milestones") == original_rows
    assert "version" not in {column["name"] for column in inspect(legacy_engine).get_columns("proposals")}
    assert "provider" not in {column["name"] for column in inspect(legacy_engine).get_columns("ai_connections")}


def test_existing_single_stage_result_does_not_hide_legacy_stage_rewards(legacy_engine):
    with legacy_engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE proposal_progress")
        ProposalProgress.__table__.create(connection)
        connection.execute(ProposalProgress.__table__.insert(), {
            "id": 91, "proposal_id": 1, "description": "Отдельный результат общей ветки",
            "points": 10, "confirmed_by": 1,
            "submitted_at": datetime(2026, 9, 23, 12), "confirmed_at": datetime(2026, 9, 23, 13),
        })
    original = all_rows(legacy_engine, "proposal_progress")
    database.create_tables()
    database.create_tables()
    assert all_rows(legacy_engine, "legacy_proposal_progress_v1") == original
    with sessionmaker(legacy_engine)() as db:
        result = db.get(Proposal, 1).progress
        assert result.points == 60
        assert "Отдельный результат общей ветки" in result.description
        assert "Подтверждённый прототип" in result.description
        assert list(db.scalars(select(ProposalProgress))) == []


def test_pending_legacy_stage_can_still_be_reviewed_once(legacy_engine):
    database.create_tables()
    from app.modules.proposals import service

    with sessionmaker(legacy_engine, expire_on_commit=False)() as db:
        service.confirm_progress(db, 2, 1)
        assert db.get(Proposal, 2).progress.points == 10
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as error:
            service.confirm_progress(db, 2, 1)
        assert error.value.status_code == 409
        assert db.get(Proposal, 1).progress.points == 50


def test_deleting_migrated_task_removes_its_canonical_and_archived_records(legacy_engine):
    database.create_tables()
    with sessionmaker(legacy_engine, expire_on_commit=False)() as db:
        tasks_service.delete_task(db, 1, 1)
        assert db.get(Task, 1) is None
        assert db.get(ProposalMilestone, 1) is None
        assert db.get(TaskRevision, 1) is None
        assert db.scalar(text("SELECT COUNT(*) FROM legacy_task_revisions_v1 WHERE task_id = 1")) == 0
        assert db.scalar(text("SELECT COUNT(*) FROM legacy_proposal_milestones_v1 WHERE proposal_id = 1")) == 0
        assert db.scalar(text("SELECT COUNT(*) FROM legacy_proposal_milestones_v1 WHERE proposal_id = 2")) == 1
        assert db.get(Proposal, 2).progress.points == 0
        assert db.connection().exec_driver_sql("PRAGMA foreign_key_check").all() == []
