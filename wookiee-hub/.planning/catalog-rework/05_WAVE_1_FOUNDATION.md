# Wave 1 — Foundation (4 параллельных агента)

**Цель:** Заложить базу: типы, atomic UI, layout, расширенные мутации в service.ts.
**Параллелизация:** ДА — 4 worktree-агента запускаются одновременно.
**Зависимость:** Wave 0 должен быть полностью готов и зеркфижен.

## Архитектура работы

Каждый агент работает в своём worktree, по завершении создаёт PR. После всех 4 PR — merge в main, верификация Wave 1, переход на Wave 2.

```
main
 ├── wave-1-a1-migrations    (агент A1)
 ├── wave-1-a2-service       (агент A2)
 ├── wave-1-a3-atomic-ui     (агент A3)
 └── wave-1-a4-layout        (агент A4)
```

После merge порядок:
1. A1 → main (типы и SQL helpers)
2. A2 → main (service.ts, зависит от A1)
3. A3 → main (atomic UI компоненты, не зависят)
4. A4 → main (layout, зависит от A3)

## Агент A1 — TypeScript Types + Supabase generated types

### Промпт
```
Ты Wave 1 Agent A1 — обновление TypeScript типов под новую схему БД Wookiee Hub.

Контекст:
- Wave 0 уже выполнена: schema статусов расширена, новые таблицы созданы
- Файл типов: src/lib/catalog/types.ts (или supabase generated types)
- Источники: `.planning/catalog-rework/01_DATA_AUDIT.md`, `02_STATUSES_FROM_SHEET.md`, MVP-файл

Задачи:
1. Через mcp__plugin_supabase_supabase__generate_typescript_types обновить supabase types
2. Убедиться, что в src/lib/catalog/types.ts есть типы:
   - Status (id, nazvanie, tip, color)
   - Kategoriya (с opisanie)
   - Kollekciya (с opisanie, god_zapuska)
   - Fabrika (с gorod, kontakt, email, wechat, specializaciya, leadtime_dni, notes)
   - Importer (с short_name, kpp, ogrn, bank, rs, ks, bik, kontakt, telefon)
   - Razmer (с ru, eu, china)
   - SemeystvoCveta (id, kod, nazvanie, opisanie, poryadok)
   - Upakovka (полный набор)
   - KanalProdazh (id, kod, nazvanie, short, color, active)
   - UiPreference (id, scope, key, value JSONB)
   - Cvet (с hex, color_en, lastovica, semeystvo_id)
   - ModelOsnova (с notion_strategy_link, yandex_disk_link, upakovka_id)
   - Sertifikat (полный набор)
3. Добавить FieldLevel = 'model' | 'variation' | 'artikul' | 'sku'
4. Добавить ATTRIBUTES_BY_CATEGORY словарь — копировать из MVP wookiee_matrix_mvp_v4.jsx (строки ~150-280)
5. Добавить FIELD_LEVEL словарь — копировать из MVP (строки ~280-350)
6. Не ломать существующие импорты (lib/catalog/types.ts уже использует кучу мест)

Verify:
- npm run build (TypeScript check, 0 errors)
- npm run lint (0 errors)
- grep -r "import.*types" src/pages/catalog/ — все импорты резолвятся

Когда готово — git commit, push в ветку wave-1-a1-types, отчёт на 200 слов.
```

## Агент A2 — service.ts (мутации + расширенные fetch'еры)

### Промпт
```
Ты Wave 1 Agent A2 — расширение src/lib/catalog/service.ts под все нужные операции.

Контекст:
- Wave 0 готова, A1 ввёл новые типы
- Файл: src/lib/catalog/service.ts
- В нём уже есть: fetchSkleykaDetail, insertKategoriya/Kollekciya/Fabrika/Importer/Razmer
- Не сломать существующие: fetchModeliOsnova, fetchModelDetail, fetchTovaryRegistry (с .range(0, 4999))

Задачи:
1. Добавить мутации для всех CRUD на справочники:
   - update / delete для kategorii, kollekcii, fabriki, importery, razmery
   - insert / update / delete для semeystva_cvetov, upakovki, kanaly_prodazh, sertifikaty
2. Добавить операции на cveta:
   - insertCvet, updateCvet, deleteCvet (мягкое — статус Архив)
3. Добавить операции на modeli_osnova:
   - createModel(payload) → возвращает kod
   - updateModel(kod, patch) — частичное обновление любых полей
   - duplicateModel(kod, newKod) — копирует только modeli_osnova-запись (без вариаций/артикулов/SKU)
   - archiveModel(kod) — каскадно: модель → variation→ artikuly → tovary в статус «Архив»
4. Добавить bulk-операции:
   - bulkUpdateModelStatus(kods[], status_id)
   - bulkUpdateTovaryStatus(barkods[], status_id, channel: 'wb'|'ozon'|'sayt'|'lamoda')
   - bulkLinkTovaryToSkleyka(barkods[], skleykaId, channel)
   - bulkUnlinkTovaryFromSkleyka(barkods[], channel)
5. Добавить операции на ui_preferences:
   - getUiPref(scope, key) → JSONB
   - setUiPref(scope, key, value)
6. Добавить расширенные fetcher'ы:
   - fetchSemeystvaCvetov, fetchUpakovki, fetchKanalyProdazh, fetchSertifikaty
   - fetchModeliOsnovaCounts() → { kategoriya_id: count } для sidebar счётчиков
   - searchGlobal(query) → { models, colors, articles, skus } для CommandPalette
7. Все мутации обновляют related queryClient.invalidateQueries

Структура файла остаётся плоской функциональной, без классов.

Verify:
- npm run build (0 errors)
- ручной smoke: дев-сервер запускается, существующие страницы работают

Когда готово — git commit, push в ветку wave-1-a2-service, отчёт на 200 слов.
```

## Агент A3 — Atomic UI компоненты

### Промпт
```
Ты Wave 1 Agent A3 — atomic UI компоненты каталога Wookiee Hub.

Контекст:
- Source of truth: /Users/danilamatveev/Projects/Wookiee/redesign + PIX/wookiee_matrix_mvp_v4.jsx
- Целевая папка: src/components/catalog/ui/
- Стилизация: .catalog-scope CSS class (не ломать дарк-тему Hub)

Задачи (создать или довести до состояния как в MVP):
1. **Tooltip** (`tooltip.tsx`) — позиционируемая подсказка на hover
2. **LevelBadge** (`level-badge.tsx`) — pill «Модель» | «Вариация» | «Артикул» | «SKU» с цветом
   - props: level: FieldLevel
3. **StatusBadge** (`status-badge.tsx`) — pill + ring + dot, по statusy.color
   - props: status: { nazvanie, color }
4. **CompletenessRing** (`completeness-ring.tsx`) — SVG-кольцо с %, цвет порогами:
   - <30 red, 30-69 amber, 70-89 blue, 90+ green
5. **Fields** (`fields.tsx`) — TextField, NumberField, SelectField, StringSelectField, MultiSelectField, TextareaField
   - props: { label, value, onChange, level?: FieldLevel, readonly?: boolean, placeholder? }
   - В readonly mode: показать значение как plain text + LevelBadge
   - В edit mode: input/select + LevelBadge сбоку
6. **FieldWrap** (`field-wrap.tsx`) — обёртка для Field с label слева и LevelBadge справа
7. **ColumnsManager** (`columns-manager.tsx`) — popover-панель чекбоксов
   - props: { columns: { key, label, default }[], scope: string, key: string, onChange }
   - Загружает/сохраняет состояние через ui_preferences (scope+key)
8. **RefModal** (`ref-modal.tsx`) — расширенная модалка для CRUD справочников
   - props: { title, fields: FieldDef[], initial, onSave, onCancel }
   - Поддержать: text, number, textarea, select, multiselect, file_url (хранится как varchar)
9. **BulkActionsBar** (`bulk-actions-bar.tsx`) — фиксированный нижний бар при selectedItems > 0
   - props: { selectedCount, actions: { id, label, icon, onClick }[], onClear }
10. **CommandPalette** (`command-palette.tsx`) — глобальный ⌘K поиск
    - props: { open, onClose, query, onQuery }
    - Через service.searchGlobal по моделям, цветам, баркодам, OZON-артикулам, WB-номенклатурам

Все компоненты:
- Полная типизация props (никаких `any`)
- DM Sans (body), Instrument Serif italic для заголовков (.cat-font-serif)
- Прокинуть className через `cn` utility
- Зависят только от lucide-react, react, типов из A1

Verify:
- TypeScript check (0 errors)
- npm run lint (0 errors)
- Создать src/components/catalog/ui/__demo__.tsx — страница с примерами всех компонент. Запустить dev сервер, открыть, проверить визуально (Playwright screenshot).

Когда готово — git commit, push в ветку wave-1-a3-atomic-ui, отчёт на 250 слов с приложенным screenshot.
```

## Агент A4 — Layout (Sidebar + TopBar + Routing)

### Промпт
```
Ты Wave 1 Agent A4 — обновление Layout каталога Wookiee Hub.

Контекст:
- Source of truth: MVP wookiee_matrix_mvp_v4.jsx (компоненты Sidebar, TopBar)
- Файлы: src/pages/catalog/_layout.tsx (или layout.tsx), src/components/catalog/sidebar.tsx
- ⚠ Не ломать существующее routing (хеш-параметры, useSearchParams)

Задачи:
1. **Sidebar — состав** (10 пунктов вместо 6):
   - Базовые модели (counts: count(*) FROM modeli_osnova)
   - Цвета (count(*) FROM cveta WHERE status != Архив)
   - Артикулы (count(*) FROM artikuly)
   - Товары/SKU (count(*) FROM tovary)
   - Склейки (count(*) FROM sklejki)
   - Категории (count(*) FROM kategorii)
   - Коллекции (count(*) FROM kollekcii)
   - Производители (count(*) FROM fabriki)
   - Юрлица (count(*) FROM importery)
   - Размеры (count(*) FROM razmery)
   - **Семейства цветов** (новое)
   - **Упаковки** (новое)
   - **Каналы продаж** (новое)
   - **Сертификаты** (новое)
2. **Sidebar счётчики** — useQuery('catalog-counts'), staleTime 60s
3. **Sidebar футер** — блок «Данила · CEO» с Avatar + role
4. **TopBar breadcrumb** — динамический «Каталог > Матрица > [Модель]» через useLocation + state
5. **TopBar кнопка ⌘K** — открывает CommandPalette из A3
6. **Глобальный hotkey ⌘K** — useEffect на keydown (e.metaKey || e.ctrlKey) && e.key === 'k'
7. **Esc** — закрывает модалки/палитру
8. **Роутинг** добавить:
   - /catalog/semeystva-cvetov
   - /catalog/upakovki
   - /catalog/kanaly-prodazh
   - /catalog/sertifikaty

Стилизация:
- Sidebar 240px, padding 16px, gap 4px между пунктами
- активный пункт — pill с bg-stone-100, иконка + label + count
- font: DM Sans (включить в index.html через Google Fonts)
- TopBar — sticky, h-14, border-bottom

Verify:
- TS check, lint
- Запустить dev сервер, перейти по всем 10+ пунктам Sidebar
- ⌘K открывает палитру, Esc закрывает
- Playwright screenshot главного экрана и сравнить с MVP

Когда готово — git commit, push в ветку wave-1-a4-layout, отчёт на 200 слов + screenshots.
```

## Параллельный запуск 4 агентов

В мастер-сессии (08_EXECUTE.md) запускать все 4 одновременно:

```python
# Псевдокод оркестратора:
parallel_tasks = [
    Agent(A1_prompt, isolation='worktree', branch='wave-1-a1-types'),
    Agent(A2_prompt, isolation='worktree', branch='wave-1-a2-service'),
    Agent(A3_prompt, isolation='worktree', branch='wave-1-a3-atomic-ui'),
    Agent(A4_prompt, isolation='worktree', branch='wave-1-a4-layout'),
]
results = parallel_tasks.run_concurrently()
```

После всех 4 → merge порядок A1, A2, A3, A4 → проверка Wave 1.

## Verification Wave 1
- [ ] npm run build — 0 errors
- [ ] npm run lint — 0 errors
- [ ] Dev server стартует
- [ ] Sidebar показывает все 14 пунктов с счётчиками
- [ ] ⌘K открывает CommandPalette, поиск возвращает результаты
- [ ] /catalog/__demo__ показывает все atomic UI правильно
- [ ] Все существующие страницы каталога открываются без regressions

После прохождения → запуск Wave 2.
