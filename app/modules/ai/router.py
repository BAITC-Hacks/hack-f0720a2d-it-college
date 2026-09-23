"""AI-функции доступны через сценарии задач, отдельные маршруты не нужны."""

from fastapi import APIRouter

router = APIRouter(tags=["ai"])
