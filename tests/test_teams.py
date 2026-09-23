"""Smoke-тест публичного списка профилей команд."""

from app.modules.teams.models import Team


def test_get_teams(client, db):
    db.add(Team(name="Test Team", interests=["AI"], skills=["аналитика"], tech=["Python"]))
    db.commit()

    response = client.get("/api/teams")
    assert response.status_code == 200
    assert response.json()[0]["tech"] == ["Python"]
