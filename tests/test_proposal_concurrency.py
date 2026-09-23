"""CAS проверяется разными сессиями и одновременно пишущими соединениями SQLite."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db import Base, _enable_sqlite_foreign_keys, load_models
from app.modules.proposals import service
from app.modules.proposals.models import Proposal, ProposalMilestone
from app.modules.proposals.schemas import MilestoneReview, MilestoneSubmission, ProposalCreate
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
        db.add(User(id=1, name="Бизнес", role="business"))
        db.flush()
        db.add(Task(id=1, owner_id=1, raw_text="Описание задачи", status="published"))
        db.flush()
        db.add(Proposal(id=1, task_id=1, team_id=1, idea="Идея решения", plan="План решения", deadline="Неделя"))
        db.commit()
    try:
        yield factory
    finally:
        engine.dispose()


def submission():
    return MilestoneSubmission(stage="research", description="Результаты интервью с пользователями")


def review_payload(snapshot):
    return MilestoneReview(submission_token=snapshot["stages"][0]["submission_token"])


def test_stale_decision_cannot_overwrite_another_decision(sessions):
    with sessions() as first, sessions() as stale:
        old = service.get_proposal(stale, 1)
        chosen = service.decide_proposal(first, 1, 1, "accepted")
        assert chosen.version == 2
        assert old.status == "pending" and old.version == 1
        with pytest.raises(HTTPException) as exc:
            service.decide_proposal(stale, 1, 1, "rejected")
        assert exc.value.status_code == 409
        first.expire_all()
        assert service.get_proposal(first, 1).status == "accepted"


def test_stale_reopen_detects_even_a_status_changed_back_to_accepted(sessions):
    with sessions() as current, sessions() as stale:
        service.decide_proposal(current, 1, 1, "accepted")
        old = service.get_proposal(stale, 1)
        service.reopen_proposal(current, 1, 1)
        service.decide_proposal(current, 1, 1, "accepted")
        assert old.status == "accepted" and old.version == 2
        with pytest.raises(HTTPException) as exc:
            service.reopen_proposal(stale, 1, 1)
        assert exc.value.status_code == 409
        current.expire_all()
        assert service.get_proposal(current, 1).status == "accepted"


def test_stale_progress_review_cannot_overwrite_confirmed_result(sessions):
    with sessions() as current, sessions() as stale:
        service.decide_proposal(current, 1, 1, "accepted")
        sent = service.submit_progress(current, 1, 1, submission())
        old = service.get_proposal(stale, 1)
        service.review_progress(current, 1, 1, "research", review_payload(sent), "confirmed")
        assert old.version == 3
        with pytest.raises(HTTPException) as exc:
            service.review_progress(stale, 1, 1, "research", review_payload(sent), "rejected")
        assert exc.value.status_code == 409
        snapshot = service.get_progress(current, 1, 1, "business", None)
        assert snapshot["earned_points"] == 20
        assert snapshot["stages"][0]["status"] == "confirmed"


def test_stale_resubmission_cannot_replace_new_report(sessions):
    with sessions() as current, sessions() as stale:
        service.decide_proposal(current, 1, 1, "accepted")
        sent = service.submit_progress(current, 1, 1, submission())
        service.review_progress(current, 1, 1, "research", review_payload(sent), "rejected")
        old = service.get_proposal(stale, 1)
        newer = service.submit_progress(current, 1, 1, submission())
        assert old.version == 4
        with pytest.raises(HTTPException) as exc:
            service.submit_progress(stale, 1, 1, submission())
        assert exc.value.status_code == 409
        snapshot = service.get_progress(current, 1, 1, "business", None)
        assert snapshot["stages"][0]["submission_token"] == newer["stages"][0]["submission_token"]


def test_stale_progress_review_cannot_run_after_reopen(sessions):
    with sessions() as current, sessions() as stale:
        service.decide_proposal(current, 1, 1, "accepted")
        sent = service.submit_progress(current, 1, 1, submission())
        old = service.get_proposal(stale, 1)
        service.reopen_proposal(current, 1, 1)
        assert old.status == "accepted"
        with pytest.raises(HTTPException) as exc:
            service.review_progress(stale, 1, 1, "research", review_payload(sent), "confirmed")
        assert exc.value.status_code == 409
        snapshot = service.get_progress(current, 1, 1, "business", None)
        assert snapshot["earned_points"] == 0
        assert snapshot["stages"][0]["status"] == "pending"


def test_simultaneous_decisions_have_only_one_winner(sessions):
    barrier = Barrier(2)

    def decide(decision):
        with sessions() as db:
            held = service.get_proposal(db, 1)
            barrier.wait(timeout=5)
            assert held.version == 1
            try:
                service.decide_proposal(db, 1, 1, decision)
                return 200, decision
            except HTTPException as exc:
                return exc.status_code, decision

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(decide, ["accepted", "rejected"]))
    assert sorted(status for status, _ in results) == [200, 409]
    with sessions() as db:
        saved = service.get_proposal(db, 1)
        assert saved.status == next(decision for status, decision in results if status == 200)
        assert saved.version == 2


def test_simultaneous_submissions_create_only_one_report(sessions):
    with sessions() as db:
        service.decide_proposal(db, 1, 1, "accepted")
    barrier = Barrier(2)

    def send(_):
        with sessions() as db:
            held = service.get_proposal(db, 1)
            barrier.wait(timeout=5)
            assert held.version == 2
            try:
                service.submit_progress(db, 1, 1, submission())
                return 200
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(send, [1, 2]))
    assert sorted(results) == [200, 409]
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(ProposalMilestone)) == 1
        assert service.get_proposal(db, 1).version == 3


def test_unrelated_integrity_error_is_not_reported_as_duplicate(sessions, monkeypatch):
    with sessions() as db:
        error = IntegrityError("INSERT", {}, ValueError("FOREIGN KEY constraint failed"))

        def fail_commit():
            raise error

        monkeypatch.setattr(db, "commit", fail_commit)
        with pytest.raises(IntegrityError) as exc:
            service.create_proposal(db, 1, ProposalCreate(
                task_id=1, idea="Идея решения", plan="План решения", deadline="Неделя"
            ))
        assert exc.value is error
