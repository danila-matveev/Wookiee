# Phase 5: Верификация - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-31
**Phase:** 05-verification
**Areas discussed:** Benchmark selection, Quality criteria, Verification process, Issue remediation

---

## Benchmark selection

| Option | Description | Selected |
|--------|-------------|----------|
| Я сам выберу | Показать конкретные Notion-страницы — лучший daily, лучший weekly и т.д. | |
| Поиск по последним отчётам | Claude найдёт последние отчёты каждого типа в Notion, пользователь одобрит | |
| Claude решает | Claude автономно найдёт и оценит отчёты по критериям (длина, полнота, данные) | |

**User's choice:** Claude находит лучшие отчёты за последний месяц и выбирает из них
**Notes:** Пользователь хочет полностью автономный поиск и выбор эталонов

### Хранение эталонов

| Option | Description | Selected |
|--------|-------------|----------|
| Notion-ссылки в доке | Сохранить URL-ы в benchmarks.md | |
| Markdown-копии локально | Скачать в docs/benchmarks/ | |
| Claude решает | Claude сам выберет формат | ✓ |

**User's choice:** Claude решает
**Notes:** —

---

## Quality criteria

| Option | Description | Selected |
|--------|-------------|----------|
| Полнота данных | Все секции заполнены, нет заглушек | ✓ |
| Глубина анализа | Monthly=P&L+стратегия, weekly=тренды, daily=компактно | ✓ |
| Точность цифр | Числа совпадают с БД | ✓ |
| Формат и читаемость | Toggle-заголовки, единообразие, русский | ✓ |

**User's choice:** Все 4 критерия (multiSelect)
**Notes:** Все критерии равнозначно важны

### Проверка точности

| Option | Description | Selected |
|--------|-------------|----------|
| Ручная проверка | Пользователь сверяет с базой | |
| SQL-проверка ключевых метрик | Claude достаёт цифры и сверяет SQL-запросами | |
| Общая проверка адекватности | Числа в разумных диапазонах | |

**User's choice:** SQL-проверка + проверка адекватности. Возможно LLM для адекватности, но SQL может быть достаточно
**Notes:** Пользователь не уверен в точном подходе, доверяет Claude выбрать оптимальный

---

## Verification process

### Даты

| Option | Description | Selected |
|--------|-------------|----------|
| Вчера/прошлая неделя | Свежие данные | ✓ |
| Конкретные даты | Пользователь укажет | |
| Claude решает | Claude выберет даты с полными данными | |

**User's choice:** Свежие данные — вчера для daily, прошлая неделя для weekly, прошлый месяц для monthly
**Notes:** —

### Порядок

| Option | Description | Selected |
|--------|-------------|----------|
| По одному с чекпоинтом | Генерируем → проверяем → фиксим → следующий | ✓ |
| Пакетом все 8 | Запускаем всё, потом анализируем | |
| Группами по 2-3 | Финансовые, маркетинговые, остальные | |

**User's choice:** По одному с чекпоинтом
**Notes:** Пользователь подтвердил что это лучший подход

---

## Issue remediation

### Что фиксить

| Option | Description | Selected |
|--------|-------------|----------|
| Плейбуки/промпты | Улучшать templates/*.md | |
| Код pipeline | Фиксить баги в pipeline/agents | |
| Claude решает | Claude диагностирует и фиксит | ✓ |

**User's choice:** Claude решает
**Notes:** —

### Количество итераций

| Option | Description | Selected |
|--------|-------------|----------|
| Пока не ок | Без лимита | |
| Макс 3 итерации | До 3 попыток на тип | |
| Claude решает | Claude определит по прогрессу | ✓ |

**User's choice:** Claude решает
**Notes:** —

---

## Claude's Discretion

- Формат хранения эталонов
- Конкретные SQL-запросы для сверки
- Порог приемлемого качества
- Количество итераций на тип
- Стратегия исправления (плейбук vs код vs данные)
- Использование LLM для проверки адекватности

## Deferred Ideas

None — discussion stayed within phase scope
