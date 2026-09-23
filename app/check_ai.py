"""Короткая ручная проверка OpenAI на вымышленных данных, без доступа к БД."""

from app.modules.ai.errors import AIServiceError
from app.modules.ai import service


def main() -> int:
    status = service.get_status()
    if status["provider"] != "openai" or not status["configured"]:
        print("OpenAI не настроен. Укажите OPENAI_API_KEY в .env и AI_PROVIDER=auto или openai.")
        return 2
    try:
        raw_text = "В учебной мастерской теряются ремонтные заявки. Нужен простой журнал обращений."
        analysis = service.analyze_draft(raw_text, known_fields={"industry": "Образование"})
        card = service.build_card(raw_text, {
            "industry": "Образование",
            "users": "Сотрудники учебной мастерской",
            "expected_result": "Веб-прототип журнала обращений с поиском",
        })
    except AIServiceError as exc:
        print(f"Проверка OpenAI не пройдена: {exc.detail}")
        return 1
    print(f"OpenAI отвечает. Модель: {status['model']}.")
    print(f"Получено вопросов: {len(analysis['questions'])}.")
    print(f"Карточка собрана: заполнено {sum(bool(value) for value in card.values())} полей.")
    print("Рабочая база данных не изменялась.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
