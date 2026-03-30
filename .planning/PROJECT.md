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

## Current Milestone: v1.0 — UX Redesign

**Goal:** Переделать Product Matrix Editor в рабочую PIM-систему по образу Notion database — с правильной навигацией, detail panel, всеми полями из спецификации, фильтрацией и CRUD.

**Target features:**
- Notion-like table view with proper column headers
- Right-side detail panel instead of inline editing
- All fields from Google Sheets spec viewable/editable at correct hierarchy level
- Left catalog navigation (ModelOsnova → Model → Artikul → Tovar)
- CRUD operations (create, edit, archive)
- Filtering and sorting
- Read-only fields protection (barcode, marketplace IDs)
- Proper reference field resolution (category, collection, factory names)

**Data source reference:** Google Sheets `19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg`
- "Все модели" — 90+ columns
- "Все артикулы" — 23 columns
- "Все товары" — 86 columns

---
*Last updated: 2026-03-22*
