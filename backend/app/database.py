import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    topic TEXT NOT NULL,
    content_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'finalized')),
    version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finalized_at TEXT,
    CHECK ((status = 'draft' AND finalized_at IS NULL)
        OR (status = 'finalized' AND finalized_at IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS evaluations (
    task_id TEXT PRIMARY KEY REFERENCES tasks(id) ON DELETE RESTRICT,
    id TEXT NOT NULL UNIQUE,
    score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
    readiness TEXT NOT NULL CHECK(readiness IN ('draft','working','ready','priority')),
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
    team_id TEXT NOT NULL,
    content_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','rejected')),
    business_comment TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    decided_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_catalog ON tasks(status, topic);
CREATE INDEX IF NOT EXISTS idx_evaluations_rating ON evaluations(score DESC);
CREATE INDEX IF NOT EXISTS idx_proposals_task ON proposals(task_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposals_team ON proposals(team_id);
CREATE TRIGGER IF NOT EXISTS immutable_finalized_task
BEFORE UPDATE ON tasks WHEN OLD.status = 'finalized'
BEGIN SELECT RAISE(ABORT, 'Finalized tasks are immutable'); END;
CREATE TRIGGER IF NOT EXISTS cannot_delete_finalized_task
BEFORE DELETE ON tasks WHEN OLD.status = 'finalized'
BEGIN SELECT RAISE(ABORT, 'Finalized tasks are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evaluation_update
BEFORE UPDATE ON evaluations
BEGIN SELECT RAISE(ABORT, 'Evaluations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evaluation_delete
BEFORE DELETE ON evaluations
BEGIN SELECT RAISE(ABORT, 'Evaluations are immutable'); END;
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=15)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(SCHEMA)
        finally:
            connection.close()

    @contextmanager
    def connection(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            # Acquire the write lock BEFORE reading a draft/evaluation. This makes
            # finalization atomic across threads, processes and application workers.
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
