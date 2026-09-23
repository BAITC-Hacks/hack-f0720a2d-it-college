"""SQLAlchemy-модель черновика и опубликованной карточки задачи."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'published')",
            name="ck_tasks_status",
        ),
        CheckConstraint(
            "level IN ('draft', 'working', 'ready', 'priority')",
            name="ck_tasks_level",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(240), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    need: Mapped[str | None] = mapped_column(Text, nullable=True)
    users: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraints: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    success_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    verification: Mapped[TaskVerification | None] = relationship(
        lazy="selectin", cascade="all, delete-orphan", uselist=False
    )


class TaskVerification(Base):
    """Снимок ручного подтверждения; отдельная таблица сохраняет совместимость БД."""

    __tablename__ = "task_verifications"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    values: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class TaskRevision(Base):
    """Неподтверждённые дополнения опубликованной карточки."""

    __tablename__ = "task_revisions"
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    values: Mapped[dict] = mapped_column(JSON, default=dict)
