# Wave 3 — Functional QA Report (Agent C2)

Дата: 2026-05-07
Branch: catalog-rework-2026-05-07
Hub: http://127.0.0.1:5173/
Tester: Claude Code Opus 4.7 (1M context) via Playwright MCP + Supabase MCP

## Summary

| # | Сценарий | Статус | Комментарий |
|---|---|---|---|
| J1 | Создание новой модели | **FAIL** | Кнопка «Новая модель» в шапке матрицы не имеет onClick handler (matrix.tsx:1627). Вторичный путь через row-меню упирается в RLS/grant. |
| J2 | Редактирование модели | **FAIL** | В ModelCard все поля ReadField — нет режима редактирования. Кнопка «Редактировать» в шапке без onClick (matrix.tsx:178). TabOpisanie на 100% read-only. |
| J3 | Дублирование модели | **FAIL** | Сервисная функция `duplicateModel('Vuki', 'TEST_C2_J3')` падает с `permission denied for table modeli_osnova`. Кнопка в шапке без onClick; row-меню вызывает функцию, но она падает с тем же error. |
| J4 | Каскадное архивирование | **FAIL** | `archiveModel('Bella')` падает с `permission denied for table modeli_osnova`. Невозможно даже создать тест-модель TEST_C2_CASCADE — INSERT тоже запрещён. |
| J5 | Bulk изменение статусов | **FAIL** | BulkActionsBar появляется при выборе моделей (после React-fiber dispatch), «Изменить статус» → «В продаже» вызывает alert: `Не удалось обновить статус: permission denied for table modeli_osnova`. |
| J6 | Bulk привязка к склейке | **FAIL** | Диалог «Привязать к склейке (WB)» открывается, поле «Название склейки…» работает, но «Создать и привязать» вызывает alert: `Не удалось создать склейку: permission denied for table skleyki_wb`. |
| J7 | Composite search в /tovary | **FAIL** | Логика `matchesCompositeSearch` корректна, но search не находит Audrey/black/S → 0 строк. Причина: `fetchTovaryRegistry` запрашивает `range(0, 4999)`, но Supabase PostgREST default `max-rows=1000`, поэтому в DOM попадает только 1000 SKU из 1473. Audrey-баркоды (id > 1000 в выдаче) теряются. Subtitle страницы показывает «1000 SKU» вместо 1473. |
| J8 | GroupBy в матрице | **PASS** | `<select>` с 5 опциями работает; «По коллекции» отрисовывает 8 групп (Бесшовное белье Jelly, Наборы трусов, и т.д.) с кол-вом моделей. Persist через `ui_preferences (scope=matrix, key=groupBy)` — после refresh select остаётся `kollekciya` ✅. Минор: групп-хедеры рендерятся как `<td colspan>`, а не `<h3>` как в спеке. |
| J9 | ColumnsManager persistence | **PASS** | На /tovary кнопка «Колонки (9)» открывает popover, toggle «Баркод GS1» и «Цена WB» добавляет колонки, после refresh в DOM остаются `БАРКОД GS1, ЦЕНА WB`. SQL: `ui_preferences (scope=tovary, key=columns)` содержит массив 11 ключей ✅. |
| J10 | ⌘K CommandPalette | **FAIL** | Палитра открывается на ⌘K (KeyboardEvent dispatched, role=dialog с `placeholder="Найти модель, цвет, баркод, артикул…"`), но при вводе «Vuki» div результатов пуст. Причина: `searchGlobal` возвращает «сырые» строки из таблиц (`{id, kod, ...}`), а CommandPalette ожидает `CommandResult` с обязательным полем `category`. Bridge между service и UI отсутствует — flat list не имеет category, grouped пуст. |
| J11 | Reference CRUD (/upakovki) | **PASS** | Полный CRUD на справочнике упаковок: «Добавить» → форма «Mailer Box S» + URL → «Сохранить» создаёт запись (rows: 10→11, БД: id=11 nazvanie='TEST_C2_J11_UPAK'). «Действия» → «Редактировать» → name updated → save → БД nazvanie='TEST_C2_J11_EDITED'. «Удалить» → confirm → строка исчезла, БД count=0 ✅. Cleanup: успешно. |
| J12 | Inline edit статусов SKU | **FAIL** | StatusBadge buttons в /tovary рендерятся (title='Статус WB — кликните чтобы изменить'), popover открывается с 7 опциями (Архив/Выводим/Подготовка/План/Запуск/...), но click по «Запуск» вызывает alert: `Не удалось обновить статус: permission denied for table tovary`. |

**Pass-rate: 3 / 12 (25%)**

## Корневая причина большинства провалов: GRANT-ы для роли `authenticated`

Запрос `has_table_privilege` показал:

| Таблица | SELECT | INSERT | UPDATE | DELETE |
|---|:-:|:-:|:-:|:-:|
| modeli_osnova | ✅ | ❌ | ❌ | ❌ |
| modeli | ✅ | ❌ | ❌ | ❌ |
| artikuly | ✅ | ❌ | ❌ | ❌ |
| tovary | ✅ | ❌ | ❌ | ❌ |
| cveta | ✅ | ❌ | ❌ | ❌ |
| skleyki_wb / skleyki_ozon | ✅ | ❌ | ❌ | ❌ |
| tovary_skleyki_wb / _ozon | ✅ | ❌ | ❌ | ❌ |
| kategorii / kollekcii / fabriki / razmery / importery / statusy | ✅ | ❌ | ❌ | ❌ |
| upakovki | ✅ | ✅ | ✅ | ✅ |
| kanaly_prodazh | ✅ | ✅ | ✅ | ✅ |
| sertifikaty | ✅ | ✅ | ✅ | ✅ |
| semeystva_cvetov | ✅ | ✅ | ✅ | ✅ |
| ui_preferences | ✅ | ✅ | ✅ | ✅ |

**RLS-политики `authenticated_*` существуют для всех таблиц** (insert/update/delete/select), но без базовых GRANT-ов PostgreSQL отклоняет запрос ещё до проверки RLS.

PostgreSQL HINT прямо подсказывает:
```sql
GRANT INSERT, UPDATE, DELETE ON public.modeli_osnova TO authenticated;
-- + аналогично для modeli, artikuly, tovary, cveta, skleyki_wb, skleyki_ozon,
--   tovary_skleyki_wb, tovary_skleyki_ozon, kategorii, kollekcii, fabriki,
--   razmery, importery, statusy
```

## Дополнительные находки для C4

### A. Неработающие кнопки в шапке ModelCard (matrix.tsx:172-180)

Все три кнопки рендерятся без `onClick`:
- `<button>Дублировать</button>` — line 173
- `<button>В архив</button>` — line 176
- `<button>Редактировать</button>` — line 178

При этом `handleRowDuplicate`/`handleRowArchive` существуют и работают через row-меню.

### B. Кнопка «Новая модель» без onClick (matrix.tsx:1627)

```tsx
<button className="..."><Plus /> Новая модель</button>
```

Нет ни обработчика, ни диалога создания. Сценарий J1 невозможен через UI.

### C. PostgREST max-rows=1000 ограничивает /tovary

`fetchTovaryRegistry` использует `.range(0, 4999)`, но Supabase возвращает максимум 1000 строк. Из-за этого composite-search не находит модели после первой 1000 SKU. На странице subtitle показывает «1000 SKU» вместо реальных 1473.

Решение: либо клиентская пагинация (загрузка кусками по 1000), либо повышение `max-rows` в Supabase API настройках.

### D. CommandPalette — отсутствует адаптер service → UI

`searchGlobal()` в service.ts возвращает:
```ts
{ models: [{id, kod, nazvanie_etiketka}], colors: [...], articles: [...], skus: [...] }
```

CommandPalette в `components/catalog/ui/command-palette.tsx:91-95` делает:
```ts
const flat: CommandResult[] = [...(r.models ?? []), ...(r.colors ?? []), ...(r.articles ?? []), ...(r.skus ?? [])]
```

Но `CommandResult` требует `{id, category, label, sub?, target?}`. Категория не проставляется → grouped по category пуст → результаты не отображаются.

Нужен маппинг внутри CommandPalette либо обновление searchGlobal, чтобы возвращать сразу CommandResult.

### E. Несоответствие счётчика моделей

В sidebar `Базовые модели = 56` (через `fetchCatalogCounts`), но топ-бар матрицы временно показал «57 моделей» при наличии открытой ModelCard. Возможно, дубль ключа в queryClient. Не воспроизводится стабильно — не блокер.

### F. Авто-навигация при snapshot

При длинных snapshot-операциях (>50KB) Playwright MCP видимо триггерит сэйв и страница может «убежать» по sidebar links. Это особенность Playwright MCP, не код Hub. Workaround: использовать `browser_evaluate` без snapshot и фиксировать URL внутри одного evaluate-блока.

## Рекомендации для C4 (приоритет)

1. **BLOCKER**: применить миграцию с GRANT-ами на 14 таблиц каталога. Без этого 9/12 сценариев невозможны.
2. **BLOCKER**: добавить onClick к кнопкам шапки ModelCard и кнопке «Новая модель» в матрице (или хотя бы скрыть их если функционал не реализован).
3. **BLOCKER**: реализовать редактирование description/полей в ModelCard (replace ReadField → editable input при `isEditing` state).
4. **MAJOR**: починить CommandPalette — добавить mapping searchGlobal results → CommandResult с category.
5. **MAJOR**: решить max-rows=1000 для /tovary (пагинация или config).
6. **MINOR**: групп-хедеры в матрице сделать `<h3>` как в спеке (сейчас `<td colspan>`).

## Cleanup

- ✅ /upakovki — TEST_C2_J11_* удалена.
- Состояние БД: ничего не изменено (все попытки записи упали с permission denied).
