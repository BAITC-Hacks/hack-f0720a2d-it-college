"""Сервис откликов и только ручного принятия или отклонения бизнесом."""

from typing import Literal

from fastapi import HTTPException
from sqlalchemy import MetaData, Table, delete, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.proposals.models import Proposal
from app.modules.proposals.schemas import ProposalCreate
from app.modules.tasks import service as tasks_service
from app.modules.teams import service as teams_service


def delete_for_task(db: Session, task_id: int) -> None:
    """Удаляет отклики и старые записи прогресса в транзакции вызывающего сервиса."""
    connection = db.connection()
    if inspect(connection).has_table("proposal_progress"):
        # Таблица могла остаться от предыдущей версии; миграция или очистка БД не нужны.
        progress = Table(
            "proposal_progress", MetaData(), autoload_with=connection, resolve_fks=False
        )
        proposal_ids = select(Proposal.id).where(Proposal.task_id == task_id)
        db.execute(delete(progress).where(progress.c.proposal_id.in_(proposal_ids)))
    db.execute(delete(Proposal).where(Proposal.task_id == task_id))


def counts_by_task(db: Session, task_ids: list[int]) -> dict[int, int]:
    if not task_ids:
        return {}
    statement = select(Proposal.task_id, func.count(Proposal.id)).where(
        Proposal.task_id.in_(task_ids)
    ).group_by(Proposal.task_id)
    return dict(db.execute(statement).all())


def list_for_user(db: Session, user_id: int, role: str, team_id: int | None) -> list[Proposal]:
    statement = select(Proposal)
    if role == "business":
        statement = statement.where(Proposal.task_id.in_(tasks_service.owned_ids(db, user_id)))
    elif role == "team" and team_id is not None:
        statement = statement.where(Proposal.team_id == team_id)
    else:
        raise HTTPException(status_code=403, detail="Пользователь не связан с командой")
    return list(db.scalars(statement.order_by(Proposal.created_at.desc(), Proposal.id.desc())))


def reopen_proposal(db: Session, proposal_id: int, owner_id: int) -> Proposal:
    """Отменяет только явно выбранное решение владельца, не затрагивая другие отклики."""
    proposal = get_proposal(db, proposal_id)
    tasks_service.require_owner(tasks_service.get_task(db, proposal.task_id), owner_id)
    if proposal.status == "pending":
        raise HTTPException(status_code=409, detail="Отклик уже находится на рассмотрении")
    proposal.status = "pending"
    db.commit()
    db.refresh(proposal)
    return proposal


def get_proposal(db: Session, proposal_id: int) -> Proposal:
    proposal = db.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Отклик не найден")
    return proposal


def create_proposal(db: Session, team_id: int | None, payload: ProposalCreate) -> Proposal:
    if team_id is None:
        raise HTTPException(status_code=403, detail="Пользователь не связан с командой")
    teams_service.get_team(db, team_id)
    task = tasks_service.get_task(db, payload.task_id)
    if task.status != "published":
        raise HTTPException(status_code=409, detail="Отклик можно отправить только на опубликованную задачу")

    proposal = Proposal(team_id=team_id, status="pending", **payload.model_dump())
    db.add(proposal)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Команда уже откликнулась на эту задачу") from exc
    db.refresh(proposal)
    return proposal


def list_task_proposals(db: Session, task_id: int, owner_id: int) -> list[Proposal]:
    task = tasks_service.get_task(db, task_id)
    tasks_service.require_owner(task, owner_id)
    statement = select(Proposal).where(Proposal.task_id == task_id).order_by(Proposal.created_at.desc())
    return list(db.scalars(statement))


def decide_proposal(
    db: Session,
    proposal_id: int,
    owner_id: int,
    decision: Literal["accepted", "rejected"],
) -> Proposal:
    proposal = get_proposal(db, proposal_id)
    task = tasks_service.get_task(db, proposal.task_id)
    tasks_service.require_owner(task, owner_id)
    if proposal.status != "pending":
        raise HTTPException(status_code=409, detail="По этому отклику решение уже принято")
    proposal.status = decision
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return proposal
