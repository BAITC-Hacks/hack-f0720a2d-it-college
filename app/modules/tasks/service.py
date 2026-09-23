"""Бизнес-логика сохранения, рейтинга и статусов задачи."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ai import service as ai_service
from app.modules.rating import service as rating_service
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import DraftCreate, TaskPatch


def _recalculate(task: Task) -> dict:
    rating = rating_service.calculate(task)
    task.score = rating["score"]
    task.level = rating["level"]
    task.breakdown = rating["breakdown"]
    return rating


def _save(db: Session, task: Task) -> Task:
    _recalculate(task)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def to_read(task: Task) -> dict:
    data = {column.name: getattr(task, column.name) for column in Task.__table__.columns}
    rating = rating_service.calculate(task)
    data["level_label"] = rating["level_label"]
    data["missing"] = rating["missing"]
    return data


def create_draft(db: Session, owner_id: int, payload: DraftCreate) -> Task:
    task = Task(
        owner_id=owner_id,
        title=payload.title,
        industry=payload.industry,
        raw_text=payload.raw_text,
    )
    return _save(db, task)


def get_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task


def list_owned(db: Session, owner_id: int) -> list[dict]:
    """Карточки текущего бизнеса, включая неопубликованные черновики."""
    statement = select(Task).where(Task.owner_id == owner_id).order_by(Task.updated_at.desc(), Task.id.desc())
    return [to_read(task) for task in db.scalars(statement)]


def owned_ids(db: Session, owner_id: int) -> list[int]:
    return list(db.scalars(select(Task.id).where(Task.owner_id == owner_id)))


def list_published(
    db: Session,
    industry: str | None = None,
    level: str | None = None,
) -> list[dict]:
    statement = select(Task).where(Task.status == "published")
    if industry:
        statement = statement.where(Task.industry == industry)
    if level:
        statement = statement.where(Task.level == level)
    statement = statement.order_by(Task.score.desc(), Task.created_at.desc())
    return [to_read(task) for task in db.scalars(statement)]


def require_owner(task: Task, user_id: int) -> None:
    if task.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Действие доступно только владельцу задачи")


def get_questions(db: Session, task_id: int) -> dict:
    task = get_task(db, task_id)
    return ai_service.analyze_draft(task.raw_text)


def build_card(db: Session, task_id: int, owner_id: int, answers: dict[str, str]) -> Task:
    task = get_task(db, task_id)
    require_owner(task, owner_id)
    if task.status == "published":
        raise HTTPException(status_code=409, detail="Опубликованную задачу нельзя заново собирать из ответов")
    card = ai_service.build_card(task.raw_text, answers)
    for field, value in card.items():
        if value is not None:
            setattr(task, field, value)
    task.status = "draft"
    return _save(db, task)


def update_task(db: Session, task_id: int, owner_id: int, payload: TaskPatch) -> Task:
    task = get_task(db, task_id)
    require_owner(task, owner_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    if task.status == "confirmed" and payload.model_fields_set:
        task.status = "draft"
    return _save(db, task)


def confirm_task(db: Session, task_id: int, owner_id: int) -> Task:
    task = get_task(db, task_id)
    require_owner(task, owner_id)
    if task.status == "published":
        raise HTTPException(status_code=409, detail="Задача уже опубликована")
    task.status = "confirmed"
    return _save(db, task)


def publish_task(db: Session, task_id: int, owner_id: int) -> Task:
    task = get_task(db, task_id)
    require_owner(task, owner_id)
    if task.status != "confirmed":
        raise HTTPException(status_code=409, detail="Сначала подтвердите карточку задачи")
    task.status = "published"
    return _save(db, task)
