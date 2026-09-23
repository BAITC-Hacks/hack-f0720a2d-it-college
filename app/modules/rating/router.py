"""У рейтинга нет отдельного HTTP API: его вызывает сервис задач."""

from fastapi import APIRouter

router = APIRouter(tags=["rating"])
