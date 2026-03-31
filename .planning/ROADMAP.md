# Roadmap: Wookiee

## Milestones

- v1.0 **Product Matrix UX Redesign** - Phases 1-4 (shipped 2026-03-30)
- v2.0 **Упрощение системы отчётов** - Phases 1-5 (in progress)

## Phases

<details>
<summary>v1.0 Product Matrix UX Redesign (Phases 1-4) - SHIPPED 2026-03-30</summary>

### Phase 1: Foundation
**Goal**: Single source of truth for entity routing; detail panel dispatches to correct API; table rows reflect panel saves
**Requirements**: FOUND-01, FOUND-02, FOUND-03
**Plans:** 2/2 complete

### Phase 2: Detail Panel
**Goal**: All fields visible in read mode, edit mode with correct input types, save/cancel
**Requirements**: PANEL-01..08
**Plans:** 6/6 complete

### Phase 3: Table View
**Goal**: Human-readable display names, resolved references, sort, column toggle, create record
**Requirements**: TABLE-01..07, CRUD-01, CRUD-02
**Plans:** 3/3 complete

### Phase 4: Filter System
**Goal**: Status/category filters, multi-field filter builder, hierarchy drill-down, saved views
**Requirements**: FILT-01..05
**Plans:** 3/3 complete

</details>

## v2.0 Упрощение системы отчётов

**Milestone Goal:** Одна простая рабочая система аналитических отчётов — V2 оркестратор (agents/oleg/), без V3/LangGraph, стабильная генерация каждый день.

- [x] **Phase 1: Очистка** - Удаление V3, зависимостей, docs, обновление Docker (completed 2026-03-30)
- [ ] **Phase 2: Настройка агента** - База знаний, иерархия данных, структура отчётов по типам и периодам
- [ ] **Phase 3: Надёжность** - Pre-flight, retry, валидация полноты, graceful degradation, защита от дублей
- [ ] **Phase 4: Запуск и доставка** - Cron-задачи, Notion upsert, Telegram-уведомления, русские названия
- [ ] **Phase 5: Верификация** - Генерация всех 8 типов, сравнение с эталонами, проверка на реальных данных
- [ ] **Phase 6: Документация и зачистка** - Полная документация системы, удаление всех лишних контейнеров и мёртвого кода

## Phase Details

### Phase 1: Очистка
**Goal**: Кодовая база содержит только одну систему отчётов (V2), без мёртвого кода V3
**Depends on**: Nothing (first phase)
**Requirements**: CLEAN-01, CLEAN-02, CLEAN-03, CLEAN-04
**Success Criteria** (what must be TRUE):
  1. Директория agents/v3/ не существует, все файлы удалены
  2. В requirements*.txt нет зависимостей langchain/langgraph/langchain-openai
  3. В docs/ нет V3-related планов и спецификаций
  4. Docker-compose запускает V2 систему напрямую без упоминаний V3
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md — Patch V3 cross-reference, delete agents/v3/ and V3 scripts
- [x] 01-02-PLAN.md — Delete V3 docs, update docker-compose

### Phase 2: Настройка агента
**Goal**: Агент имеет полную базу знаний, понимает иерархию данных, и для каждого типа/периода отчёта знает точную структуру и глубину анализа
**Depends on**: Phase 1
**Requirements**: PLAY-01, PLAY-02, PLAY-03, VER-03
**Success Criteria** (what must be TRUE):
  1. Плейбук разбит на модули: core (бизнес-контекст, формулы, глоссарий), templates (структура каждого типа отчёта), rules (стратегии, антипаттерны, диагностика)
  2. Иерархия данных и отчётов задокументирована: какие tools → какие данные → какие секции отчёта
  3. Для каждого из 8 типов отчёта определена точная структура с обязательными секциями и toggle-заголовками
  4. Глубина анализа настроена: daily=компактный (ключевые метрики), weekly=глубокий (тренды, модели, гипотезы), monthly=максимальный (P&L, юнит-экономика, стратегия)
  5. Маркетинговый и funnel плейбуки обновлены в том же формате
**Plans**: 2 plans

Plans:
- [ ] 02-01: TBD

### Phase 3: Надёжность
**Goal**: Система не публикует пустые/неполные отчёты и корректно обрабатывает ошибки на каждом этапе
**Depends on**: Phase 2
**Requirements**: REL-01, REL-02, REL-03, REL-04, REL-05, REL-06, REL-07
**Success Criteria** (what must be TRUE):
  1. При отсутствии данных в источнике отчёт не запускается, в логе указана причина
  2. При пустом ответе LLM система делает retry (до 2 раз) и в итоге получает непустой результат
  3. Отчёт с пропущенными секциями не публикуется в Notion; вместо пропуска пишется причина (graceful degradation)
  4. В Notion для каждой комбинации период+тип существует ровно одна страница (upsert, без дублей)
  5. Telegram-уведомление отправляется только после успешной публикации в Notion
**Plans**: 2 plans

Plans:
- [ ] 03-01-PLAN.md — Gate checker (pre-flight data quality gates) + report types registry + fix funnel_weekly Notion label
- [ ] 03-02-PLAN.md — Report pipeline (retry, section validation, graceful degradation, publish+notify ordering)

### Phase 4: Запуск и доставка
**Goal**: Все 8 типов отчётов запускаются автоматически по расписанию и доставляются в Notion + Telegram
**Depends on**: Phase 3
**Requirements**: SCHED-01, SCHED-02, SCHED-03, SCHED-04
**Success Criteria** (what must be TRUE):
  1. Crontab содержит задачи для всех 8 типов отчётов с правильными расписаниями (daily/weekly/monthly)
  2. Опубликованный отчёт в Notion имеет properties: период, тип, статус — заполнены корректно
  3. После публикации в Notion приходит Telegram-уведомление с ссылкой на отчёт
  4. Типы отчётов в Notion и Telegram отображаются на русском языке
**Plans**: 2 plans

Plans:
- [ ] 04-01: TBD

### Phase 5: Верификация
**Goal**: Все 8 типов отчётов проверены на реальных данных и соответствуют эталонам качества
**Depends on**: Phase 4
**Requirements**: RPT-01, RPT-02, RPT-03, RPT-04, RPT-05, RPT-06, RPT-07, RPT-08, VER-01, VER-02
**Success Criteria** (what must be TRUE):
  1. Каждый из 8 типов отчётов сгенерирован на реальных данных без ошибок
  2. Финансовый monthly содержит P&L, юнит-экономику, стратегию; weekly — тренды и гипотезы; daily — компактную сводку
  3. Маркетинговые отчёты содержат данные по кампаниям, ДРР, CTR; воронка — конверсии по этапам
  4. Для каждого типа отчёта определён эталон из лучших существующих отчётов в Notion
  5. Качество новых отчётов не хуже эталонов (полнота данных, точность, глубина анализа)
**Plans**: 2 plans

Plans:
- [ ] 05-01: TBD

### Phase 6: Документация и зачистка
**Goal**: Полная документация работающей системы + удаление всего лишнего с сервера (контейнеры, мёртвый код, старые скрипты)
**Depends on**: Phase 5
**Requirements**: DOC-01, DOC-02, DOC-03
**Success Criteria** (what must be TRUE):
  1. Документация описывает всю систему: архитектура, компоненты, типы отчётов, расписания, доставка, troubleshooting
  2. На сервере запущены ТОЛЬКО нужные контейнеры (всё лишнее удалено)
  3. В репозитории нет мёртвого кода, неиспользуемых скриптов, устаревших docs/plans/specs
  4. Один документ (README или docs/system.md) — точка входа для понимания всей системы
**Plans**: 2 plans

Plans:
- [ ] 06-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Очистка | 2/2 | Complete   | 2026-03-30 |
| 2. Настройка агента | 0/? | Not started | - |
| 3. Надёжность | 0/2 | Not started | - |
| 4. Запуск и доставка | 0/? | Not started | - |
| 5. Верификация | 0/? | Not started | - |
| 6. Документация и зачистка | 0/? | Not started | - |
