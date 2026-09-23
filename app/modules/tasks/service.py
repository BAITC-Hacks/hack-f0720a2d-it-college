"""Бизнес-логика сохранения, рейтинга и статусов задачи."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.ai import service as ai_service
from app.modules.rating import service as rating_service
from app.modules.tasks.models import Task, TaskVerification, utc_now
from app.modules.tasks.schemas import DraftCreate, TaskPatch


def _rating(task: Task) -> dict:
    values = {field: getattr(task, field) for field in rating_service.FIELD_WEIGHTS}
    snapshot = task.verification.values if task.verification else (
        values if task.status in {"confirmed", "published"} else {}
    )
    # Совместимость: прежний published/confirmed уже означал ручное подтверждение.
    values["confirmed_fields"] = [field for field in rating_service.FIELD_WEIGHTS
                                 if values[field] and snapshot.get(field) == values[field]]
    return rating_service.calculate(values)


def _preserve_confirmation(task: Task) -> None:
    if task.verification is None:
        snapshot = ({field: getattr(task, field) for field in rating_service.FIELD_WEIGHTS}
                    if task.status in {"confirmed", "published"} else {})
        task.verification = TaskVerification(values=snapshot)


def _recalculate(task: Task) -> dict:
    rating = _rating(task)
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


def _lock_current(db: Session, task: Task) -> None:
    """Короткая условная запись защищает подтверждение от параллельной правки.

    SQLite удерживает блокировку записи до commit. Старый экземпляр ORM не
    сможет подтвердить/опубликовать значения, уже изменённые другой сессией.
    """
    result = db.execute(
        update(Task).where(Task.id == task.id, Task.updated_at == task.updated_at)
        .values(updated_at=task.updated_at),
        execution_options={"synchronize_session": False},
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Карточка уже изменена. Обновите страницу и повторите действие")


def to_read(task: Task) -> dict:
    data = {column.name: getattr(task, column.name) for column in Task.__table__.columns}
    data.update(_rating(task))
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
    # Совместимые старые БД могут хранить прежний кеш рейтинга. Для небольшого
    # MVP сортируем и фильтруем по тому же актуальному расчёту, который видит UI.
    tasks = [to_read(task) for task in db.scalars(statement)]
    if level:
        tasks = [task for task in tasks if task["level"] == level]
    return sorted(tasks, key=lambda task: (task["score"], task["created_at"], task["id"]), reverse=True)


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
    _lock_current(db, task)
    _preserve_confirmation(task)
    for field, value in card.items():
        if value is not None:
            setattr(task, field, value)
    task.status = "draft"
    return _save(db, task)


def update_task(db: Session, task_id: int, owner_id: int, payload: TaskPatch) -> Task:
    task = get_task(db, task_id)
    require_owner(task, owner_id)
    _lock_current(db, task)
    _preserve_confirmation(task)
    changes = payload.model_dump(exclude_unset=True)
    changed = any(getattr(task, field) != value for field, value in changes.items())
    for field, value in changes.items():
        setattr(task, field, value)
    if task.status == "confirmed" and changed:
        task.status = "draft"
    return _save(db, task)


def delete_task(db: Session, task_id: int, owner_id: int) -> None:
    """Атомарно удаляет карточку, снимок подтверждения, отклики и их прогресс."""
    # Локальный импорт разрывает цикл: отклики уже используют публичный сервис задач.
    from app.modules.proposals import service as proposals_service

    task = get_task(db, task_id)
    require_owner(task, owner_id)
    try:
        _lock_current(db, task)
        proposals_service.delete_for_task(db, task_id)
        db.delete(task)
        db.commit()
    except Exception:
        db.rollback()
        raise


def confirm_task(db: Session, task_id: int, owner_id: int, expected_updated_at=None) -> Task:
    task = get_task(db, task_id)
    require_owner(task, owner_id)
    if expected_updated_at is not None and task.updated_at.replace(tzinfo=None) != expected_updated_at.replace(tzinfo=None):
        raise HTTPException(status_code=409, detail="Карточка уже изменена. Обновите страницу и проверьте новые сведения")
    _lock_current(db, task)
    _preserve_confirmation(task)
    task.verification.values = {field: getattr(task, field) for field in rating_service.FIELD_WEIGHTS}
    task.verification.confirmed_at = utc_now()
    if task.status != "published":
        task.status = "confirmed"
    task.updated_at = utc_now()
    return _save(db, task)


def publish_task(db: Session, task_id: int, owner_id: int) -> Task:
    task = get_task(db, task_id)
    require_owner(task, owner_id)
    _lock_current(db, task)
    if task.status != "confirmed":
        raise HTTPException(status_code=409, detail="Сначала подтвердите карточку задачи")
    task.status = "published"
    return _save(db, task)
