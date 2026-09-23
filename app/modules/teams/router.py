"""HTTP-маршрут общего списка команд."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.teams import schemas, service

router = APIRouter(prefix="/teams", tags=["teams"])
Db = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[schemas.TeamRead])
def get_teams(db: Db):
    return service.list_teams(db)
