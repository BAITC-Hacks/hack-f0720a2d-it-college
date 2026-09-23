"""HTTP-маршруты списка пользователей и упрощённого входа."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.users import schemas, service

router = APIRouter(prefix="/users", tags=["users"])
Db = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[schemas.UserRead])
def get_users(db: Db):
    return service.list_users(db)


@router.post("/login", response_model=schemas.UserRead)
def login(payload: schemas.LoginRequest, db: Db):
    return service.login(db, payload)
