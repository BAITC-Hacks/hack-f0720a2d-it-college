from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.schemas import (
    AnalysisRequest, AnalysisResponse, EvaluationRead, FinalizeRequest, ProposalCreate,
    ProposalDecision, ProposalPage, ProposalRead, Readiness, TaskCreate, TaskPage, TaskPatch, TaskRead,
)
from app.services.ai import AIAnalysisService
from app.services.evaluation import EvaluationService
from app.services.proposals import ProposalService
from app.services.tasks import TaskService

router = APIRouter(prefix="/api/v1")


def get_tasks(request: Request) -> TaskService:
    return request.app.state.tasks


def get_proposals(request: Request) -> ProposalService:
    return request.app.state.proposals


def get_evaluations(request: Request) -> EvaluationService:
    return request.app.state.evaluations


def get_ai(request: Request) -> AIAnalysisService:
    return request.app.state.ai


Tasks = Annotated[TaskService, Depends(get_tasks)]
Proposals = Annotated[ProposalService, Depends(get_proposals)]
Evaluations = Annotated[EvaluationService, Depends(get_evaluations)]
AI = Annotated[AIAnalysisService, Depends(get_ai)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED, tags=["Карточки"])
def create_task(payload: TaskCreate, service: Tasks):
    return service.create(payload)


@router.get("/tasks", response_model=TaskPage, tags=["Карточки"])
def list_tasks(
    service: Tasks,
    status: Literal["draft", "finalized", "all"] = "finalized",
    topic: Annotated[str | None, Query(max_length=200)] = None,
    readiness: Readiness | None = None,
    limit: Limit = 20, offset: Offset = 0,
):
    """Каталог: опубликованные карточки по убыванию рейтинга, включая низкий рейтинг."""
    return service.list(status=status, topic=topic, readiness=readiness, limit=limit, offset=offset)


@router.get("/tasks/{task_id}", response_model=TaskRead, tags=["Карточки"])
def get_task(task_id: UUID, service: Tasks):
    return service.get(str(task_id))


@router.patch("/tasks/{task_id}", response_model=TaskRead, tags=["Карточки"])
def update_task(task_id: UUID, payload: TaskPatch, service: Tasks):
    return service.update(str(task_id), payload)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Карточки"])
def delete_task(task_id: UUID, service: Tasks):
    service.delete(str(task_id))
    return Response(status_code=204)


@router.post("/tasks/{task_id}/evaluation", response_model=EvaluationRead, tags=["Однократная оценка"])
def evaluate_task(task_id: UUID, payload: FinalizeRequest, service: Evaluations):
    """Подтвердить, оценить и опубликовать карточку атомарно. Повтор возвращает прежний результат."""
    return service.finalize_once(str(task_id), payload)


@router.get("/tasks/{task_id}/evaluation", response_model=EvaluationRead, tags=["Однократная оценка"])
def get_evaluation(task_id: UUID, service: Evaluations):
    return service.get(str(task_id))


@router.post(
    "/tasks/{task_id}/proposals", response_model=ProposalRead,
    status_code=status.HTTP_201_CREATED, tags=["Предложения команд"],
)
def create_proposal(task_id: UUID, payload: ProposalCreate, service: Proposals):
    return service.create(str(task_id), payload)


@router.get("/tasks/{task_id}/proposals", response_model=ProposalPage, tags=["Предложения команд"])
def list_proposals(
    task_id: UUID, service: Proposals,
    status: Literal["pending", "accepted", "rejected"] | None = None,
    team_id: Annotated[str | None, Query(max_length=200)] = None,
    limit: Limit = 20, offset: Offset = 0,
):
    return service.list(str(task_id), status=status, team_id=team_id, limit=limit, offset=offset)


@router.get("/proposals/{proposal_id}", response_model=ProposalRead, tags=["Предложения команд"])
def get_proposal(proposal_id: UUID, service: Proposals):
    return service.get(str(proposal_id))


@router.patch("/proposals/{proposal_id}/decision", response_model=ProposalRead, tags=["Предложения команд"])
def decide_proposal(proposal_id: UUID, payload: ProposalDecision, service: Proposals):
    """Ручное решение бизнеса по одному отклику. Несколько accepted для одной задачи допустимы."""
    return service.decide(str(proposal_id), payload)


@router.post("/ai/analyze", response_model=AnalysisResponse, tags=["AI-анализ"])
async def analyze(payload: AnalysisRequest, service: AI):
    """Анализирует описание и ответы. Возвращает предложение карточки, не изменяя хранилище."""
    return await service.analyze(payload)
