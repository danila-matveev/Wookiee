# PIM Phase 3 — продолжение работы

## Промпт для нового чата

```
PIM
Закоммить и верифицировать Phase 3 Product Matrix Editor.

План: docs/superpowers/plans/2026-03-20-product-matrix-phase3-plan.md
Спек: docs/superpowers/specs/2026-03-20-product-matrix-editor-design.md
Phase 1+2 план (для контекста): docs/superpowers/plans/2026-03-20-product-matrix-editor-plan.md

## Что уже сделано (полностью, весь код написан)

Phase 3 (Tasks 16-29) полностью реализована в предыдущем чате:

### Backend (всё в services/product_matrix_api/):
- schemas.py — расширен: Pydantic-схемы для artikuly, tovary, cveta, fabriki, importery, skleyki_wb, skleyki_ozon, sertifikaty + SearchResult/SearchResponse + BulkActionRequest
- app.py — расширен: зарегистрированы 9 новых роутеров
- routes/articles.py — CRUD artikuly (GET list, GET by id, POST, PATCH)
- routes/products.py — CRUD tovary/SKU
- routes/colors.py — CRUD cveta
- routes/factories.py — CRUD fabriki
- routes/importers.py — CRUD importery
- routes/cards.py — CRUD skleyki WB + Ozon (один файл, два префикса)
- routes/certs.py — CRUD sertifikaty
- routes/search.py — глобальный поиск по 10 таблицам (ILIKE + relevance sort)
- routes/bulk.py — массовое обновление любой сущности

### Тесты:
- tests/product_matrix_api/test_schemas_phase3.py — 10 тестов
- tests/product_matrix_api/test_integration_phase3.py — 21 тест (все роуты + search + bulk + OpenAPI)

### Frontend (всё в wookiee-hub/src/):
- lib/matrix-api.ts — расширен: 10 новых типов + 18 API-методов (list/get/create/update для всех + search + bulkAction)
- pages/product-matrix/articles-page.tsx
- pages/product-matrix/products-page.tsx
- pages/product-matrix/colors-page.tsx
- pages/product-matrix/factories-page.tsx
- pages/product-matrix/importers-page.tsx
- pages/product-matrix/cards-wb-page.tsx
- pages/product-matrix/cards-ozon-page.tsx
- pages/product-matrix/certs-page.tsx
- components/matrix/global-search.tsx — Cmd+K dialog с debounced поиском
- components/matrix/mass-edit-bar.tsx — массовое изменение статуса
- pages/product-matrix/index.tsx — переписан: роутер ENTITY_PAGES на все 9 страниц + GlobalSearch + MassEditBar

## Что нужно сделать

1. Запусти верификацию:
   - python3 -m pytest tests/product_matrix_api/ -v (ожидается 54 passed)
   - cd wookiee-hub && npx tsc --noEmit (ожидается 0 ошибок)

2. Если всё зелёное — закоммить 4 коммитами:
   - feat(matrix-api): schemas
   - feat(matrix-api): routes + search + bulk
   - test(matrix-api): integration tests
   - feat(matrix-ui): entity pages + global search + mass edit

3. НЕ коммить файлы, не относящиеся к Phase 3 (scripts/run_price_analysis.py и прочие untracked "... 2.py" дубликаты).
```
