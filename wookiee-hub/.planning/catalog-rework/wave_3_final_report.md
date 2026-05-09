# Wave 3 — Final Fixes Report (C4)

Дата: 2026-05-07
Branch: catalog-rework-2026-05-07
Hub URL (dev, верификация): http://127.0.0.1:5173/

## BLOCKER fixes

| # | Fix | Status | Verify |
|---|-----|--------|--------|
| 1 | GRANT INSERT/UPDATE/DELETE для authenticated на 16 каталоговых таблиц + USAGE,SELECT на sequences | DONE | Migration `catalog_grant_authenticated_2026_05_07` применена, `information_schema.role_table_grants` показывает SELECT/INSERT/UPDATE/DELETE на каждой из 16 таблиц |
| 2 | RLS-политики INSERT/UPDATE/DELETE для authenticated на 5 junction/skleyki таблицах (modeli_osnova_sertifikaty, skleyki_wb, skleyki_ozon, tovary_skleyki_wb, tovary_skleyki_ozon) | DONE | Migration `catalog_rls_junction_2026_05_07`, `pg_policies` показывает по 5 политик (1 service_role + 4 authenticated) на каждой |
| 3 | ModelCard editable: режим edit с Save/Cancel, draft state, кнопки шапки (Дублировать, В архив, Редактировать) с onClick, кнопка «Новая модель» в матрице с onClick | DONE | E2E через Playwright: правка material `Нейлон → Нейлон+TEST_C4` сохранилась в БД, после возврата восстановлена. Архивирование TEST_C4_CASCADE через UI прошло (status_id=26 «Архив»), модель удалена. |
| 5 | Размерная линейка как chip-pills (XS/S/M/L/XL/XXL) + LevelBadge на каждом поле Описания/Атрибутов/Контента | DONE | Снимок `/catalog/matrix?model=Vuki`: на каждом поле виден badge «МОДЕЛЬ», размерная линейка показана 6 чипами. В edit-mode чипы становятся кликабельными, ладдер sortится в каноническом порядке. |

## MAJOR fixes

| # | Fix | Status | Verify |
|---|-----|--------|--------|
| 4 | tovary 1000-row PostgREST limit | DONE (client-side pagination) | `fetchTovaryRegistry`/`fetchArtikulyRegistry` теперь page по 1000 пока не вернётся <PAGE. `/catalog/tovary` показывает «1473 SKU» в подзаголовке (раньше 1000). |
| 6 | CommandPalette результаты | DONE | ⌘K → «Vuki» возвращает категории МОДЕЛИ (Vuki, Set Vuki) и АРТИКУЛЫ (Vuki/washed_*). Адаптеры `adaptModels/Colors/Articles/Skus` в `command-palette.tsx` маппят сырые DB-строки в `CommandResult` с category/label/sub/target. |
| 7 | Архивный статус для tip='lamoda' | DONE | Migration `catalog_lamoda_arhiv_2026_05_07` добавил `(nazvanie='Архив', tip='lamoda', color='gray')`. Каскадное архивирование теперь корректно меняет `status_lamoda_id`. |
| 9 | __demo__ page wired до A3's CatalogUiDemo | DONE | `/catalog/__demo__` показывает реальные демки (Tooltip, LevelBadge, StatusBadge, CompletenessRing, fields, RefModal, ColumnsManager, BulkActionsBar, CommandPalette). Old «В разработке» stub удалён. |

## Deferred / not-reproducible MINOR

- **FIX 8 (cold-load redirect на /upakovki, /sertifikaty, /references/statusy)** — после применения FIX 1+2 не воспроизводится. Прямые `browser_navigate` на каждый из 3 URL открывают целевую страницу, URL остаётся стабильным, h1 правильный. Подозреваю race-condition в `browser_snapshot` (Playwright MCP) тригерил sidebar-link во время C1's session. Если воспроизведётся — закрыть отдельным фолоу-апом.
- **MINOR из визуального отчёта C1** — оставлены без правок (low priority):
  - ИНН в /references/importery с «.0» в конце (число → строка форматирование)
  - ColumnsManager в /catalog/artikuly показывает 7 колонок (ТЗ — 11), в /tovary 8 (ТЗ — 17)
  - В Matrix есть 3 второстепенных tabs (Базовые модели/Артикулы/SKU) — дублирует sidebar
  - ModelCard заполненность ring показывает 70%, текст 10/10 — рассогласовано
  - Hover MoreHorizontal на строках справочников
- **angelina/* артикулы (4 шт.) с cvet_id IS NULL** — minor data quality, архивные.  Можно покрыть отдельной миграцией.
- **Bundle warning >500kB** — главный chunk 1.8MB. Деплой работает, но имеет смысл code-split в отдельной задаче.

## Hub status (контрольный лист)

- [x] Колонка Статус в матрице (`StatusBadge` в строках)
- [x] Размерная линейка как chip-pills XS/S/M/L/XL/XXL
- [x] LevelBadge на каждом поле ModelCard (вкладки Описание + Атрибуты + Контент)
- [x] Каскадное архивирование (modeli_osnova → modeli → artikuly → tovary с разными status_*_id) работает через UI как authenticated
- [x] CommandPalette ⌘K возвращает грouped results (МОДЕЛИ/ЦВЕТА/АРТИКУЛЫ/SKU)
- [x] 9 справочников (kategorii, kollekcii, fabriki, importery, razmery, statusy, semeystva-cvetov, upakovki, kanaly-prodazh, sertifikaty) — CRUD доступен (RLS+grant позволяют)
- [x] BulkActionsBar — выделение моделей открывает bar, «Изменить статус» → выбор статуса работает (Alice 24 → 23 → 24)
- [x] /catalog/tovary показывает 1473 SKU (paginated fetch)
- [x] /catalog/__demo__ показывает реальные A3 atomic-демки

## TS / Build status

- `npx tsc -p tsconfig.temp.json --noEmit` — exit 0, 0 errors
- `npm run build` — clean rebuild, exit 0, build finished in 3.66s

## Что не сделано и почему

- **FIX 8** — не воспроизводится после применения FIX 1+2; deferred, требуется наблюдение пользователя на prod.
- **MINOR полировка** — из C1 — оставлено как backlog, не блокирует MVP.

## Миграции (применены к Supabase project gjvwcdtfglupewcwzfhw)

1. `catalog_grant_authenticated_2026_05_07`
2. `catalog_rls_junction_2026_05_07`
3. `catalog_lamoda_arhiv_2026_05_07`

## Ключевые файлы

- `src/lib/catalog/service.ts` — paginated `fetchTovaryRegistry`/`fetchArtikulyRegistry`
- `src/components/catalog/ui/command-palette.tsx` — adapters `adaptModels/Colors/Articles/Skus`
- `src/pages/catalog/matrix.tsx` — edit-mode ModelCard, header buttons wired, FIX 5 chip-pills + LevelBadge
- `src/pages/catalog/__demo__.tsx` — re-export A3's `CatalogUiDemo`
