"""Сервис фильтрации каталога и сортировки задач по рейтингу."""

from sqlalchemy.orm import Session

from app.modules.tasks import service as tasks_service
from app.modules.proposals import service as proposals_service


def get_catalog(db: Session, industry: str | None = None, level: str | None = None) -> list[dict]:
    tasks = tasks_service.list_published(db, industry=industry, level=level)
    counts = proposals_service.counts_by_task(db, [task["id"] for task in tasks])
    return [dict(task, proposals_count=counts.get(task["id"], 0)) for task in tasks]
