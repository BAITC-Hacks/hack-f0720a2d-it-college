import sqlite3
from datetime import datetime, timezone

from app.errors import ServiceError


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_task(connection: sqlite3.Connection, task_id: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise ServiceError(404, "task_not_found", "Карточка задания не найдена")
    return row


def require_draft(row: sqlite3.Row) -> None:
    if row["status"] != "draft":
        raise ServiceError(
            409, "task_finalized", "Финальная карточка уже оценена и не может быть изменена"
        )


def require_version(row: sqlite3.Row, expected_version: int) -> None:
    if row["version"] != expected_version:
        raise ServiceError(
            409, "version_conflict", "Карточка изменилась. Загрузите актуальную версию"
        )
