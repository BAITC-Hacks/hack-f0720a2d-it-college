"""Сервис чтения профилей студенческих команд."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.teams.models import Team


def list_teams(db: Session) -> list[Team]:
    return list(db.scalars(select(Team).order_by(Team.name)))


def get_team(db: Session, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Команда не найдена")
    return team
