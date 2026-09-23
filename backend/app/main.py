import sqlite3
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import router
from app.config import Settings
from app.database import Database
from app.errors import ServiceError
from app.services.ai import AIAnalysisService
from app.services.evaluation import EvaluationService
from app.services.proposals import ProposalService
from app.services.tasks import TaskService


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    database = Database(config.database_path)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database.initialize()
        async with httpx.AsyncClient() as client:
            application.state.ai = AIAnalysisService(config, client)
            yield

    application = FastAPI(
        title="HackAlem Tasks API", version="1.0.0",
        description="Карточки заданий, предложения команд, AI-анализ и однократная финальная оценка.",
        lifespan=lifespan,
    )
    application.state.database = database
    application.state.tasks = TaskService(database)
    application.state.proposals = ProposalService(database)
    application.state.evaluations = EvaluationService(database)
    application.add_middleware(
        CORSMiddleware, allow_origins=list(config.cors_origins),
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @application.exception_handler(sqlite3.OperationalError)
    async def database_error_handler(request: Request, exc: sqlite3.OperationalError):
        # Do not expose SQL, filesystem paths or data in API errors.
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "storage_unavailable", "message": "Хранилище временно недоступно"}},
        )

    @application.get("/health", tags=["Состояние"])
    def health():
        with database.connection() as connection:
            connection.execute("SELECT COUNT(*) FROM tasks").fetchone()
        return {"status": "ok", "ai_provider": config.ai_provider}

    application.include_router(router)
    return application


app = create_app()
