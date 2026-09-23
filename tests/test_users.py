"""Smoke-тест списка пользователей и выбора роли без пароля."""

from app.modules.users.models import User


def test_users_login(client, db):
    db.add(User(id=1, name="Заказчик", role="business"))
    db.commit()

    response = client.get("/api/users")
    assert response.status_code == 200
    assert response.json()[0]["name"] == "Заказчик"

    response = client.post("/api/users/login", json={"user_id": 1, "role": "business"})
    assert response.status_code == 200
    assert response.json()["role"] == "business"
