"""Настройки AI и обнаружение моделей доступны текущему бизнес-пользователю."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.ai import schemas, service
from app.modules.users import service as users_service

router = APIRouter(prefix="/ai", tags=["ai"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[Any, Depends(users_service.get_current_user)]
OptionalUser = Annotated[Any, Depends(users_service.get_optional_user)]


@router.get("/settings", response_model=schemas.ConnectionRead)
def settings(db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    return service.read_settings(db, user.id)


@router.put("/settings", response_model=schemas.ConnectionRead)
def save_settings(payload: schemas.ConnectionInput, db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    return service.save_settings(db, user.id, payload)


@router.get("/models", response_model=schemas.ModelsRead)
def models(db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    return service.available_models(db, user.id)


@router.post("/models", response_model=schemas.ModelsRead)
def probe_models(payload: schemas.ConnectionInput, db: Db, user: CurrentUser):
    users_service.require_role(user, "business")
    return service.available_models(db, user.id, payload)


@router.get("/status", response_model=schemas.AIStatus)
def status(db: Db, user: OptionalUser):
    return service.get_status(db, user.id if user else None)
