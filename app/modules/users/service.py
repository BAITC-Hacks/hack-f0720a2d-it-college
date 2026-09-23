"""Сервис выбора пользователя, ролей и зависимости X-User-Id."""

from typing import Literal

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.users.models import User
from app.modules.users.schemas import LoginRequest


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def login(db: Session, payload: LoginRequest) -> User:
    user = get_user(db, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if payload.role is not None and user.role != payload.role:
        raise HTTPException(status_code=400, detail="Выбранная роль не соответствует пользователю")
    return user


def require_role(user: User, role: Literal["business", "team"]) -> None:
    if user.role != role:
        role_name = "бизнеса" if role == "business" else "команды"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Действие доступно только пользователю роли {role_name}",
        )


def get_current_user(
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
) -> User:
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="Передайте заголовок X-User-Id")
    user = get_user(db, x_user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Пользователь из X-User-Id не найден")
    return user


def get_optional_user(
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
) -> User | None:
    if x_user_id is None:
        return None
    return get_current_user(db, x_user_id)
