import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

import pytest

from app.database import Database
from app.errors import ServiceError
from app.schemas import CardFields, FinalizeRequest, TaskCreate, TaskPatch
from app.services import evaluation as evaluation_module
from app.services.evaluation import EvaluationService, readiness_for_score, score_card
from app.services.tasks import TaskService


@pytest.mark.parametrize("score,expected", [
    (0, "draft"), (39, "draft"), (40, "working"), (69, "working"),
    (70, "ready"), (89, "ready"), (90, "priority"), (100, "priority"),
])
def test_readiness_boundaries(score, expected):
    assert readiness_for_score(score) == expected


def test_partial_points_and_placeholders():
    result = score_card(CardFields(
        context="Есть описание процесса", need="TBD", data="нет данных",
        contact="coordinator@example.com", interaction_format="   ",
        success_criteria="Проверка по согласованному набору из 100 заявок",
    ))
    assert sum(item.points for item in result) == 30
    assert result[0].points == 10
    assert result[1].points == 0
    assert result[-1].points == 5


def test_concurrent_finalization_computes_exactly_once(settings, complete_card, monkeypatch):
    database = Database(settings.database_path)
    database.initialize()
    task = TaskService(database).create(TaskCreate(**complete_card))
    barrier, counter_lock, calls = Barrier(8), Lock(), []
    original = evaluation_module.score_card

    def count_score(card):
        with counter_lock:
            calls.append(True)
        return original(card)

    monkeypatch.setattr(evaluation_module, "score_card", count_score)

    def finalize(_):
        # Independent service/connection instances, as with several application workers.
        service = EvaluationService(Database(settings.database_path))
        barrier.wait()
        return service.finalize_once(task.id, FinalizeRequest(confirmed=True, expected_version=1))

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(finalize, range(8)))
    assert len(calls) == 1
    assert len({result.id for result in results}) == 1
    assert all(result == results[0] for result in results)
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0] == 1


def test_failed_finalization_rolls_back_both_card_and_evaluation(settings, complete_card):
    database = Database(settings.database_path)
    database.initialize()
    task = TaskService(database).create(TaskCreate(**complete_card))
    with database.connection(write=True) as connection:
        connection.execute("""CREATE TRIGGER test_fail_finalize BEFORE UPDATE ON tasks
            BEGIN SELECT RAISE(ABORT, 'Simulated storage failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        EvaluationService(database).finalize_once(task.id, FinalizeRequest(confirmed=True, expected_version=1))
    assert TaskService(database).get(task.id).status == "draft"
    with pytest.raises(ServiceError) as error:
        EvaluationService(database).get(task.id)
    assert error.value.code == "evaluation_not_found"


def test_final_card_and_evaluation_cannot_be_rewritten_in_database(settings, complete_card):
    database = Database(settings.database_path)
    database.initialize()
    task = TaskService(database).create(TaskCreate(**complete_card))
    EvaluationService(database).finalize_once(task.id, FinalizeRequest(confirmed=True, expected_version=1))
    for statement in [
        "UPDATE tasks SET title='changed' WHERE id=?",
        "DELETE FROM tasks WHERE id=?",
        "UPDATE evaluations SET score=0 WHERE task_id=?",
        "DELETE FROM evaluations WHERE task_id=?",
    ]:
        with pytest.raises(sqlite3.IntegrityError):
            with database.connection(write=True) as connection:
                connection.execute(statement, (task.id,))


def test_edit_racing_with_finalization_cannot_change_rated_snapshot(settings, complete_card):
    database = Database(settings.database_path)
    database.initialize()
    task = TaskService(database).create(TaskCreate(**complete_card))
    barrier = Barrier(2)

    def edit():
        barrier.wait()
        try:
            return TaskService(database).update(task.id, TaskPatch(expected_version=1, data=""))
        except ServiceError as error:
            return error.code

    def finalize():
        barrier.wait()
        try:
            return EvaluationService(database).finalize_once(task.id, FinalizeRequest(confirmed=True, expected_version=1))
        except ServiceError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        edit_future, final_future = executor.submit(edit), executor.submit(finalize)
        edited, evaluated = edit_future.result(), final_future.result()
    current = TaskService(database).get(task.id)
    if evaluated == "version_conflict":
        assert current.status == "draft" and current.version == 2
        assert current.data == "" and current.score is None
    else:
        assert edited == "task_finalized"
        assert current.status == "finalized" and current.score == 100
        assert evaluated.card_snapshot.data == current.data
