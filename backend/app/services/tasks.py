import json
import sqlite3
from uuid import uuid4

from app.database import Database
from app.schemas import TaskCreate, TaskPage, TaskPatch, TaskRead
from app.services.common import require_draft, require_task, require_version, utc_now

TASK_QUERY = """
    SELECT t.*, e.score, e.readiness
    FROM tasks t LEFT JOIN evaluations e ON e.task_id = t.id
"""


def task_from_row(row: sqlite3.Row) -> TaskRead:
    return TaskRead(
        **json.loads(row["content_json"]),
        id=row["id"],
        status=row["status"],
        version=row["version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        finalized_at=row["finalized_at"],
        score=row["score"],
        readiness=row["readiness"],
    )


class TaskService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, payload: TaskCreate) -> TaskRead:
        task_id, now = str(uuid4()), utc_now()
        with self.database.connection(write=True) as connection:
            connection.execute(
                """INSERT INTO tasks
                (id, title, topic, content_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (task_id, payload.title, payload.topic, payload.model_dump_json(), now, now),
            )
            row = connection.execute(TASK_QUERY + " WHERE t.id = ?", (task_id,)).fetchone()
            return task_from_row(row)

    def get(self, task_id: str) -> TaskRead:
        with self.database.connection() as connection:
            require_task(connection, task_id)
            row = connection.execute(TASK_QUERY + " WHERE t.id = ?", (task_id,)).fetchone()
            return task_from_row(row)

    def list(
        self, *, status: str = "finalized", topic: str | None = None,
        readiness: str | None = None, limit: int = 20, offset: int = 0,
    ) -> TaskPage:
        clauses, parameters = [], []
        if status != "all":
            clauses.append("t.status = ?")
            parameters.append(status)
        if topic is not None:
            clauses.append("t.topic = ?")
            parameters.append(topic)
        if readiness is not None:
            clauses.append("e.readiness = ?")
            parameters.append(readiness)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.database.connection() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM tasks t LEFT JOIN evaluations e ON e.task_id=t.id"
                + where, parameters,
            ).fetchone()[0]
            rows = connection.execute(
                TASK_QUERY + where
                + " ORDER BY COALESCE(e.score, -1) DESC, t.created_at DESC, t.id LIMIT ? OFFSET ?",
                [*parameters, limit, offset],
            ).fetchall()
        return TaskPage(
            items=[task_from_row(row) for row in rows], total=total, limit=limit, offset=offset
        )

    def update(self, task_id: str, payload: TaskPatch) -> TaskRead:
        with self.database.connection(write=True) as connection:
            row = require_task(connection, task_id)
            require_draft(row)
            require_version(row, payload.expected_version)
            content = json.loads(row["content_json"])
            content.update(payload.model_dump(exclude_unset=True, exclude={"expected_version"}))
            card = TaskCreate.model_validate(content)
            connection.execute(
                """UPDATE tasks SET title=?, topic=?, content_json=?, version=version+1,
                updated_at=? WHERE id=?""",
                (card.title, card.topic, card.model_dump_json(), utc_now(), task_id),
            )
            updated = connection.execute(TASK_QUERY + " WHERE t.id=?", (task_id,)).fetchone()
            return task_from_row(updated)

    def delete(self, task_id: str) -> None:
        with self.database.connection(write=True) as connection:
            row = require_task(connection, task_id)
            require_draft(row)
            connection.execute("DELETE FROM tasks WHERE id=?", (task_id,))
