"""Неразрушающее обновление существующей SQLite-базы при запуске."""

from sqlalchemy import create_engine, inspect, text

from app import db as database


def test_existing_proposals_receive_version_without_losing_data(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE proposals (
                id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL, idea TEXT NOT NULL,
                plan TEXT NOT NULL, deadline VARCHAR(120) NOT NULL,
                link VARCHAR(500), status VARCHAR(20) NOT NULL,
                created_at DATETIME NOT NULL
            )
        """))
        connection.execute(text("""
            INSERT INTO proposals VALUES
            (42, 6, 1, 'Existing idea', 'Existing plan', '2 weeks',
             NULL, 'accepted', '2026-09-23 12:00:00')
        """))
    monkeypatch.setattr(database, "engine", engine)
    try:
        database.create_tables()
        database.create_tables()
        with engine.connect() as connection:
            row = connection.execute(text("SELECT id, idea, status, version FROM proposals")).one()
            assert tuple(row) == (42, "Existing idea", "accepted", 1)
            tables = set(inspect(connection).get_table_names())
            assert {"task_revisions", "proposal_milestones"} <= tables
    finally:
        engine.dispose()
