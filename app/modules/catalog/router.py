"""HTTP-маршрут открытого каталога без порога минимального рейтинга."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.catalog import schemas, service

router = APIRouter(prefix="/catalog", tags=["catalog"])
Db = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[schemas.CatalogTask])
def get_catalog(
    db: Db,
    industry: str | None = Query(default=None, max_length=120),
    level: Literal["draft", "working", "ready", "priority"] | None = None,
):
    return service.get_catalog(db, industry=industry, level=level)
