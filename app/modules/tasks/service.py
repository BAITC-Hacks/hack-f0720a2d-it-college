"""Бизнес-логика сохранения, рейтинга и статусов задачи."""

from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.ai import service as ai_service
from app.modules.rating import service as rating_service
from app.modules.tasks.models import Task, TaskRevision
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


def to_read(task: Task, *, has_pending_changes: bool = False) -> dict:
    data = {column.name: getattr(task, column.name) for column in Task.__table__.columns}
    rating = rating_service.calculate(task)
    data["level_label"] = rating["level_label"]
    data["missing"] = rating["missing"]
    data["has_pending_changes"] = has_pending_changes
    data["revision_token"] = None
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


def get_visible_task(db: Session, task_id: int, user_id: int | None, role: str | None) -> Task:
    task = get_task(db, task_id)
    if task.status != "published":
        if user_id is None:
            raise HTTPException(status_code=401, detail="Передайте заголовок X-User-Id")
        if role != "business":
            raise HTTPException(status_code=403, detail="Черновик доступен только владельцу задачи")
        require_owner(task, user_id)
    return task


def _preview(task: Task, revision: TaskRevision | None) -> dict:
    data = to_read(task, has_pending_changes=revision is not None)
    if revision is not None:
        data.update(revision.payload)
        data.update(rating_service.calculate(data))
        data["revision_token"] = revision.token
    return data


def get_for_edit(db: Session, task_id: int, owner_id: int) -> dict:
    task = get_task(db, task_id)
    require_owner(task, owner_id)
    return _preview(task, db.get(TaskRevision, task_id))


def list_owned(db: Session, owner_id: int) -> list[dict]:
    """Карточки текущего бизнеса, включая неопубликованные черновики."""
    statement = select(Task).where(Task.owner_id == owner_id).order_by(Task.updated_at.desc(), Task.id.desc())
    tasks = list(db.scalars(statement))
    pending_ids = set(db.scalars(select(TaskRevision.task_id).where(
        TaskRevision.task_id.in_([task.id for task in tasks])
    )))
    return [to_read(task, has_pending_changes=task.id in pending_ids) for task in tasks]


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


def _revision_conflict() -> HTTPException:
    return HTTPException(status_code=409, detail="Изменения уже обновлены или подтверждены. Откройте карточку заново.")


def _save_revision(db: Session, task: Task, changes: dict) -> dict:
    try:
        # Блокируем запись до конца транзакции и не затираем опубликованную версию,
        # если её успел подтвердить другой запрос после чтения карточки.
        current = db.execute(update(Task).where(
            Task.id == task.id, Task.updated_at == task.updated_at, Task.status == "published"
        ).values(updated_at=task.updated_at).execution_options(synchronize_session=False))
        if current.rowcount != 1:
            raise _revision_conflict()
        revision = db.get(TaskRevision, task.id, populate_existing=True)
        values = {**(revision.payload if revision else {}), **changes}
        values = {field: value for field, value in values.items() if getattr(task, field) != value}
        if values:
            if revision is None:
                revision = TaskRevision(task_id=task.id, payload=values, token=str(uuid4()))
                db.add(revision)
            elif values != revision.payload:
                revision.payload = values
                revision.token = str(uuid4())
        elif revision is not None:
            db.delete(revision)
            revision = None
        db.commit()
        return _preview(task, revision)
    except IntegrityError as exc:
        db.rollback()
        raise _revision_conflict() from exc
    except Exception:
        db.rollback()
        raise


def update_task(db: Session, task_id: int, owner_id: int, payload: TaskPatch) -> dict:
    task = get_task(db, task_id)
    require_owner(task, owner_id)
    changes = payload.model_dump(exclude_unset=True)
    if task.status == "published":
        return _save_revision(db, task, changes)
    for field, value in changes.items():
        setattr(task, field, value)
    if task.status == "confirmed" and payload.model_fields_set:
        task.status = "draft"
    return to_read(_save(db, task))


def confirm_changes(db: Session, task_id: int, owner_id: int, revision_token: str) -> Task:
    task = get_task(db, task_id)
    require_owner(task, owner_id)
    if task.status != "published":
        raise HTTPException(status_code=409, detail="Подтверждение изменений доступно опубликованной карточке")
    try:
        revision = db.get(TaskRevision, task_id, populate_existing=True)
        if revision is None or revision.token != revision_token:
            raise _revision_conflict()
        changes = dict(revision.payload)
        claimed = db.execute(delete(TaskRevision).where(
            TaskRevision.task_id == task_id, TaskRevision.token == revision_token
        ))
        if claimed.rowcount != 1:
            raise _revision_conflict()
        db.refresh(task)
        for field, value in changes.items():
            setattr(task, field, value)
        _recalculate(task)
        db.commit()
        db.refresh(task)
        return task
    except Exception:
        db.rollback()
        raise


def delete_task(db: Session, task_id: int, owner_id: int) -> None:
    """Удаляет карточку и все её отклики целиком либо сохраняет всё при ошибке."""
    # Локальный импорт разрывает цикл: отклики уже используют публичный сервис задач.
    from app.modules.proposals import service as proposals_service

    task = get_task(db, task_id)
    require_owner(task, owner_id)
    try:
        db.execute(delete(TaskRevision).where(TaskRevision.task_id == task_id))
        proposals_service.delete_for_task(db, task_id)
        db.delete(task)
        db.commit()
    except Exception:
        db.rollback()
        raise


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
