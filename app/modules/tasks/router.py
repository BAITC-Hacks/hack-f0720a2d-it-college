"""HTTP-маршруты конструктора и жизненного цикла задачи."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.ai.schemas import AnalyzeDraftOutput
from app.modules.tasks import schemas, service
from app.modules.users import service as users_service

router = APIRouter(prefix="/tasks", tags=["tasks"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[Any, Depends(users_service.get_current_user)]
OptionalUser = Annotated[Any, Depends(users_service.get_optional_user)]


@router.get("", response_model=list[schemas.TaskRead])
def my_tasks(db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    return service.list_owned(db, user.id)


@router.post("/draft", response_model=schemas.TaskRead, status_code=201)
def create_draft(payload: schemas.DraftCreate, db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    return service.to_read(service.create_draft(db, user.id, payload))


@router.post("/{task_id}/questions", response_model=AnalyzeDraftOutput)
def questions(task_id: int, db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    task = service.get_task(db, task_id)
    service.require_owner(task, user.id)
    return service.get_questions(db, task_id)


@router.post("/{task_id}/card", response_model=schemas.TaskRead)
def build_card(task_id: int, payload: schemas.CardAnswers, db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    return service.to_read(service.build_card(db, task_id, user.id, payload.answers))


@router.patch("/{task_id}", response_model=schemas.TaskRead)
def update_task(task_id: int, payload: schemas.TaskPatch, db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    return service.to_owner_read(db, service.update_task(db, task_id, user.id, payload))


@router.delete("/{task_id}", status_code=204, response_class=Response)
def delete_task(task_id: int, db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    service.delete_task(db, task_id, user.id)
    return Response(status_code=204)


@router.post("/{task_id}/confirm", response_model=schemas.TaskRead)
def confirm_task(task_id: int, db: Db, user: CurrentUser, payload: schemas.ConfirmRequest | None = None):
    users_service.require_role(user, "business")
    return service.to_read(service.confirm_task(db, task_id, user.id, payload.expected_updated_at if payload else None))


@router.post("/{task_id}/publish", response_model=schemas.TaskRead)
def publish_task(task_id: int, db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    return service.to_read(service.publish_task(db, task_id, user.id))


@router.get("/{task_id}", response_model=schemas.TaskRead)
def get_task(task_id: int, db: Db, user: OptionalUser):
    return service.read_visible(db, task_id, user.id if user else None)
