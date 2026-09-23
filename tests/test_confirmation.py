"""Подтверждение каждого поля, редактирование, совместимость и русская валидация."""

import pytest

from app.modules.rating.service import FIELD_WEIGHTS
from app.modules.tasks.models import Task
from app.modules.users.models import User


@pytest.fixture
def owned_card(client, db):
    db.add_all([User(id=1, name="Владелец", role="business"), User(id=2, name="Другой", role="business")])
    db.commit()
    headers = {"X-User-Id": "1"}
    result = client.post("/api/tasks/draft", headers=headers, json={"raw_text": "Нужен сервис"}).json()
    return f"/api/tasks/{result['id']}", headers


def test_edit_revokes_only_changed_field_and_published_stays_visible(client, owned_card):
    url, headers = owned_card
    card = {field: "Полное описание поля, данное самим пользователем." for field in FIELD_WEIGHTS}
    saved = client.patch(url, headers=headers, json=card).json()
    assert saved["score"] == 0 and saved["potential_score"] == 100
    assert client.post(url + "/publish", headers=headers).status_code == 409
    assert client.post(url + "/confirm", headers={"X-User-Id": "2"}).status_code == 403
    assert client.post(url + "/confirm", headers=headers).json()["score"] == 100
    assert client.post(url + "/publish", headers=headers).status_code == 200
    edited = client.patch(url, headers=headers, json={"data": "Изменённые данные требуют повторного подтверждения."}).json()
    assert edited["score"] == 80 and edited["potential_score"] == 100
    assert edited["unconfirmed_fields"] == ["data"]
    assert edited["status"] == "published"
    # Предварительная версия владельца не заменяет подтверждённую публичную.
    assert client.get("/api/catalog").json()[0]["score"] == 100
    assert client.get(url).json()["data"] == card["data"]
    assert client.post(url + "/confirm", headers=headers).json()["score"] == 100
    assert client.get("/api/catalog").json()[0]["score"] == 100


def test_stale_confirmation_rejected_and_noop_patch_keeps_confirmation(client, owned_card):
    url, headers = owned_card
    old = client.get(url, headers=headers).json()
    client.patch(url, headers=headers, json={"context": "Подробный контекст, написанный представителем бизнеса."})
    assert client.post(url + "/confirm", headers=headers,
                       json={"expected_updated_at": old["updated_at"]}).status_code == 409
    confirmed = client.post(url + "/confirm", headers=headers).json()
    unchanged = client.patch(url, headers=headers, json={"context": confirmed["context"]}).json()
    assert unchanged["status"] == "confirmed" and unchanged["score"] == 10


def test_legacy_published_confirmation_preserved_on_first_edit(client, db, owned_card):
    db.add(Task(id=99, owner_id=1, raw_text="Старый ввод", status="published",
                context="Ранее подтверждённое описание длиной более 30 символов.",
                data="Ранее подтверждённые данные длиной более 30 символов."))
    db.commit()
    assert client.get("/api/tasks/99").json()["score"] == 30
    changed = client.patch("/api/tasks/99", headers={"X-User-Id": "1"}, json={"data": "Новый набор данных"}).json()
    assert changed["score"] == 10


@pytest.mark.parametrize("method,suffix,payload", [
    ("post", "/card", {"answers": {"madeup": "Текст"}}),
    ("post", "/card", {"answers": {"title": "А" * 241}}),
    ("patch", "", {"context": "А" * 10001}),
    ("patch", "", {"score": 100}),
    ("patch", "", {"raw_text": None}),
])
def test_bad_input_is_russian_422_not_500(client, owned_card, method, suffix, payload):
    url, headers = owned_card
    response = getattr(client, method)(url + suffix, headers=headers, json=payload)
    assert response.status_code == 422
    assert all(any("А" <= char <= "я" for char in error["msg"]) for error in response.json()["errors"])
    assert all("input" not in error for error in response.json()["errors"])
