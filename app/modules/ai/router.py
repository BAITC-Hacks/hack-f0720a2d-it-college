"""Публичная конфигурация AI; генерация доступна через сценарии задач."""

from fastapi import APIRouter

from app.modules.ai import schemas, service

router = APIRouter(tags=["ai"])


@router.get("/ai/status", response_model=schemas.AIStatus)
def status():
    return service.get_status()
