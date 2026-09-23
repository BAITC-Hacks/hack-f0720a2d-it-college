"""Smoke-тест сквозного сценария карточки от черновика до публикации."""

from app.modules.users.models import User


def test_task_draft_card_confirm_publish(client, db):
    db.add(User(id=1, name="Бизнес", role="business"))
    db.commit()
    headers = {"X-User-Id": "1"}

    response = client.post(
        "/api/tasks/draft",
        headers=headers,
        json={
            "raw_text": "Клиенты долго ждут ответа на обращения, хотим улучшить процесс обработки.",
            "title": "Ускорение поддержки",
            "industry": "Сервисы",
        },
    )
    assert response.status_code == 201
    task_id = response.json()["id"]

    response = client.post(f"/api/tasks/{task_id}/questions", headers=headers)
    assert response.status_code == 200
    assert len(response.json()["questions"]) >= 3

    detailed = "Подробное пользовательское описание, содержащее больше тридцати символов."
    response = client.post(
        f"/api/tasks/{task_id}/card",
        headers=headers,
        json={
            "answers": {
                "need": detailed,
                "users": detailed,
                "data": detailed,
                "constraints": detailed,
                "expected_result": detailed,
                "success_criteria": detailed,
                "contact": detailed,
            }
        },
    )
    assert response.status_code == 200
    assert response.json()["score"] == 100

    assert client.post(f"/api/tasks/{task_id}/confirm", headers=headers).status_code == 200
    response = client.post(f"/api/tasks/{task_id}/publish", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "published"
