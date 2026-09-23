"""Compatible CAS coverage from elnar2, using the shared single-stage contract."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db import Base, _enable_sqlite_foreign_keys, load_models
from app.modules.proposals import service
from app.modules.proposals.models import Proposal
from app.modules.proposals.schemas import ProgressSubmit
from app.modules.tasks.models import Task
from app.modules.teams.models import Team
from app.modules.users.models import User


@pytest.fixture
def sessions(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'concurrency.db').as_posix()}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    load_models()
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    with factory() as db:
        db.add(Team(id=1, name="Команда"))
        db.flush()
        db.add(User(id=1, name="Владелец", role="business"))
        db.flush()
        db.add(Task(id=1, owner_id=1, raw_text="Описание задачи", status="published"))
        db.flush()
        db.add(Proposal(id=1, task_id=1, team_id=1, idea="Идея решения", plan="План решения", deadline="Неделя"))
        db.commit()
    try:
        yield factory
    finally:
        engine.dispose()


def submission(description="Подготовлен рабочий прототип, проверены основные сценарии."):
    return ProgressSubmit(description=description, link="https://example.com/demo")


def assert_conflict(operation):
    with pytest.raises(HTTPException) as error:
        operation()
    assert error.value.status_code == 409


def test_stale_decision_cannot_overwrite_another_decision(sessions):
    with sessions() as current, sessions() as stale:
        held = service.get_proposal(stale, 1)
        service.decide_proposal(current, 1, 1, "accepted")
        assert held.status == "pending"
        assert_conflict(lambda: service.decide_proposal(stale, 1, 1, "rejected"))
    with sessions() as reader:
        assert service.get_proposal(reader, 1).status == "accepted"


def test_stale_reopen_detects_status_changed_back_to_accepted(sessions):
    with sessions() as current, sessions() as stale:
        service.decide_proposal(current, 1, 1, "accepted")
        held = service.get_proposal(stale, 1)
        service.reopen_proposal(current, 1, 1)
        service.decide_proposal(current, 1, 1, "accepted")
        assert held.status == "accepted"
        assert_conflict(lambda: service.reopen_proposal(stale, 1, 1))
    with sessions() as reader:
        assert service.get_proposal(reader, 1).status == "accepted"


def test_stale_progress_review_cannot_run_after_reopen(sessions):
    with sessions() as current, sessions() as stale:
        service.decide_proposal(current, 1, 1, "accepted")
        service.submit_progress(current, 1, 1, submission())
        held = service.get_proposal(stale, 1)
        service.reopen_proposal(current, 1, 1)
        assert held.status == "accepted"
        assert_conflict(lambda: service.confirm_progress(stale, 1, 1))
    with sessions() as reader:
        saved = service.get_proposal(reader, 1)
        assert saved.status == "pending"
        assert saved.progress.points == 0
        assert saved.progress.confirmed_at is None


def test_stale_progress_edit_cannot_overwrite_new_report(sessions):
    with sessions() as current, sessions() as stale:
        service.decide_proposal(current, 1, 1, "accepted")
        service.submit_progress(current, 1, 1, submission())
        held = service.get_proposal(stale, 1)
        replacement = "Новый отчёт содержит результаты дополнительных проверок команды."
        service.submit_progress(current, 1, 1, submission(replacement))
        assert held.progress.description != replacement
        assert_conflict(lambda: service.submit_progress(stale, 1, 1, submission()))
    with sessions() as reader:
        assert service.get_proposal(reader, 1).progress.description == replacement


def test_stale_rejection_cannot_remove_confirmed_progress(sessions):
    with sessions() as current, sessions() as stale:
        service.decide_proposal(current, 1, 1, "accepted")
        service.submit_progress(current, 1, 1, submission())
        held = service.get_proposal(stale, 1)
        service.confirm_progress(current, 1, 1)
        assert held.progress.points == 0
        assert_conflict(lambda: service.reject_progress(stale, 1, 1))
    with sessions() as reader:
        assert service.get_proposal(reader, 1).progress.points == 10


@pytest.mark.parametrize("operation", ["decision", "confirmation"])
def test_simultaneous_writers_have_only_one_winner(sessions, operation):
    if operation == "confirmation":
        with sessions() as db:
            service.decide_proposal(db, 1, 1, "accepted")
            service.submit_progress(db, 1, 1, submission())
    barrier = Barrier(2)

    def run(index):
        with sessions() as db:
            held = service.get_proposal(db, 1)
            version = held.version
            barrier.wait(timeout=5)
            assert held.version == version
            try:
                if operation == "decision":
                    service.decide_proposal(db, 1, 1, ("accepted", "rejected")[index])
                else:
                    service.confirm_progress(db, 1, 1)
                return 200, index
            except HTTPException as error:
                return error.status_code, index

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(run, (0, 1)))
    assert sorted(status for status, _ in results) == [200, 409]
    with sessions() as reader:
        saved = service.get_proposal(reader, 1)
        if operation == "decision":
            winner = next(index for status, index in results if status == 200)
            assert saved.status == ("accepted", "rejected")[winner]
        else:
            assert saved.progress.points == 10
            assert saved.progress.confirmed_at is not None
