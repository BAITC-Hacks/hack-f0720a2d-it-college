# AI Sana — передача дизайна в разработку

Макеты: Design-холст «AI Sana — дизайн» (страницы: Каталог · Создание задачи · Карточка и отклик · Кабинет бизнеса · Токены и компоненты).

## Файлы

| Файл | Куда положить | Что это |
|---|---|---|
| `tokens.css` | `static/css/tokens.css` | Цвета, шрифты, отступы, радиусы — CSS-переменные |
| `components.css` | `static/css/components.css` | Все компоненты (классы ниже) |
| `ui.js` | `static/js/ui.js` | Рендер-функции: `catalogRow`, `badge`, `meter`, `breakdown`, `missingList`, `emptyState`, `alertBox`, `showFieldErrors` |
| `source/` | не нужен в приложении | Python-генератор макетов (`ds.py` — токены и компоненты, `screens*.py` — экраны) |

Подключение в `static/index.html`:
```html
<link rel="stylesheet" href="/static/css/tokens.css">
<link rel="stylesheet" href="/static/css/components.css">
<script type="module" src="/static/js/app.js"></script>
```

## Правила
- Один акцент `--c-accent`. Красный и зелёный — только ошибки и успех. Новых цветов не добавлять.
- Шрифты: Onest — весь интерфейс, JetBrains Mono — баллы, счётчики, eyebrow-метки.
- Отступы — только `--s-*` (шаг 4px). Радиусы: бейдж 6, кнопка/поле 8, панель 12.
- Название и ожидаемый результат задачи — всегда первые и самые крупные в строке/карточке.
- Уровень по баллу: `levelOf(score)` в `ui.js` — те же пороги, что в `app/modules/rating/service.py` (90/70/40).
- Черновик (0–39) никогда не скрывается и не блокирует отклик: пунктирный бейдж + «Требует уточнения · отклик открыт».
- Кнопки выбора команды — только ручные (`Выбрать команду` / `Отклонить`). Никаких «лучшее совпадение» и автоназначений.

## Компоненты → классы
| Компонент | Классы |
|---|---|
| Шапка | `.header .nav` (`aria-current="page"`) |
| Кнопки | `.btn .btn--primary/secondary/dark/ghost/danger`, `.btn--sm`, `.btn--block`, `disabled` |
| Поле | `.field[data-field] > .field__label + .input/.textarea/.select + .field__error + .field__hint`; ошибка — `.field.is-invalid` |
| Готовность | `.badge--priority/ready/working/draft`, `.meter.meter--{level} > .meter__fill`, `.score`, `.score--lg` |
| Каталог | `.catalog > .catalog__head + .catalog-row` (грид 40px / 1fr / 200px / 190px) |
| Расшифровка | `.breakdown__row`, `.missing`, `.state--complete/short/empty` |
| Сообщения | `.alert--info/error/success/draft`, `.empty` |
| Навигация | `.stepper` (`aria-current="step"`, `.is-done`), `.tabs .tab[aria-selected]`, `.chip`, `.status--pending/accepted/rejected` |
| Сравнение | `.compare > .compare__row > .compare__label + .compare__cell(.is-accepted/.is-rejected)`, `--cols` = число откликов |

## Экраны → API (префикс /api; заголовок `X-User-Id`)
| Экран | Эндпоинты |
|---|---|
| Каталог | `GET /api/catalog?industry=&level=` — сортировка по `score` уже на сервере |
| Создание 1 · описание | `POST /api/tasks/draft` (DraftCreate) → 422 → `showFieldErrors` |
| Создание 2 · вопросы | `POST /api/tasks/{id}/questions` → вопросы (≥3); ответы → `POST /api/tasks/{id}/card` |
| Создание 3 · карточка | `PATCH /api/tasks/{id}` → в ответе `score, level, level_label, breakdown, missing` — перерисовать панель рейтинга |
| Создание 4 · публикация | `POST /api/tasks/{id}/confirm` → `POST /api/tasks/{id}/publish` |
| Карточка задачи | `GET /api/tasks/{id}`; отклик `POST /api/proposals` (idea ≥10, plan ≥10, deadline ≥2, link) |
| Кабинет бизнеса | `GET /api/tasks/{id}/proposals`; `POST /api/proposals/{id}/accept` и `/reject` — только по кнопке |

## Как добавить новый экран
1. Собрать из существующих классов: `.page` (контент + колонка 380px) или `.header + .stack`.
2. Заголовок `.h1`, панели `.panel`, служебные подписи `.eyebrow`.
3. Нужны состояния: пусто → `.empty`, ошибка → `.field.is-invalid` + `.alert--error`, успех → `.alert--success`.
4. Если нужен новый компонент — сначала добавить его в `components.css` на токенах, потом использовать.
