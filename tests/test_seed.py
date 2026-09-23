"""Проверка объёма, полноты и безопасного повторного seed в изолированной БД."""

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.modules.proposals.models import Proposal
from app.modules.rating.service import FIELD_WEIGHTS, calculate
from app.modules.tasks.models import Task, TaskVerification
from app.modules.teams.models import Team
from app.modules.users.models import User
from app.seed import seed as seed_module


def configure_seed(monkeypatch, db):
    """Используем только in-memory engine фикстуры, не рабочую SQLite-базу."""
    monkeypatch.setattr(seed_module, "SessionLocal", sessionmaker(bind=db.get_bind()))
    monkeypatch.setattr(seed_module, "create_tables", lambda: None)


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_seed_has_required_volume_diverse_drafts_and_all_catalog_levels(db, monkeypatch):
    configure_seed(monkeypatch, db)
    seed_module.seed()

    assert {model.__name__: count(db, model) for model in (User, Task, Team, Proposal)} == {
        "User": 7, "Task": 10, "Team": 5, "Proposal": 5,
    }
    drafts = list(db.scalars(select(Task).where(Task.status == "draft").order_by(Task.id)))
    assert len(drafts) == 5
    assert [sum(bool(getattr(task, field)) for field in FIELD_WEIGHTS) for task in drafts] == [0, 2, 4, 6, 8]
    assert all(task.raw_text and task.industry for task in drafts)
    assert all(task.score == 0 for task in drafts)
    assert all(db.get(TaskVerification, task.id) is None for task in drafts)
    assert [calculate(task)["potential_score"] for task in drafts] == [0, 20, 50, 75, 100]

    cards = list(db.scalars(select(Task).where(Task.status == "published").order_by(Task.id)))
    assert {task.id: task.score for task in cards} == {6: 100, 7: 95, 8: 37.5, 9: 85, 10: 60}
    assert {task.level for task in cards} == {"draft", "working", "ready", "priority"}
    assert count(db, TaskVerification) == 5
    for task in cards:
        verification = db.get(TaskVerification, task.id)
        values = {field: getattr(task, field) for field in FIELD_WEIGHTS}
        assert verification.values == values
        result = calculate({**values, "confirmed_fields": [field for field, value in values.items() if value]})
        assert task.score == result["score"]
        assert task.level == result["level"]
        assert task.breakdown == result["breakdown"]

    for card in seed_module.read_json("cards.json"):
        assert set(FIELD_WEIGHTS) <= set(card)
        assert card["score"] == db.get(Task, card["id"]).score
    for team in db.scalars(select(Team)):
        assert team.name and team.interests and team.skills and team.tech
    for proposal in db.scalars(select(Proposal)):
        assert db.get(Team, proposal.team_id) is not None
        assert db.get(Task, proposal.task_id).status == "published"
        assert proposal.idea and proposal.plan and proposal.deadline and proposal.link


def test_repeated_seed_preserves_user_changes(db, monkeypatch):
    configure_seed(monkeypatch, db)
    seed_module.seed()
    task = db.get(Task, 1)
    task.title = "Изменение участника команды"
    proposal = db.get(Proposal, 1)
    proposal.status = "rejected"
    db.commit()
    before = {
        model.__name__: count(db, model)
        for model in (User, Task, Team, Proposal, TaskVerification)
    }

    seed_module.seed()
    db.expire_all()
    assert db.get(Task, 1).title == "Изменение участника команды"
    assert db.get(Proposal, 1).status == "rejected"
    assert {
        model.__name__: count(db, model)
        for model in (User, Task, Team, Proposal, TaskVerification)
    } == before


def test_seed_does_not_replace_an_existing_partial_database(db, monkeypatch):
    configure_seed(monkeypatch, db)
    db.add(User(id=101, name="Существующий пользователь", role="business"))
    db.commit()
    seed_module.seed()
    assert count(db, User) == 1
    assert db.get(User, 101).name == "Существующий пользователь"
    assert count(db, Task) == count(db, Team) == count(db, Proposal) == 0
