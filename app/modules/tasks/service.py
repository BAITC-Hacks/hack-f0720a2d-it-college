"""Бизнес-логика сохранения, рейтинга и статусов задачи."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import MetaData, Table, delete, inspect, select, update
from sqlalchemy.orm import Session

from app.modules.ai import service as ai_service
from app.modules.ai.schemas import CARD_FIELDS
from app.modules.rating import service as rating_service
from app.modules.tasks.models import Task, TaskVerification, TaskRevision, utc_now
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


def to_owner_read(db: Session, task: Task) -> dict:
    data = to_read(task)
    revision = db.get(TaskRevision, task.id)
    if revision:
        data.update(revision.values)
        data["confirmed_fields"] = [field for field in data["confirmed_fields"]
                                    if field not in revision.values]
        data.update(rating_service.calculate(data))
        data["has_pending_changes"] = True
    return data


def read_visible(db: Session, task_id: int, user_id: int | None) -> dict:
    task = get_task(db, task_id)
    if task.owner_id == user_id:
        return to_owner_read(db, task)
    if task.status != "published":
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return to_read(task)


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
    return [to_owner_read(db, task) for task in db.scalars(statement)]


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
    known = {field: getattr(task, field) for field in CARD_FIELDS if getattr(task, field)}
    return ai_service.questions_for_task(db, task.id, task.owner_id, task.raw_text, known)


def build_card(db: Session, task_id: int, owner_id: int, answers: dict[str, str]) -> Task:
    task = get_task(db, task_id)
    require_owner(task, owner_id)
    if task.status == "published":
        raise HTTPException(status_code=409, detail="Опубликованную задачу нельзя заново собирать из ответов")
    version = (task.updated_at, task.status)
    known = {field: getattr(task, field) for field in CARD_FIELDS if getattr(task, field)}
    supplied = {field: value for field, value in answers.items() if value.strip()}
    card = ai_service.build_card_for_task(db, task.id, owner_id, task.raw_text, supplied, known)
    if (task.updated_at, task.status) != version:
        raise HTTPException(409, "Карточка изменилась во время работы AI. Обновите страницу и повторите сборку.")
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
    if task.status == "published":
        revision = db.get(TaskRevision, task.id)
        previous = revision.values if revision else {}
        values = {**previous, **changes}
        values = {field: value for field, value in values.items() if value != getattr(task, field)}
        if values != previous:
            if values:
                revision = revision or TaskRevision(task_id=task.id)
                revision.values = values
                db.add(revision)
            elif revision:
                db.delete(revision)
            task.updated_at = utc_now()
        return _save(db, task)
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
        ai_service.delete_for_task(db, task_id)
        connection = db.connection()
        for name in inspect(connection).get_table_names():
            if name.startswith("legacy_task_revisions_v1"):
                archive = Table(name, MetaData(), autoload_with=connection, resolve_fks=False)
                db.execute(delete(archive).where(archive.c.task_id == task_id))
        revision = db.get(TaskRevision, task_id)
        if revision:
            db.delete(revision)
            db.flush()
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
    revision = db.get(TaskRevision, task.id)
    if revision:
        for field, value in revision.values.items():
            setattr(task, field, value)
        db.delete(revision)
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
