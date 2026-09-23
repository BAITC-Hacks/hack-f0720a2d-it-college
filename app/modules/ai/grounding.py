"""???????? ????? ???????????? AI-??????? ?? ???????? ?????????."""

import re

from app.modules.ai import compatible_provider as provider
from app.modules.ai.compatible_prompts import FIELD_LABELS
from app.modules.ai.schemas import CardExtraction, CardFields


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _grounded_card(extraction: CardExtraction, raw_text: str, known: dict, answers: dict) -> CardFields:
    fragments = {_normalize(raw_text)}
    labels = {label for names in FIELD_LABELS.values() for label in names}
    for line in raw_text.splitlines():
        fragments.add(_normalize(line))
        label, separator, value = line.partition(":")
        if separator and label.strip().casefold() in labels:
            line = value.strip()
            fragments.add(_normalize(line))
        fragments.update(_normalize(part) for part in re.split(r"(?<=[.!?])\s+", line) if part.strip())
    fields = {}
    for name, quotes in extraction.model_dump().items():
        manual = answers.get(name) or known.get(name)
        if manual:
            fields[name] = manual
            continue
        other_answers = {_normalize(value) for key, value in answers.items() if key != name and value}
        grounded = []
        for quote in quotes:
            quote = _normalize(quote)
            if quote in other_answers:
                raise provider.InvalidAIResponse("Ответ пользователя перенесён в другое поле")
            if quote not in fragments:
                # Небольшие модели выделяют словосочетания вопреки инструкции.
                # Восстанавливаем целое предложение из источника, вместе с
                # отрицаниями и условиями; неоднозначный источник отклоняем.
                matches = [part for part in fragments if quote in part]
                minimal = [part for part in matches if not any(other != part and other in part for other in matches)]
                if len(minimal) != 1 or minimal[0] in other_answers:
                    raise provider.InvalidAIResponse("Не найден однозначный целый фрагмент источника")
                quote = minimal[0]
            grounded.append(quote)
        fields[name] = "\n".join(dict.fromkeys(grounded)) or None
    # Ручные значения имеют приоритет перед извлечением модели.
    fields.update({key: value for key, value in known.items() if value})
    fields.update({key: value for key, value in answers.items() if value})
    return CardFields.model_validate(fields)


