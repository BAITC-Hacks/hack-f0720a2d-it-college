"""SQLAlchemy-модели отклика команды и подтверждаемого результата одного этапа."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name="ck_proposals_status",
        ),
        UniqueConstraint("task_id", "team_id", name="uq_proposals_task_team"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False, index=True)
    idea: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[str] = mapped_column(Text, nullable=False)
    deadline: Mapped[str] = mapped_column(String(120), nullable=False)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    progress: Mapped[ProposalProgress | None] = relationship(
        back_populates="proposal", uselist=False, lazy="selectin"
    )


class ProposalProgress(Base):
    """Один фактический этап по отклику; баллы появляются после решения владельца."""

    __tablename__ = "proposal_progress"
    __table_args__ = (
        CheckConstraint("points >= 0", name="ck_progress_nonnegative_points"),
        CheckConstraint(
            "(confirmed_at IS NULL AND confirmed_by IS NULL AND points = 0) OR "
            "(confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL AND points > 0)",
            name="ck_progress_confirmation",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(
        ForeignKey("proposals.id"), nullable=False, unique=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    points: Mapped[int] = mapped_column(default=0, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    proposal: Mapped[Proposal] = relationship(back_populates="progress")

    @property
    def status(self) -> str:
        return "confirmed" if self.confirmed_at is not None else "submitted"
