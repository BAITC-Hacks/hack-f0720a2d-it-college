"""Настройки подключения бизнеса и кэш анализа конкретной версии карточки."""

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AIConnection(Base):
    __tablename__ = "ai_connections"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    base_url: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(240), default="")
    api_key: Mapped[str] = mapped_column(Text, default="")
    response_format: Mapped[str] = mapped_column(String(20), default="auto")


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
