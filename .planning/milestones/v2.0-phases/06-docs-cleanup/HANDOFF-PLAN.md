# Phase 6: Документация и зачистка — План доработок

> Контекст: Milestone v2.0, фазы 1-5 выполнены. Осталась только фаза 6.
> Прочитай AGENTS.md и CLAUDE.md перед началом.

## Статус на 2026-04-02

| Требование | Статус | Что осталось |
|-----------|--------|-------------|
| DOC-01 | ~80% | docs/system.md (271 строк) — хорошая основа, нужны доработки |
| DOC-02 | НЕ ПРОВЕРЕНО | 2 контейнера в docker-compose не запущены на сервере |
| DOC-03 | DONE | V3 удалена, мёртвого кода нет |

---

## Задача 1: Дополнить docs/system.md (DOC-01)

Файл `docs/system.md` уже содержит архитектуру, 8 типов, pipeline, troubleshooting. Нужно дополнить:

### 1.1 Добавить секцию "Доставка в Notion"
Где: после секции "Gate Checker" (~строка 128)

Содержание:
- Notion Database ID берётся из `NOTION_DATABASE_ID` в `.env`
- Properties при публикации: "Период начала" (date), "Период конца" (date), "Тип анализа" (select, русские названия), "Статус" (select)
- Upsert логика: `shared/notion_client.py` → `sync_report()` ищет существующую страницу по date+type, обновляет или создаёт новую
- Markdown → Notion blocks: `shared/notion_blocks.py` конвертирует toggle-заголовки в toggle блоки

Источник данных: `shared/notion_client.py` (функции `sync_report`, `_find_existing_page`)

### 1.2 Добавить пороги Gate Checker
Где: в секции "Gate Checker" (~строка 116)

Текущее описание перечисляет 3 hard + 3 soft gates, но не указывает пороги. Нужно:
- Прочитать `agents/oleg/pipeline/gate_checker.py`
- Для каждого gate указать: что проверяется, порог (например, "данные за последние N часов"), что происходит при провале

### 1.3 Обновить список контейнеров
Где: секция "Docker-контейнеры" (~строка 135)

На сервере реально запущены:
```
wookiee_oleg         — отчёты (cron)
wookiee_sheets_sync  — синхронизация Google Sheets
vasily-api           — локализация
wb_mcp_ip            — WB API (ИП)
wb_mcp_ooo           — WB API (ООО)
bitrix24_mcp         — Битрикс24
```

В docs/system.md указаны ещё `wookiee_dashboard_api` и `wookiee_knowledge_base` — они определены в docker-compose.yml (строки 202 и 239), но **НЕ запущены на сервере**. Нужно:
- Пометить их как "не деплоится на прод" или вынести в отдельный раздел "Опциональные сервисы"
- Добавить n8n + Caddy в список (они на сервере есть, в доке нет)

---

## Задача 2: Зачистка docker-compose.yml (DOC-02)

### 2.1 Проверить, нужны ли эти сервисы

| Контейнер | В compose | На сервере | Решение |
|-----------|-----------|------------|---------|
| wookiee_dashboard_api | Да (строка 202) | НЕТ | Если не используется → удалить из compose или вынести в profiles |
| wookiee_knowledge_base | Да (строка 239) | НЕТ | Если не используется → удалить из compose или вынести в profiles |

Прочитать `deploy/docker-compose.yml` целиком. Проверить:
- Есть ли другие неиспользуемые сервисы
- Есть ли упоминания V3 (finolog-cron уже должен быть удалён)

### 2.2 Синхронизировать compose с реальностью
- Если dashboard_api/knowledge_base нужны → добавить `profiles: [optional]` чтобы не стартовали по умолчанию
- Если не нужны → закомментировать или удалить

---

## Задача 3: Обновить GSD-артефакты (финализация milestone)

### 3.1 REQUIREMENTS.md
Отметить как выполненные (заменить `[ ]` на `[x]`):
- RPT-01..08 — все 8 типов проверены (см. `.planning/phases/05-verification/05-01-SUMMARY.md` и `05-02-SUMMARY.md`)
- VER-01 — все 8 типов сгенерированы
- VER-02 — эталоны найдены (см. `05-reference-standards.md`)
- DOC-01..03 — после выполнения задач 1-2 выше

В Traceability table:
- RPT-01..08: Pending → Complete
- VER-01, VER-02: Pending → Complete
- DOC-01..03: Pending → Complete

### 3.2 ROADMAP.md
- Phase 2: `1/2` → `2/2`, "In Progress" → "Complete"
- Phase 5: `0/2` → `2/2`, "Planned" → "Complete", добавить дату `2026-04-02`
- Phase 6: `0/?` → `2/2` (или сколько планов), "Not started" → "Complete"
- Планы 05-01, 05-02: `[ ]` → `[x]`
- Milestone header: "Phases 1-5 (in progress)" → "Phases 1-6 (shipped)"

### 3.3 STATE.md
- status: executing → shipped
- completed_phases: 5 → 6
- completed_plans: 10 → 12
- percent: 83 → 100
- Current Position: Phase 06 → SHIPPED
- Progress bar: [██████████] 100%

---

## Задача 4: Закрыть milestone

После выполнения задач 1-3:
```
/gsd:complete-milestone
```

Это заархивирует `.planning/phases/` в `.planning/archive/v2.0/` и подготовит проект к следующему milestone.

---

## Порядок выполнения

```
Задача 1 (docs/system.md) → Задача 2 (docker-compose) → Задача 3 (GSD-артефакты) → Задача 4 (закрытие)
```

Примерный объём: ~30 минут работы.

## Команда для запуска

В новом контексте:
```
Прочитай .planning/phases/06-docs-cleanup/HANDOFF-PLAN.md и выполни все 4 задачи последовательно. После задач 1-3 закрой milestone через /gsd:complete-milestone.
```
