import json
import sqlite3
from uuid import uuid4

from app.database import Database
from app.errors import ServiceError
from app.schemas import ProposalCreate, ProposalDecision, ProposalPage, ProposalRead
from app.services.common import require_task, utc_now


def proposal_from_row(row: sqlite3.Row) -> ProposalRead:
    return ProposalRead(
        **json.loads(row["content_json"]), id=row["id"], task_id=row["task_id"],
        status=row["status"], business_comment=row["business_comment"],
        created_at=row["created_at"], decided_at=row["decided_at"],
    )


def require_proposal(connection: sqlite3.Connection, proposal_id: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
    if row is None:
        raise ServiceError(404, "proposal_not_found", "Предложение команды не найдено")
    return row


class ProposalService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, task_id: str, payload: ProposalCreate) -> ProposalRead:
        with self.database.connection(write=True) as connection:
            task = require_task(connection, task_id)
            if task["status"] != "finalized":
                raise ServiceError(409, "task_not_published", "Отклики доступны после подтверждения карточки")
            proposal_id = str(uuid4())
            connection.execute(
                """INSERT INTO proposals (id, task_id, team_id, content_json, created_at)
                VALUES (?, ?, ?, ?, ?)""",
                (proposal_id, task_id, payload.team_id, payload.model_dump_json(), utc_now()),
            )
            return proposal_from_row(require_proposal(connection, proposal_id))

    def get(self, proposal_id: str) -> ProposalRead:
        with self.database.connection() as connection:
            return proposal_from_row(require_proposal(connection, proposal_id))

    def list(
        self, task_id: str, *, status: str | None = None,
        team_id: str | None = None, limit: int = 20, offset: int = 0,
    ) -> ProposalPage:
        where = " WHERE task_id=?"
        parameters = [task_id]
        if status is not None:
            where += " AND status=?"
            parameters.append(status)
        if team_id is not None:
            where += " AND team_id=?"
            parameters.append(team_id)
        with self.database.connection() as connection:
            require_task(connection, task_id)
            total = connection.execute(
                "SELECT COUNT(*) FROM proposals" + where, parameters
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT * FROM proposals" + where + " ORDER BY created_at DESC, id LIMIT ? OFFSET ?",
                [*parameters, limit, offset],
            ).fetchall()
        return ProposalPage(
            items=[proposal_from_row(row) for row in rows], total=total, limit=limit, offset=offset
        )

    def decide(self, proposal_id: str, payload: ProposalDecision) -> ProposalRead:
        with self.database.connection(write=True) as connection:
            require_proposal(connection, proposal_id)
            connection.execute(
                "UPDATE proposals SET status=?, business_comment=?, decided_at=? WHERE id=?",
                (payload.status, payload.business_comment, utc_now(), proposal_id),
            )
            return proposal_from_row(require_proposal(connection, proposal_id))
