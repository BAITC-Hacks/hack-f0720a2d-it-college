"""Идемпотентная загрузка демонстрационных пользователей, задач, команд и откликов."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal, create_tables
from app.modules.proposals.models import Proposal
from app.modules.rating.service import FIELD_WEIGHTS, calculate
from app.modules.tasks.models import Task, TaskVerification
from app.modules.teams.models import Team
from app.modules.users.models import User

DATA_DIR = Path(__file__).resolve().parent / "data"


def read_json(filename: str) -> list[dict]:
    with (DATA_DIR / filename).open(encoding="utf-8") as source:
        return json.load(source)


def seed() -> None:
    create_tables()
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)) is not None:
            print("База уже содержит пользователей; seed пропущен.")
            return

        teams = [Team(**item) for item in read_json("teams.json")]
        db.add_all(teams)
        db.flush()

        users = [
            User(id=1, name="Алия, бизнес-заказчик", role="business"),
            User(id=2, name="Тимур, бизнес-заказчик", role="business"),
            *[
                User(id=index + 2, name=f"Представитель {team.name}", role="team", team_id=team.id)
                for index, team in enumerate(teams, start=1)
            ],
        ]
        db.add_all(users)
        db.flush()

        tasks: list[Task] = []
        verifications: list[TaskVerification] = []
        for item in [*read_json("drafts.json"), *read_json("cards.json")]:
            item = dict(item)
            item.pop("score", None)
            task = Task(**item)
            # Опубликованные синтетические карточки изображают уже подтверждённые
            # бизнесом сведения. Черновики заполнены по-разному, но не подтверждены.
            values = {field: item.get(field) for field in FIELD_WEIGHTS}
            confirmed = item.get("status") in {"confirmed", "published"}
            confirmed_fields = [field for field, value in values.items() if value] if confirmed else []
            rating = calculate({**item, "confirmed_fields": confirmed_fields})
            task.score = rating["score"]
            task.level = rating["level"]
            task.breakdown = rating["breakdown"]
            tasks.append(task)
            if confirmed:
                verifications.append(TaskVerification(task_id=item["id"], values=values))
        db.add_all(tasks)
        db.flush()
        db.add_all(verifications)

        db.add_all(Proposal(**item) for item in read_json("proposals.json"))
        db.commit()
        print("Seed готов: 7 пользователей, 10 задач, 5 команд и 5 откликов.")


if __name__ == "__main__":
    seed()
