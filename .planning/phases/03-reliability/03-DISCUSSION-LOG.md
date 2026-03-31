# Phase 3: Надёжность - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 03-reliability
**Areas discussed:** Pre-flight проверки, Retry и обработка пустого LLM, Валидация полноты отчёта, Порядок publish+notify

---

## Pre-flight проверки

| Option | Description | Selected |
|--------|-------------|----------|
| Быстрый пинг источников | Каждый tool проверяет наличие данных за период | |
| Полная проверка по типу | Минимальный набор данных для каждого типа отчёта | |
| Ты решаешь | Claude выбирает | |

**User's choice:** Custom — описал существующий механизм проверки через `dateupdate` поле в БД
**Notes:** Данные берутся из Supabase PostgreSQL, не из Google Sheets. Поле `dateupdate` в каждой таблице показывает свежесть. Ранее был скрипт, отправлявший в Telegram "✅ Данные за X готовы" с метриками (заказы, выручка%, маржа%) по WB и Ozon.

### Follow-up: Источник данных

| Option | Description | Selected |
|--------|-------------|----------|
| Через sheets_sync статус | Смотреть в Google Sheets последнюю синхронизацию | |
| Напрямую через data tools | Минимальный запрос через tools агента | |
| Не помню / Claude найдёт | Claude поищет в кодовой базе | ✓ |

**User's choice:** Claude найдёт
**Notes:** Найден gate_checker interface в watchdog/diagnostic.py, pipeline/ директория описана в SYSTEM.md но не создана

### Follow-up: Telegram + метрики

| Option | Description | Selected |
|--------|-------------|----------|
| Telegram + логи | Как раньше: сообщение в Telegram + логи | ✓ |
| Только логи | Тихо в логах | |

**User's choice:** Telegram + логи

| Option | Description | Selected |
|--------|-------------|----------|
| Заказы + выручка + маржа | Как в примере | |
| Только заказы > 0 | Простая проверка | |
| Ты решаешь | | |

**User's choice:** Custom — проверять все необходимые источники (финансовые, рекламные, заказы), ориентироваться на `dateupdate` поле

---

## Retry и обработка пустого LLM

| Option | Description | Selected |
|--------|-------------|----------|
| Пустой/короткий ответ | Пустая строка или <500 символов | |
| Пустой + нет секций | Пустая строка или нет markdown-заголовков | |
| Ты решаешь | Claude выберет критерии | ✓ |

**User's choice:** Ты решаешь

| Option | Description | Selected |
|--------|-------------|----------|
| Только LLM-вызов | Повторяем тот же промпт | |
| Весь chain | Перезапускаем с начала | |
| Ты решаешь | Claude выберет | ✓ |

**User's choice:** Ты решаешь
**Notes:** Пользователь не знаком с деталями LLM-пайплайна. Был дан контекст объяснения. Решение полностью делегировано Claude.

---

## Валидация полноты отчёта

| Option | Description | Selected |
|--------|-------------|----------|
| Из шаблонов Phase 2 | Шаблоны playbook определяют секции | ✓ |
| Минимальные правила | Не пустой, 3+ заголовка, длина > порога | |
| Ты решаешь | | |

**User's choice:** Из шаблонов Phase 2

| Option | Description | Selected |
|--------|-------------|----------|
| Писать причину в секцию | Graceful degradation с объяснением | ✓ |
| Не публиковать вообще | Если хоть одна секция пуста | |
| Ты решаешь | | |

**User's choice:** Custom — если данных нет совсем, отчёт не формируется. Если формируется, но часть недоступна — писать объяснение человеческим языком с предложением решения.

---

## Порядок publish+notify

| Option | Description | Selected |
|--------|-------------|----------|
| Да, достаточно | sync_report upsert покрывает REL-06 | |
| Нужны доработки | | |
| Ты решаешь | Claude проверит | ✓ |

**User's choice:** Ты решаешь

| Option | Description | Selected |
|--------|-------------|----------|
| Лог + отчёт успешен | Telegram некритичен | |
| Retry Telegram | 1-2 повтора | |
| Ты решаешь | | ✓ |

**User's choice:** Ты решаешь

---

## Claude's Discretion

- Критерии "пустого" LLM-ответа
- Уровень retry (LLM-вызов vs chain)
- Поведение при Telegram failure
- Конкретные hard/soft gates для gate_checker
- Формат Telegram-сообщения
- Проверка корректности sync_report для всех типов

## Deferred Ideas

None
