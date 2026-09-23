"""Smoke-тест заменяемого AI-контракта без внешнего API."""

import pytest

from app.config import get_settings
from app.modules.ai import service
from app.modules.ai.service import analyze_draft, build_card


def test_ai_stub_asks_questions_and_does_not_invent():
    raw_text = "У нас долго обрабатываются обращения покупателей."
    analysis = analyze_draft(raw_text)
    assert analysis["provider"] == "stub"
    assert len(analysis["questions"]) >= 3
    assert "success_criteria" in analysis["missing_fields"]

    card = build_card(raw_text, {"need": "Сократить время обработки обращений"})
    assert card["context"] == raw_text
    assert card["need"] == "Сократить время обработки обращений"
    assert card["contact"] is None


def test_stub_respects_fields_already_saved_on_task():
    analysis = analyze_draft(
        "Описание магазина",
        known_fields={"title": "Поддержка магазина", "industry": "Торговля", "data": "Обезличенные обращения"},
    )
    assert not {"title", "industry", "data"}.intersection(analysis["missing_fields"])
    assert analysis["provider"] == "stub"


@pytest.mark.parametrize("mode,key", [("auto", ""), ("stub", "sk-test-deliberately-unused")])
def test_offline_modes_never_create_provider_client(monkeypatch, mode, key):
    from app.modules.ai import provider

    monkeypatch.setenv("AI_PROVIDER", mode)
    monkeypatch.setenv("OPENAI_API_KEY", key)
    get_settings.cache_clear()
    monkeypatch.setattr(provider, "create_client", lambda *_args, **_kwargs: pytest.fail("Offline mode must not create HTTP client"))
    assert analyze_draft("Исходное описание задачи")["provider"] == "stub"
    assert build_card("Исходное описание задачи", {"need": "Потребность команды"})["contact"] is None


def test_explicit_openai_without_key_fails_without_network(monkeypatch):
    from app.modules.ai import provider

    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(provider, "create_client", lambda *_args, **_kwargs: pytest.fail("Missing key must not create HTTP client"))
    with pytest.raises(service.AIServiceError) as exc:
        analyze_draft("Исходное описание задачи")
    assert exc.value.status_code == 503
