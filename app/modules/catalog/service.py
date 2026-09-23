"""Сервис фильтрации каталога и сортировки задач по рейтингу."""

from sqlalchemy.orm import Session

from app.modules.tasks import service as tasks_service


def get_catalog(db: Session, industry: str | None = None, level: str | None = None) -> list[dict]:
    return tasks_service.list_published(db, industry=industry, level=level)
