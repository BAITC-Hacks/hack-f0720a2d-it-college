"""Подключение SQLAlchemy, фабрика сессий и регистрация моделей."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
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
    Base.metadata.create_all(bind=engine)
