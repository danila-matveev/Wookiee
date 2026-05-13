# W10 — Catalog Overhaul Log

## 2026-05-13 11:55 — Старт W10

- W9 запушен и задеплоен на prod (https://hub.os.wookiee.shop)
- Получены ~13 скриншотов + расширенный verbal-feedback от пользователя
- Запущены 2 параллельных Explore-агента: фронт-аудит + DB-аудит
- Найдены 3 критичные находки:
  - W10.42: cveta.status_id указывают на product-id вместо color-id (это и есть «миллиард раз» баг)
  - W10.43: junction artikuly_skleyki_* отсутствует
  - W10.39: legacy + new audit пишут параллельно на 9 таблицах
- Зафиксирован TZ на 37 уникальных пунктов в 5 волн
- Продолжаем в ветке `feature/catalog-overhaul-w9` (W10 коммиты с префиксом `w10.X`)

## 2026-05-13 16:20 — W10.1 (Wave A) — Управление колонками реально применяется

- В `/artikuly` и `/tovary` рендер уже корректно использовал `columnConfig.visibleColumns` (W9.5 hook был полностью подключён в thead/tbody) — клики в ColumnsManager там работают.
- В матрице (`ModeliOsnovaTable`) DOM строился из захардкоженных массивов; visibility шла через `display: none`, **порядок колонок не применялся**.
- Фикс (commit `d1de1e1`): MATRIX_RENDER_KEYS + render-метаданные, `renderColumns: useMemo` из `columnConfig.order` + visibility, thead/tbody мапят через switch по ключу, `key={renderColumns.join("|")}` форсит ре-рендер `<table>` при изменении набора.
- localStorage persistence (`catalog-<pageKey>-columns-v2`) и dnd-kit reorder (`handleDragEnd → moveColumn`) — уже работали из W9.5, дополнительной работы не требовалось.
- Out of scope: подвкладки `/matrix → Артикулы (реестр) / SKU (реестр)` — у них вообще нет ColumnsManager (они используют свои MATRIX_ARTIKULY_COLS / MATRIX_TOVARY_COLS). Если потребуется конфигуратор и там, нужен отдельный пункт.

## 2026-05-13 17:30 — Wave A complete (14/14 пунктов, W10.34 перенесён в Wave B)

Cherry-pick результаты:
- A1 (W10.42 DB migration): `a0d20c3` — cveta.status_id перенесён с product-id (8,9,11,12,14) на color-id (34,35). 115 цветов теперь "Продаётся", 19 "Выводим". Trigger CHECK на tip='color' активен.
- A2 (W10.20+W10.5 color util): 5 коммитов `a98d847..641668b`. `colorSwatchStyle(hex)` + `ColorSwatch hex={...}` без `swatchColor` hash fallback. `/tovary` колонка ЦВЕТ: swatch + code + name.
- A3 (W10.2+W10.27+W10.3+W10.28 layout): `6c8d384..b64dbbd`. Horizontal scroll + ellipsis + key={visibleColumns.join('|')} table rerender.
- A4 (W10.4+W10.29 sort): `b97fa3b..2a17661`. `size-utils.ts` с `compareRazmer` применён в model-card TabSKU/Articles, /tovary, /skleyki, /artikuly. W10.34 — InlineColorCell dbl-click — НЕ выполнен (агент не нашёл компонент в worktree от main, переношу в Wave B).
- A5 (W10.1 column manager apply): `d1de1e1` — matrix.tsx рендерит из visible+ordered config.
- A6 (W10.16+W10.31 filters+breadcrumbs): `66310d1, 1e7096b, e9da01d`. `route-labels.ts` mapping для русских крошек. /colors family/status chip-buttons → FilterBar dropdowns. W10.22 — verify-only (chip-rows на /matrix уже не было после W9.4).

Конфликты разрешены: matrix.tsx (3 hunks RAZMER_LADDER → DISPLAY_CHIPS), model-card/skleyka-card/tovary/artikuly/colors (swatchColor → удалён), все W10.20 swatch sites → `ColorSwatch hex={t.cvet_hex}`.

Проверки:
- `tsc --noEmit -p tsconfig.temp.json` — clean (0 errors)
- `vite build` — success, 29.47s, 1.63 MB bundle

Wave B стартует.

## 2026-05-13 18:45 — Wave B complete (6/6 пунктов)

Cherry-pick результаты:
- B1 (W10.7+W10.34 inline edit dbl-click): `e16a609` — InlineTextCell/InlineColorCell/InlineSelectCell заменили `onClick={enter}` → `onDoubleClick={enter}` + hover Pencil indicator.
- B2 (W10.6 ArtikulDrawer): `72451ea` — new file `artikul-card.tsx` (693 lines), tabs Описание/SKU/История, inline validation regex.
- B3 (W10.32 SkuDrawer): `5ec5a4e` — new file `sku-card.tsx` (712 lines), channel statuses.
- B4 (W10.8 validation): in-line с B2/B3.
- B5 (W10.17 drawer corner): `rounded-l-2xl` + `shadow-[-20px_0_40px_rgba(0,0,0,0.08)]` на model-card + skleyka-card + artikul-card + sku-card.
- B6 (W10.38 row-click skleyki): after W10.7 dbl-click — single-click открывает drawer склейки, конфликт разрешён.

Wave C стартует.

## 2026-05-13 20:10 — Wave C complete (4/4 пунктов)

Cherry-pick результаты:
- C1 (W10.9+W10.37 create artikul): `7eff681` + `a6dfdd1` — AddArtikulModal: Razmery multiselect + bulkInsertTovary создаёт SKU per (color × size).
- C2 (W10.10 palette filter): `01e1adb` — фильтр палитры по `semeystvo` в AddArtikulModal.
- C3 (W10.11+W10.33 bulk actions): `b1c17d6` + `530e2bd` + `a5b8da2` + `af1b94a` — BulkActionsBar extended (discriminated union button/dropdown/confirm); bulk status + bulk fabrika + bulk delete для /artikuly.
- C4 (W10.18 multiselect kategorii): `b871980` — AddAtributModal multiselect Категории + bulkLinkAtributToKategorii.

Конфликты разрешены: artikuly.tsx (lucide imports merge: Tag/Download → Factory → Trash2 + ChevronDown), tovary.tsx (ChevronDown/ChevronRight + Trash2/Download/Link2 + bulkDeleteTovary), service.ts (TovarPatch+updateTovar + bulkUpdateArtikulFabrika + bulkDeleteArtikuly).

Проверки:
- `tsc --noEmit -p tsconfig.temp.json` — clean
- `vite build` — success, 4.48s, 1.64 MB bundle

Wave D стартует.

## 2026-05-13 21:55 — Wave D complete (11/11 пунктов)

DB-миграции (`e85d462`):
- W10.43: миграция 027 — junction tables `artikuly_skleyki_wb` / `artikuly_skleyki_ozon` (composite PK, FK на `skleyki_wb`/`skleyki_ozon` соответственно). Backfill из `tovary_skleyki_*` через `tovary.artikul_id`: WB 473 артикула в 27 склейках, OZON 442 в 16. RLS + GRANT для authenticated. БЕЗ audit-триггеров (composite PK без поля id).
- W10.39: миграция 028 — DROP `tr_<table>_izmeneniya` на 9 каталожных таблицах. По факту висели на 4 (artikuly/cveta/modeli/tovary). Функция `log_izmeneniya()` и `infra.istoriya_izmeneniy` сохранены.
- W10.40: миграция 029 — `audit_trigger_fn` на 7 справочниках (atributy, fabriki, tipy_kollekciy, kategoriya_atributy, modeli_osnova_razmery, skleyki_wb, skleyki_ozon). Заодно сняли legacy log_izmeneniya со склеек. `cvet_kategoriya` пропущен (composite PK).
- W10.41: миграция 029 — ALL-политика на `tipy_kollekciy` разделена на INSERT/UPDATE/DELETE (`with_check`/`USING` явно).

Cherry-pick результаты (3 параллельных worktree-агента + D3 в main):
- D2 (W10.23+W10.24+W10.25+W10.36): `2afc79e` + `28e9ee9` + `b363dbd`. SKU в карточке склейки группируются по `artikul_id` (заголовок `artikul.kod/cvet • N SKU (sizes)` с сортировкой по `compareRazmer`). Текст правил заменён на 4 буллета. TabHistory склейки — SELECT из `audit_log` через `.or()` (skleyki_{ch} по row_id + junctions по JSONB.skleyka_id).
- D3 (W10.26+W10.19): `c95522d` + `b44a4d8`. Колонка «Склейка» в /artikuly и /tovary (lazy fetch, `default visible:false`, chip канала + название), клик → новый `SkleykaDrawer` (wrapper над SkleykaCard). Вкладка «Склейки» в model-card — `fetchModelSkleyki`. Drawer-over-drawer для модели → Link на /catalog/skleyki?kanal=&id= (избежать z-index ambiguity).
- D4 (W10.12+W10.13): `d3d7f34` + `216654b`. `fetchAuditForModel` — 3 параллельных запроса (model+modeli / artikuly / tovary), merge DESC. TabHistory: chip-bar фильтр `Все/Модель/Артикулы/SKU` с счётчиками. Кнопка «Откатить» на UPDATE-записях из {modeli_osnova, modeli, artikuly, tovary}, пропуская `id/created_at/updated_at`. `window.confirm` для UX.

Конфликты разрешены: service.ts (две независимые функции fetchSkleykaHistory + fetchAuditForModel + AuditForModelInput — обе сохранены последовательно), model-card.tsx (TabSkleyki от D3 + HistoryFilter/EMPTY_AUDIT_ROWS от D4 — обе сохранены).

Проверки:
- `tsc --noEmit -p tsconfig.temp.json` — clean
- `vite build` — success, 4.11s

Wave E стартует.

## 2026-05-14 02:00 — Wave E complete (3/3 пункта)

Контекст: после 2 неудачных worktree-агентов (1-й крашнулся API-ошибкой
до коммитов, 2-й определил неверный base и отказался стартовать) — Wave E
сделана inline в main worktree.

Commit `0bd5df9` — feat(w10.14+w10.15+w10.35): reference cards drawer.

W10.14 + W10.15 + W10.35: 5 reference-страниц
(brendy/kollekcii/kategorii/tipy-kollekciy/fabriki) — клик по строке
открывает side-drawer `ReferenceDrawer` (новый файл
`pages/catalog/reference-card.tsx`, ~620 строк) вместо RefModal.
Стиль match с ArtikulDrawer — rounded-l-2xl + shadow-2xl + Esc-close.

Drawer:
- Вкладка «Описание» — inline-форма через переэкспортированный
  `FieldInput` из ref-modal (поддерживает все 8 типов полей).
- Вкладка «Привязанные» — секции `linked-models` через FK на
  `modeli_osnova`:
  - brendy → brand_id (read-only, NOT NULL FK — hint объясняет почему)
  - kollekcii → kollekciya_id (add/remove)
  - kategorii → kategoriya_id + ВТОРАЯ секция «Атрибуты категории»
    через kategoriya_atributy junction (linkAtributToKategoriya
    уже был; добавлен unlinkAtributFromKategoriya + picker)
  - tipy-kollekciy → tip_kollekcii_id (add/remove)
  - fabriki → fabrika_id (add/remove)

RefModal остаётся для «Добавить новый». CatalogTable теперь поддерживает
`onRowClick` (игнорирует клики по button/a/input/select, чтобы не
конфликтовать с RowActions).

Service helpers:
- `fetchModeliByRef(column, refId)` — generic по 5 ref-колонкам
- `fetchModeliWithoutRef(column, search, limit)` — picker кандидатов
- `setModelRef(modelId, column, refId|null)` — generic mutation
- `fetchAtributyNotLinkedToKategoriya(...)` + `unlinkAtributFromKategoriya`

Проверки:
- `tsc --noEmit -p tsconfig.temp.json` — clean
- `vite build` — success, 3.73s

Verifier pass стартует.

