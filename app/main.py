"""Сборка FastAPI-приложения, API-роутеров, CORS и статического фронтенда."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder

from app.db import create_tables
from app.modules.ai.router import router as ai_router
from app.modules.catalog.router import router as catalog_router
from app.modules.proposals.router import router as proposals_router
from app.modules.rating.router import router as rating_router
from app.modules.tasks.router import router as tasks_router
from app.modules.teams.router import router as teams_router
from app.modules.users.router import router as users_router

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    yield


app = FastAPI(
    title="AI Sana — каталог бизнес-задач",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            {"detail": "Некорректные входные данные", "errors": exc.errors()}
        ),
    )


for api_router in (
    users_router,
    tasks_router,
    rating_router,
    ai_router,
    catalog_router,
    teams_router,
    proposals_router,
):
    app.include_router(api_router, prefix="/api")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}
