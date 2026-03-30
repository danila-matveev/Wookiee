# Project: Wookiee Product Matrix

**Created:** 2026-03-22
**Core Value:** Централизованное управление товарной матрицей (PIM) для мультиканального fashion-бизнеса — от модели до баркода, с финансами, складом и маркетплейсами.

## Architecture

- **Backend:** FastAPI + SQLAlchemy (`services/product_matrix_api/`)
- **Frontend:** React + Vite + Tailwind + shadcn/ui (`wookiee-hub/`)
- **Database:** PostgreSQL (Supabase) с RLS
- **Data hierarchy:** ModelOsnova → Model → Artikul → Tovar
- **Reference tables:** Kategoriya, Kollekciya, Status, Razmer, Fabrika, Importer, Cvet
- **Marketplace grouping:** SleykaWB, SleykaOzon (M:N with Tovar)

## What Exists (v0)

### Backend (working)
- CRUD endpoints for all entity types (models, articles, products, colors, factories, importers, cards, certs)
- External data endpoints (stock, finance) with caching
- Search, bulk operations, schema introspection, views, archive, admin routes
- ~40 fields on ModelOsnova, ~12 on Model, ~8 on Artikul, ~12 on Tovar

### Frontend (partially working, major UX issues)
- Basic entity list view with inline editing (Excel-style — wrong approach)
- Entity detail page with tabs (Info, Stock, Finance, Rating, Tasks)
- Stock/Finance tabs work with real data
- Navigation via sidebar entity selector

### Known Problems
- Navigation has unnecessary extra layer of menus
- Inline editing instead of detail panel
- Technical field names shown instead of display names
- Reference fields (category, collection, factory) show "—" instead of values
- No CRUD buttons (+), no filtering, no settings
- Missing ~70% of fields from the specification
- Not usable as a daily work tool

## Completed Milestones

### v1.0 — UX Redesign (completed 2026-03-30)
Product Matrix Editor → рабочая PIM-система: Notion-like table view, detail panel, фильтрация, CRUD, все поля из спецификации.

## Current Milestone: v2.0 — Упрощение системы отчётов

**Goal:** Одна простая рабочая система аналитических отчётов — V2 оркестратор (agents/oleg/), без V3/LangGraph, стабильная генерация каждый день.

**Target features:**
- Удаление agents/v3/ целиком (LangGraph, 24 микроагента, conductor, APScheduler)
- 8 типов отчётов: финансовый (daily/weekly/monthly), маркетинговый (weekly/monthly), воронка продаж, ДДС, локализация
- Pre-flight проверка данных перед запуском агентов
- Retry при пустом/неполном ответе LLM
- Валидация полноты секций перед публикацией в Notion
- Разбивка playbook.md на модули (core + templates + rules) без потери качества
- Глубина анализа по периоду: daily=компактный, weekly=глубокий, monthly=максимальный
- Простые toggle-заголовки в структуре отчётов
- Простые cron-задачи вместо APScheduler
- Русские названия типов отчётов

**Принцип качества отчёта:** полнота данных, точность, единообразный формат, глубина анализа соответствует периоду, обоснованные гипотезы на базе данных.

**Детальный анализ V2 vs V3:** см. `~/.claude/plans/glimmering-forging-babbage.md`

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-30*
