"""HTTP-маршруты отклика команды и ручного решения владельца задачи."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.proposals import schemas, service
from app.modules.users import service as users_service

router = APIRouter(tags=["proposals"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[Any, Depends(users_service.get_current_user)]


@router.get("/proposals", response_model=list[schemas.ProposalRead])
def my_proposals(db: Db, user: CurrentUser):
    return service.list_for_user(db, user.id, user.role, user.team_id)


@router.post("/proposals/{proposal_id}/reopen", response_model=schemas.ProposalRead)
def reopen_proposal(proposal_id: int, db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    return service.reopen_proposal(db, proposal_id, user.id)


@router.post("/proposals", response_model=schemas.ProposalRead, status_code=201)
def create_proposal(payload: schemas.ProposalCreate, db: Db, user: CurrentUser):
    users_service.require_role(user, "team")
    return service.create_proposal(db, user.team_id, payload)


@router.get("/tasks/{task_id}/proposals", response_model=list[schemas.ProposalRead])
def task_proposals(task_id: int, db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    return service.list_task_proposals(db, task_id, user.id)


@router.post("/proposals/{proposal_id}/accept", response_model=schemas.ProposalRead)
def accept_proposal(proposal_id: int, db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    return service.decide_proposal(db, proposal_id, user.id, "accepted")


@router.post("/proposals/{proposal_id}/reject", response_model=schemas.ProposalRead)
def reject_proposal(proposal_id: int, db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    return service.decide_proposal(db, proposal_id, user.id, "rejected")


@router.post("/proposals/{proposal_id}/progress", response_model=schemas.ProposalRead)
def submit_progress(proposal_id: int, payload: schemas.ProgressSubmit, db: Db, user: CurrentUser):
    users_service.require_role(user, "team")
    return service.submit_progress(db, proposal_id, user.team_id, payload)


@router.post("/proposals/{proposal_id}/progress/confirm", response_model=schemas.ProposalRead)
def confirm_progress(proposal_id: int, db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    return service.confirm_progress(db, proposal_id, user.id)


@router.post("/proposals/{proposal_id}/progress/reject", response_model=schemas.ProposalRead)
def reject_progress(proposal_id: int, db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    return service.reject_progress(db, proposal_id, user.id)
