from dataclasses import dataclass
from uuid import uuid4

from app.database import Database
from app.errors import ServiceError
from app.schemas import CardFields, CriterionResult, EvaluationRead, FinalizeRequest, TaskCreate
from app.services.common import require_draft, require_task, require_version, utc_now

FORMULA_VERSION = "completeness-v1"
PLACEHOLDERS = {
    "-", "—", "?", "...", "tbd", "todo", "n/a", "unknown", "нет данных",
    "не знаю", "не указано", "уточнить", "позже", "потом уточним",
}


def is_filled(value: str) -> bool:
    normalized = " ".join(value.casefold().split())
    return bool(normalized) and normalized not in PLACEHOLDERS


@dataclass(frozen=True)
class Criterion:
    key: str
    label: str
    weight: int
    fields: tuple[str, ...]


CRITERIA = (
    Criterion("context_need", "Контекст и потребность", 20, ("context", "need")),
    Criterion("data", "Данные и материалы", 20, ("data",)),
    Criterion("expected_result", "Ожидаемый результат", 15, ("expected_result",)),
    Criterion("success_criteria", "Критерии успеха", 15, ("success_criteria",)),
    Criterion("constraints", "Ограничения", 10, ("constraints",)),
    Criterion("users", "Пользователи", 10, ("users",)),
    Criterion("communication", "Связь с бизнесом", 10, ("contact", "interaction_format")),
)


def readiness_for_score(score: int) -> str:
    if score < 40:
        return "draft"
    if score < 70:
        return "working"
    if score < 90:
        return "ready"
    return "priority"


def score_card(card: CardFields) -> list[CriterionResult]:
    results = []
    for criterion in CRITERIA:
        missing = [field for field in criterion.fields if not is_filled(getattr(card, field))]
        points = criterion.weight * (len(criterion.fields) - len(missing)) // len(criterion.fields)
        results.append(CriterionResult(
            key=criterion.key,
            label=criterion.label,
            points=points,
            max_points=criterion.weight,
            missing_fields=missing,
            explanation=(
                "Подтверждённые поля заполнены"
                if not missing else "Не хватает сведений: " + ", ".join(missing)
            ),
        ))
    return results


class EvaluationService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get(self, task_id: str) -> EvaluationRead:
        with self.database.connection() as connection:
            require_task(connection, task_id)
            row = connection.execute(
                "SELECT result_json FROM evaluations WHERE task_id=?", (task_id,)
            ).fetchone()
            if row is None:
                raise ServiceError(404, "evaluation_not_found", "Карточка ещё не оценена")
            return EvaluationRead.model_validate_json(row["result_json"])

    def finalize_once(self, task_id: str, payload: FinalizeRequest) -> EvaluationRead:
        with self.database.connection(write=True) as connection:
            task = require_task(connection, task_id)
            existing = connection.execute(
                "SELECT result_json FROM evaluations WHERE task_id=?", (task_id,)
            ).fetchone()
            if existing is not None:
                # A retry with the original version returns the original result.
                return EvaluationRead.model_validate_json(existing["result_json"])
            require_draft(task)
            require_version(task, payload.expected_version)
            card = TaskCreate.model_validate_json(task["content_json"])
            if not is_filled(card.title):
                raise ServiceError(422, "title_required", "Перед оценкой укажите название задачи")
            criteria = score_card(card)
            score = sum(criterion.points for criterion in criteria)
            now = utc_now()
            evaluation = EvaluationRead(
                id=str(uuid4()), task_id=task_id, task_version=task["version"],
                score=score, readiness=readiness_for_score(score), criteria=criteria,
                missing_fields=[field for criterion in criteria for field in criterion.missing_fields],
                card_snapshot=card, formula_version=FORMULA_VERSION, created_at=now,
            )
            connection.execute(
                """INSERT INTO evaluations
                (task_id, id, score, readiness, result_json, created_at) VALUES (?, ?, ?, ?, ?, ?)""",
                (task_id, evaluation.id, score, evaluation.readiness, evaluation.model_dump_json(), now),
            )
            connection.execute(
                "UPDATE tasks SET status='finalized', finalized_at=?, updated_at=? WHERE id=?",
                (now, now, task_id),
            )
            return evaluation
