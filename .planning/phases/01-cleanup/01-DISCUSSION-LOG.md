# Phase 1: Очистка - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 01-cleanup
**Areas discussed:** Scripts handling, V2→V3 dependency, Docker-compose target, Docs cleanup scope

---

## Scripts handling

| Option | Description | Selected |
|--------|-------------|----------|
| Удалить все (рекомендуется) | V2 использует свои точки входа. Скрипты — обёртки V3, без V3 бесполезны | ✓ |
| Оставить нужные | Оставить актуальные скрипты, переписать импорты на V2 | |
| На усмотрение Claude | Claude решит какие удалить, какие переписать | |

**User's choice:** Удалить все
**Notes:** —

---

## V2→V3 dependency

| Option | Description | Selected |
|--------|-------------|----------|
| Перенести в shared/config | Перенести get_wb_clients() в shared/config.py (соответствует AGENTS.md) | |
| Перенести в agents/oleg/config | Копия функции в локальный конфиг V2 | |
| На усмотрение Claude | Claude решит куда перенести | ✓ |

**User's choice:** На усмотрение Claude
**Notes:** —

---

## Docker-compose target

| Option | Description | Selected |
|--------|-------------|----------|
| Переключить на V2 | Заменить на python -m agents.oleg, убрать volume v3/data | |
| Удалить контейнер | Удалить wookiee-oleg, запуск V2 в Phase 4 | |
| На усмотрение Claude | Claude решит как обновить docker-compose | ✓ |

**User's choice:** На усмотрение Claude

### finolog-cron

| Option | Description | Selected |
|--------|-------------|----------|
| Оставить, починить позже | Finolog работает отдельно, скрипт починим позже | ✓ |
| Починить сейчас | Убрать V3-импорты в этой фазе | |
| Удалить контейнер | Удалить — переделаем в Phase 4 | |

**User's choice:** Оставить, починить позже

---

## Docs cleanup scope

| Option | Description | Selected |
|--------|-------------|----------|
| Только V3-labeled | Удалить только файлы с v3 в названии | |
| Глубокая очистка | Удалить все устаревшие docs | |
| На усмотрение Claude | Claude решит что удалять | ✓ |

**User's choice:** На усмотрение Claude
**Notes:** Пользователь уточнил: жёсткая зачистка, удалять всё V3-related без колебаний

---

## Claude's Discretion

- Куда перенести get_wb_clients() при развязке V2→V3
- Как обновить Docker-compose (переключить или удалить wookiee-oleg)
- Что делать с run_localization_report.py
- Объём очистки docs сверх V3-labeled файлов

## Deferred Ideas

- Починка finolog-cron скрипта — следующие фазы
- Полная настройка Docker для V2 — Phase 4
