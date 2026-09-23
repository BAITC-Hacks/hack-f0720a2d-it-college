"""Сервис откликов и только ручного принятия или отклонения бизнесом."""

from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import MetaData, Table, case, delete, func, inspect, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.modules.proposals.models import Proposal, ProposalMilestone, utc_now
from app.modules.proposals.schemas import MilestoneReview, MilestoneSubmission, ProposalCreate, StageName
from app.modules.tasks import service as tasks_service
from app.modules.teams import service as teams_service


MILESTONES = (
    ("research", "Исследование", 20),
    ("prototype", "Прототип", 30),
    ("final", "Финальное решение", 50),
)


def _conflict(db: Session, detail: str) -> None:
    db.rollback()
    raise HTTPException(status_code=409, detail=detail)


def _execute_cas(db: Session, statement):
    """SQL predicates arbitrate competing writes; SQLite lock conflicts are retryable."""
    try:
        return db.execute(statement.execution_options(synchronize_session=False))
    except OperationalError as exc:
        db.rollback()
        code = getattr(exc.orig, "sqlite_errorcode", 0)
        if code & 0xFF in (5, 6):  # SQLITE_BUSY / SQLITE_LOCKED, including extended codes
            raise HTTPException(status_code=409, detail="Данные меняются другим запросом. Обновите страницу") from exc
        raise


def _is_duplicate_proposal(exc: IntegrityError) -> bool:
    constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    return constraint == "uq_proposals_task_team" or str(exc.orig) == (
        "UNIQUE constraint failed: proposals.task_id, proposals.team_id"
    )


def delete_for_task(db: Session, task_id: int) -> None:
    """Удаляет отклики и старые записи прогресса в транзакции вызывающего сервиса."""
    proposal_ids = select(Proposal.id).where(Proposal.task_id == task_id)
    db.execute(delete(ProposalMilestone).where(ProposalMilestone.proposal_id.in_(proposal_ids)))
    connection = db.connection()
    if inspect(connection).has_table("proposal_progress"):
        # Таблица могла остаться от предыдущей версии; миграция или очистка БД не нужны.
        progress = Table(
            "proposal_progress", MetaData(), autoload_with=connection, resolve_fks=False
        )
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
    return _change_decision(db, proposal, proposal.status, "pending")


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
        if _is_duplicate_proposal(exc):
            raise HTTPException(status_code=409, detail="Команда уже откликнулась на эту задачу") from exc
        raise
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
    return _change_decision(db, proposal, "pending", decision)


def _change_decision(db: Session, proposal: Proposal, expected_status: str, decision: str) -> Proposal:
    result = _execute_cas(
        db,
        update(Proposal)
        .where(Proposal.id == proposal.id, Proposal.version == proposal.version, Proposal.status == expected_status)
        .values(status=decision, version=Proposal.version + 1),
    )
    if result.rowcount != 1:
        _conflict(db, "Решение по отклику уже изменилось. Обновите страницу")
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(proposal)
    return proposal


def _require_team(proposal: Proposal, team_id: int | None) -> None:
    if team_id is None or proposal.team_id != team_id:
        raise HTTPException(status_code=403, detail="Прогресс доступен только своей команде")


def _guard_progress_write(db: Session, proposal: Proposal) -> None:
    """Serialize progress with decision/reopen without overwriting stale session state."""
    if proposal.status != "accepted":
        raise HTTPException(status_code=409, detail="Работа с этапами доступна только по принятому отклику")
    result = _execute_cas(
        db,
        update(Proposal)
        .where(Proposal.id == proposal.id, Proposal.version == proposal.version, Proposal.status == "accepted")
        .values(version=Proposal.version + 1),
    )
    if result.rowcount != 1:
        _conflict(db, "Отклик или его прогресс уже изменился. Обновите страницу")


def _progress_snapshot(db: Session, proposal: Proposal) -> dict:
    rows = db.scalars(
        select(ProposalMilestone)
        .where(ProposalMilestone.proposal_id == proposal.id)
        .execution_options(populate_existing=True)
    )
    by_stage = {row.stage: row for row in rows}
    stages = []
    for stage, title, points in MILESTONES:
        row = by_stage.get(stage)
        stages.append({
            "stage": stage, "title": title, "points": points,
            "status": row.status if row else "not_started",
            **{field: getattr(row, field) if row else None for field in (
                "description", "link", "submission_token", "review_comment", "submitted_at", "reviewed_at"
            )},
        })
    earned = sum(stage["points"] for stage in stages if stage["status"] == "confirmed")
    weight = case({stage: points for stage, _, points in MILESTONES}, value=ProposalMilestone.stage, else_=0)
    team_points = db.scalar(
        select(func.coalesce(func.sum(weight), 0))
        .select_from(ProposalMilestone)
        .join(Proposal, Proposal.id == ProposalMilestone.proposal_id)
        .where(Proposal.team_id == proposal.team_id, ProposalMilestone.status == "confirmed")
    )
    return {
        "proposal_id": proposal.id, "team_points": team_points,
        "earned_points": earned, "completion_percent": earned, "stages": stages,
    }


def get_progress(db: Session, proposal_id: int, user_id: int, role: str, team_id: int | None) -> dict:
    proposal = get_proposal(db, proposal_id)
    if role == "business":
        tasks_service.require_owner(tasks_service.get_task(db, proposal.task_id), user_id)
    elif role == "team":
        _require_team(proposal, team_id)
    else:
        raise HTTPException(status_code=403, detail="Нет доступа к прогрессу")
    return _progress_snapshot(db, proposal)


def submit_progress(db: Session, proposal_id: int, team_id: int | None, payload: MilestoneSubmission) -> dict:
    proposal = get_proposal(db, proposal_id)
    _require_team(proposal, team_id)
    try:
        _guard_progress_write(db, proposal)
        rows = list(db.scalars(select(ProposalMilestone).where(
            ProposalMilestone.proposal_id == proposal_id
        ).execution_options(populate_existing=True)))
        by_stage = {row.stage: row for row in rows}
        for stage, _, _ in MILESTONES:
            if stage == payload.stage:
                break
            if stage not in by_stage or by_stage[stage].status != "confirmed":
                _conflict(db, "Сначала дождитесь подтверждения предыдущего этапа")
        existing = by_stage.get(payload.stage)
        if existing is not None and existing.status != "rejected":
            _conflict(db, "Этап уже отправлен или подтверждён")
        values = {
            "description": payload.description, "link": payload.link, "status": "pending",
            "submission_token": str(uuid4()), "review_comment": None,
            "submitted_at": utc_now(), "reviewed_at": None,
        }
        if existing is None:
            db.add(ProposalMilestone(proposal_id=proposal_id, stage=payload.stage, **values))
        else:
            result = _execute_cas(db, update(ProposalMilestone).where(
                ProposalMilestone.id == existing.id, ProposalMilestone.status == "rejected",
                ProposalMilestone.submission_token == existing.submission_token,
            ).values(**values))
            if result.rowcount != 1:
                _conflict(db, "Этап уже изменился. Обновите страницу")
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(proposal)
    return _progress_snapshot(db, proposal)


def review_progress(
    db: Session, proposal_id: int, owner_id: int, stage: StageName,
    payload: MilestoneReview, decision: Literal["confirmed", "rejected"],
) -> dict:
    proposal = get_proposal(db, proposal_id)
    tasks_service.require_owner(tasks_service.get_task(db, proposal.task_id), owner_id)
    try:
        _guard_progress_write(db, proposal)
        result = _execute_cas(db, update(ProposalMilestone).where(
            ProposalMilestone.proposal_id == proposal_id, ProposalMilestone.stage == stage,
            ProposalMilestone.status == "pending",
            ProposalMilestone.submission_token == str(payload.submission_token),
        ).values(status=decision, review_comment=payload.comment, reviewed_at=utc_now()))
        if result.rowcount != 1:
            _conflict(db, "Этап уже проверен, пересдан или ещё не отправлен. Обновите страницу")
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(proposal)
    return _progress_snapshot(db, proposal)
