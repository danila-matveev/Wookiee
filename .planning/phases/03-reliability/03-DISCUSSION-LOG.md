# Phase 3: Надёжность - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-31
**Phase:** 03-reliability
**Areas discussed:** Pre-flight gates, Pipeline architecture, Error UX

---

## Pre-flight gates

### Partial data handling

| Option | Description | Selected |
|--------|-------------|----------|
| Запускать то что готово | Если WB ready — запускаем WB-отчёты. Ozon ждёт. | ✓ |
| Ждать полной готовности | Отчёты только когда ВСЕ источники обновились | |

**User's choice:** Запускать то что готово
**Notes:** —

### Volume checks

| Option | Description | Selected |
|--------|-------------|----------|
| Да, базовые sanity checks | dateupdate + минимум записей (orders > 0) | ✓ |
| Только свежесть | dateupdate = сегодня — достаточно | |

**User's choice:** Да, базовые sanity checks
**Notes:** —

### Gate types

| Option | Description | Selected |
|--------|-------------|----------|
| Hard: свежесть + volume. Soft: аномалии | Hard block, soft = предупреждение | ✓ |
| Hard: только свежесть. Soft: volume + anomalies | Минимальные блокировки | |

**User's choice:** Hard: свежесть + volume. Soft: аномалии
**Notes:** —

---

## Pipeline architecture

### Pipeline location

| Option | Description | Selected |
|--------|-------------|----------|
| Wrapper снаружи | pipeline.run() → gate → orchestrator → validate → publish → notify | ✓ |
| Внутри orchestrator | Всё в orchestrator.run_chain | |
| Claude decides | — | |

**User's choice:** Wrapper снаружи
**Notes:** —

### Retry level

| Option | Description | Selected |
|--------|-------------|----------|
| Chain-level | Перезапуск всего orchestrator.run_chain | ✓ |
| LLM-call level | Повтор конкретного LLM-вызова | |
| Claude decides | — | |

**User's choice:** Chain-level
**Notes:** —

---

## Error UX

### Pre-flight block message

| Option | Description | Selected |
|--------|-------------|----------|
| Краткое сообщение | 1-2 строки с причиной | |
| Подробное сообщение | Полный статус каждого gate | |
| Без Telegram при блоке | Только в лог | |

**User's choice:** Other (free text)
**Notes:** Пользователь описал детальный паттерн: проверка данных с 6 утра каждые 30 мин. Telegram апдейт каждые 2 часа если данные не готовы. Если готовы — пишем сразу. Формат: на русском, с процентами по категориям (финансовые, рекламные, заказы), без техжаргона. Расписание polling = Phase 4, но gate_checker должен поддерживать формат с процентами.

### Retry visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Нет, пользователь не знает | Retry только в логах | ✓ |
| Да, пометка в Telegram | "Отчёт со 2-й попытки" | |

**User's choice:** Retry только в логах
**Notes:** Пользователь хочет в будущем создать БД для workflow логов (не в этой фазе).

### Full failure action

| Option | Description | Selected |
|--------|-------------|----------|
| Лог + Telegram alert | "❌ Отчёт не сгенерирован после 3 попыток" | ✓ |
| Только лог | Не спамить ошибками | |

**User's choice:** Лог + Telegram alert
**Notes:** —

### Scope split (Phase 3 vs Phase 4)

| Option | Description | Selected |
|--------|-------------|----------|
| Разделить: Phase 3 = механизм, Phase 4 = расписание | gate_checker + pipeline в Phase 3, cron + polling в Phase 4 | |

**User's choice:** Other (free text)
**Notes:** Уточнил: проверка каждые 30 мин, Telegram апдейт каждые 2 часа. Зафиксировано как Phase 4 scope, но gate_checker интерфейс (процент готовности по категориям) — Phase 3.

---

## Claude's Discretion

- Конкретные пороги для "пустого" LLM-ответа
- Конкретные hard/soft gates (таблицы, поля)
- Формат pipeline.run
- Структура report_types registry

## Deferred Ideas

- Расписание polling (6:00-18:00, 30мин/2ч) — Phase 4
- БД для workflow логов — post Phase 3
- LLM аналитика для ДДС/Локализация — backlog
