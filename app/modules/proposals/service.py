"""Сервис откликов и только ручного принятия или отклонения бизнесом."""

from typing import Literal

from fastapi import HTTPException
from sqlalchemy import MetaData, Table, delete, func, inspect, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.modules.proposals.models import Proposal, ProposalProgress, ProposalMilestone, utc_now
from app.modules.proposals.schemas import ProgressSubmit, ProposalCreate
from app.modules.tasks import service as tasks_service
from app.modules.teams import service as teams_service


PROGRESS_POINTS = 10


def _lock_current(db: Session, proposal: Proposal) -> None:
    """Не позволяет устаревшему кабинету отменить решение или подтвердить другой отчёт."""
    version = proposal.version
    changed = db.execute(
        update(Proposal).where(Proposal.id == proposal.id, Proposal.version == version)
        .values(version=version + 1), execution_options={"synchronize_session": False},
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Отклик уже изменён. Обновите страницу и повторите действие")
    set_committed_value(proposal, "version", version + 1)


def delete_for_task(db: Session, task_id: int) -> None:
    """Удаляет отклики и старые записи прогресса в транзакции вызывающего сервиса."""
    connection = db.connection()
    proposal_ids = select(Proposal.id).where(Proposal.task_id == task_id)
    for name in inspect(connection).get_table_names():
        if name.startswith(("legacy_proposal_milestones_v1", "legacy_proposal_progress_v1")):
            archive = Table(name, MetaData(), autoload_with=connection, resolve_fks=False)
            db.execute(delete(archive).where(archive.c.proposal_id.in_(proposal_ids)))
    if inspect(connection).has_table("proposal_milestones"):
        db.execute(delete(ProposalMilestone).where(ProposalMilestone.proposal_id.in_(proposal_ids)))
    if inspect(connection).has_table("proposal_progress"):
        # Для удаления достаточно proposal_id: поддерживаем текущую таблицу
        # и старую схему percent/comment без её миграции или очистки чужих строк.
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
    _lock_current(db, proposal)
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
    _lock_current(db, proposal)
    proposal.status = decision
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return proposal


def submit_progress(
    db: Session, proposal_id: int, team_id: int | None, payload: ProgressSubmit
) -> Proposal:
    """Сохраняет один результат выбранной команды, пока бизнес его не подтвердил."""
    proposal = get_proposal(db, proposal_id)
    if team_id is None or proposal.team_id != team_id:
        raise HTTPException(status_code=403, detail="Результат может отправить только команда этого отклика")
    if proposal.status != "accepted":
        raise HTTPException(status_code=409, detail="Сначала бизнес должен выбрать команду")
    progress = proposal.progress
    if progress is not None and progress.confirmed_at is not None:
        raise HTTPException(status_code=409, detail="Подтверждённый результат нельзя изменять")
    _lock_current(db, proposal)
    if progress is None:
        proposal.progress = ProposalProgress(**payload.model_dump())
    else:
        model = type(progress)
        key = model.proposal_id if isinstance(progress, ProposalMilestone) else model.id
        values = payload.model_dump()
        if isinstance(progress, ProposalMilestone):
            values["summary"] = values.pop("description")
        changed = db.execute(
            update(model)
            .where(key == progress.id, model.confirmed_at.is_(None))
            .values(**values, submitted_at=utc_now())
        )
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="Результат уже подтверждён; обновите страницу")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Результат уже сохранён; обновите страницу") from exc
    db.refresh(proposal)
    return proposal


def confirm_progress(db: Session, proposal_id: int, owner_id: int) -> Proposal:
    """Начисляет фиксированные баллы один раз, только за вручную подтверждённый этап."""
    proposal = get_proposal(db, proposal_id)
    tasks_service.require_owner(tasks_service.get_task(db, proposal.task_id), owner_id)
    if proposal.status != "accepted":
        raise HTTPException(status_code=409, detail="Подтвердить результат можно только выбранной команды")
    progress = proposal.progress
    if progress is None:
        raise HTTPException(status_code=409, detail="Команда ещё не отправила результат этапа")
    _lock_current(db, proposal)
    model = type(progress)
    key = model.proposal_id if isinstance(progress, ProposalMilestone) else model.id
    values = {"points": PROGRESS_POINTS, "confirmed_at": utc_now()}
    if isinstance(progress, ProposalProgress):
        values["confirmed_by"] = owner_id
    changed = db.execute(
        update(model)
        .where(key == progress.id, model.confirmed_at.is_(None))
        .values(**values)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Результат уже подтверждён, баллы начислены")
    db.commit()
    db.refresh(proposal)
    return proposal


def reject_progress(db: Session, proposal_id: int, owner_id: int) -> Proposal:
    proposal = get_proposal(db, proposal_id)
    tasks_service.require_owner(tasks_service.get_task(db, proposal.task_id), owner_id)
    if proposal.status != "accepted" or proposal.progress is None:
        raise HTTPException(409, "Нет результата выбранной команды, ожидающего проверки")
    _lock_current(db, proposal)
    progress = proposal.progress
    model = type(progress)
    key = model.proposal_id if isinstance(progress, ProposalMilestone) else model.id
    changed = db.execute(delete(model).where(key == progress.id, model.confirmed_at.is_(None)))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Подтверждённый результат нельзя вернуть на доработку")
    db.commit()
    db.refresh(proposal)
    return proposal
