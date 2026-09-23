"""Подключение SQLAlchemy, фабрика сессий и регистрация моделей."""

from __future__ import annotations

from collections.abc import Generator
from collections import defaultdict
from datetime import datetime, timezone
import json

from sqlalchemy import create_engine, delete, event, inspect, select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine_options(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """Включает существующие FK на каждом соединении без изменения схемы БД."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


settings = get_settings()
engine = create_engine(settings.database_url, **_engine_options(settings.database_url))
if engine.dialect.name == "sqlite":
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def load_models() -> None:
    """Регистрирует таблицы, не создавая межмодульных импортов моделей."""

    from app.modules.ai import models as ai_models  # noqa: F401
    from app.modules.proposals import models as proposal_models  # noqa: F401
    from app.modules.tasks import models as task_models  # noqa: F401
    from app.modules.teams import models as team_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401


def create_tables() -> None:
    load_models()
    if engine.dialect.name != "sqlite":
        Base.metadata.create_all(bind=engine)
        return
    with engine.begin() as connection:
        # sqlite3's legacy transaction mode otherwise commits DDL before the first
        # INSERT. Keep archive, replacement and data copy in one transaction.
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        revisions, progress = _prepare_legacy_tables(connection)
        Base.metadata.create_all(bind=connection)
        _add_column(connection, "proposals", "version", "INTEGER NOT NULL DEFAULT 1")
        _add_column(connection, "ai_connections", "provider", "VARCHAR(20) NOT NULL DEFAULT 'compatible'")
        if revisions:
            target = Base.metadata.tables["task_revisions"]
            connection.execute(target.insert(), [
                {"task_id": row["task_id"], "values": _revision_values(row)} for row in revisions
            ])
        _restore_legacy_progress(connection, progress)


def _columns(connection, table_name: str) -> set[str]:
    inspector = inspect(connection)
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _add_column(connection, table_name: str, column_name: str, definition: str) -> None:
    columns = _columns(connection, table_name)
    if columns and column_name not in columns:
        connection.exec_driver_sql(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {definition}')


def _archive_table(connection, table_name: str, *, drop: bool = True) -> list[dict]:
    """Preserve every original column and row; archive FKs must not block deletion."""
    rows = [dict(row) for row in connection.exec_driver_sql(f'SELECT * FROM "{table_name}"').mappings()]
    archive = f"legacy_{table_name}_v1"
    suffix = 2
    while inspect(connection).has_table(archive):
        archive = f"legacy_{table_name}_v1_{suffix}"
        suffix += 1
    connection.exec_driver_sql(f'CREATE TABLE "{archive}" AS SELECT * FROM "{table_name}"')
    if drop:
        connection.exec_driver_sql(f'DROP TABLE "{table_name}"')
    return rows


def _prepare_legacy_tables(connection) -> tuple[list[dict], list[tuple[str, dict]]]:
    revisions = []
    progress = []
    columns = _columns(connection, "task_revisions")
    if columns and ("values" not in columns or "payload" in columns or "token" in columns):
        revisions = _archive_table(connection, "task_revisions")
    milestone_columns = {"proposal_id", "summary", "link", "points", "submitted_at", "confirmed_at"}
    columns = _columns(connection, "proposal_milestones")
    if columns and ("stage" in columns or not milestone_columns.issubset(columns)):
        progress.extend(("milestone", row) for row in _archive_table(connection, "proposal_milestones"))
    progress_columns = {"id", "proposal_id", "description", "link", "points", "submitted_at", "confirmed_at", "confirmed_by"}
    columns = _columns(connection, "proposal_progress")
    if columns and ("percent" in columns or not progress_columns.issubset(columns)):
        progress.extend(("progress", row) for row in _archive_table(connection, "proposal_progress"))
    return revisions, progress


def _revision_values(row: dict) -> dict:
    value = row.get("values") if row.get("values") is not None else row.get("payload", {})
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("Legacy task revision must contain a JSON object")
    return value


def _legacy_time(value) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value is None:
        raise ValueError("Legacy progress is missing its submission timestamp")
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _legacy_result(row: dict) -> dict:
    """Project older progress without changing the rewards it already earned."""
    stage_info = {
        "research": ("Исследование", 20),
        "prototype": ("Прототип", 30),
        "final": ("Финальное решение", 50),
    }
    submitted = _legacy_time(row.get("submitted_at") or row.get("updated_at"))
    if "stage" in row:
        title, weight = stage_info.get(row["stage"], (row["stage"], 0))
        status = {"confirmed": "подтверждено", "pending": "ожидает проверки", "rejected": "возвращено на доработку"}.get(row["status"], row["status"])
        description = f"{title} — {status}\n{row.get('description') or ''}"
        points = weight if row["status"] == "confirmed" else 0
        confirmed = _legacy_time(row.get("reviewed_at") or row.get("submitted_at")) if points else None
        if row.get("review_comment"):
            description += "\nКомментарий проверяющего: " + row["review_comment"]
    else:
        description = row.get("description") or row.get("summary") or row.get("comment") or "Сохранённый результат"
        if "percent" in row:
            description = f"Ранее сохранённый прогресс: {row['percent']}%\n{description}"
        points = int(row.get("points") or 0)
        confirmed = _legacy_time(row.get("confirmed_at") or submitted) if points else None
    if row.get("link"):
        description += "\nМатериалы: " + row["link"]
    return {"summary": description, "points": points, "submitted_at": submitted,
            "confirmed_at": confirmed, "link": row.get("link")}


def _restore_legacy_progress(connection, progress: list[tuple[str, dict]]) -> None:
    if not progress:
        return
    grouped = defaultdict(list)
    for _, row in progress:
        grouped[row["proposal_id"]].append(_legacy_result(row))
    milestone = Base.metadata.tables["proposal_milestones"]
    current_progress = Base.metadata.tables["proposal_progress"]
    current_progress_archived = False
    for proposal_id, rows in grouped.items():
        existing = connection.execute(select(milestone).where(milestone.c.proposal_id == proposal_id)).mappings().first()
        if existing:
            rows.append(_legacy_result(dict(existing)))
        current = connection.execute(select(current_progress).where(current_progress.c.proposal_id == proposal_id)).mappings().first()
        if current:
            # Keep both previously awarded results visible instead of allowing the
            # ORM's preferred single-stage row to hide the migrated achievements.
            if not current_progress_archived:
                _archive_table(connection, "proposal_progress", drop=False)
                current_progress_archived = True
            rows.append(_legacy_result(dict(current)))
            connection.execute(delete(current_progress).where(current_progress.c.proposal_id == proposal_id))
        rows.sort(key=lambda item: item["submitted_at"])
        confirmations = [row["confirmed_at"] for row in rows if row["confirmed_at"] is not None]
        values = {
            "summary": "\n\n".join(row["summary"] for row in rows),
            "points": sum(row["points"] for row in rows),
            "submitted_at": rows[0]["submitted_at"],
            "confirmed_at": max(confirmations) if confirmations else None,
            "link": next((row["link"] for row in reversed(rows) if row["link"]), None),
        }
        if existing:
            connection.execute(milestone.update().where(milestone.c.proposal_id == proposal_id).values(**values))
        else:
            connection.execute(milestone.insert().values(proposal_id=proposal_id, **values))
