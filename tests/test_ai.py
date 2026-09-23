"""Smoke-тест заменяемого AI-контракта без внешнего API."""

from app.modules.ai.service import analyze_draft, build_card


def test_ai_stub_asks_questions_and_does_not_invent():
    raw_text = "У нас долго обрабатываются обращения покупателей."
    analysis = analyze_draft(raw_text)
    assert len(analysis["questions"]) >= 3
    assert "success_criteria" in analysis["missing_fields"]

    card = build_card(raw_text, {"need": "Сократить время обработки обращений"})
    assert card["context"] == raw_text
    assert card["need"] == "Сократить время обработки обращений"
    assert card["contact"] is None
