# Marketing v4 Fidelity — Design

**Дата:** 2026-05-12
**Эталон:** `docs/superpowers/specs/wookiee_marketing_v4.jsx` (780 строк)
**Контекст:** `docs/superpowers/plans/2026-05-09-marketing-hub-impl-v2-phase1-verification.md`, `2026-05-09-marketing-hub-impl-v2-phase2-verification.md`

## 1. Контекст и цели

Раздел «Маркетинг» в Wookiee Hub (`/marketing/promo-codes`, `/marketing/search-queries`) находится после Phase 2 (мерж `4968d53`, 2026-05-10) в state «функционал есть, визуал и UX не соответствуют эталону». Эталон — `wookiee_marketing_v4.jsx`: проработанный JSX-прототип с пиксельной точностью верстки, конфигурируемой группировкой и полной воронкой деталки.

Параллельно за 2026-05-12 в main залиты:
- `marketing.search_queries_weekly` + `marketing.search_query_product_breakdown` (sync v2.0.0, commits `39e4146`+`05e007a`+`d14a1f7`) — 1396 weekly + 18750 breakdown за 12 недель bootstrap
- `marketing.promo_product_breakdown` (promocodes sync v2.1.0, commits `f301f41`+`fe47c74`+`33585e5`)

Цели проекта:
1. **Pixel-perfect** соответствие визуала эталону v4
2. **Полный CRUD** работает на реальных данных (promo edit, status edit, add-формы подключены)
3. **Конфигурируемая группировка** — 3 пресета через `ui_preferences`, дефолт «По направлению» (= 4 группы v4)
4. **Замкнутый цикл** UI → БД → Sheets → WB API → БД → UI (bridge-логика в sync + endpoint для кнопки «Обновить»)

Non-goals: переписывание остального Hub, изменение Catalog, новые таблицы маркетинга, миграции enum статусов.

## 2. Архитектурные решения

### 2.1. Палитра — переопределение семантических токенов через `data-section`

В `index.css` блок `[data-section="marketing"] { --card: ...; --muted: ...; --border: ... }` со stone-эквивалентами. Атрибут `data-section="marketing"` ставится в `MarketingLayout`. CRM-компоненты (`@/components/crm/ui/Badge`, `Button`, `Input`) **не используем** внутри маркетинга — для маркетинга локальные реплики `components/marketing/{Badge,Button,Input}.tsx` (паттерн `Badge` из JSX:199-203). Это изолирует визуал маркетинга и оставляет CRM-раздел нетронутым.

**Отвергнутая альтернатива:** прямые `bg-stone-*` классы в JSX. Минус — разрыв с остальным Hub. CSS-переменные через scope — единая точка переключения при будущей унификации палитры.

### 2.2. Конфигурируемая группировка — паттерн `catalog/matrix.tsx`

Dropdown «Группировка» с **3 пресетами** (минимизация overengineering):

| value | label | Источник ключа |
|---|---|---|
| `direction` (default) | По направлению | brand / external / cr_general / cr_personal — иконки 🔤/📦/👥/👤 |
| `entity_type` | По типу сущности | brand / nomenclature / ww_code |
| `none` | Без группировки | — |

Persistence: `ui_preferences (scope, key) = ('marketing.search-queries', 'groupBy')` и `('marketing.promo-codes', 'groupBy')`. Helpers `getUiPref/setUiPref` выносятся из `lib/catalog/service.ts` в общий `lib/ui-preferences.ts`.

Расширение опций (по каналу/модели/кампании/статусу) — отдельная задача после feedback от пользователя.

### 2.3. UI-маппинг статусов вместо миграции enum

Текущий enum БД: `active|paused|archived`. Эталон v4: `active|free|archive`. Решение:

```ts
const STATUS_UI_TO_DB = { active: 'active', free: 'paused', archive: 'archived' } as const
const STATUS_DB_TO_UI = { active: 'active', paused: 'free', archived: 'archive' } as const
const STATUS_LABELS = { active: 'Используется', free: 'Свободен', archive: 'Архив' } as const
const STATUS_COLORS = { active: 'green', free: 'blue', archive: 'gray' } as const
```

Bidirectional словарь применяется в `StatusEditor`, `Badge` в таблице, `useUpdateSearchQueryStatus` (mutation конвертирует UI→DB перед отправкой). БД не трогаем.

**Отвергнутая альтернатива:** ALTER TYPE / переименование значений. Риск миграции данных, риск сломать сторонних потребителей. UI-маппинг — нулевой риск, легко откатить.

### 2.4. Detail panel — split-pane с responsive fallback

Эталон v4: статичная панель `w-[420px]` справа, остаётся в потоке. Текущий код использует drawer (`@/components/crm/ui/Drawer`). Перестраиваем на split-pane с breakpoint `lg:`:

- `lg:` (≥ 1024px): split-pane `<aside className="w-[420px] border-l">` рядом с таблицей
- `< lg`: drawer fallback (выезжающая панель)

### 2.5. Bridge-логика в sync для замыкания CRUD-цикла

**Текущий gap (Phase 2 sync v2.0.0/v2.1.0):**
- `sync_search_queries.py` читает список слов **только из Sheets col A**, не из БД
- `sync_promocodes.py` читает dictionary **только из Sheets**
- UI-формы (`AddPromoPanel`, `AddBrandQueryPanel`, `AddWWPanel`) пишут в `crm.*` напрямую
- Новые записи через UI **не попадают в Sheets** → следующий sync их игнорирует → метрики не собираются

**Решение:** новая функция `_ensure_db_words_in_sheets()` в каждом из sync-скриптов, запускается до основного pull-from-WB:
1. SELECT из БД (`crm.substitute_articles.code` + `crm.branded_queries.query` для search-queries, `crm.promo_codes` для promocodes)
2. Чтение текущих значений Sheets col A
3. Diff → недостающие добавляются в Sheets в правильную секцию (по `purpose` для search-queries, в dictionary для promocodes)
4. Парсинг разделителей-заголовков («Артикулы внешний лид», «Креаторы общие:», «Креаторы личные:», «Соцсети:») для определения позиции вставки

**Отвергнутая альтернатива:** UI пишет в Sheets напрямую через Google API proxy. Сложно (новые секреты, новые тайминги, конфликт с manual edits). Bridge в существующем sync — минимальное изменение.

### 2.6. Endpoint для кнопки «Обновить» — `analytics_api` subprocess

`POST /api/marketing/sync/{job_name}` (`job_name ∈ {search-queries, promocodes}`):
- Запускает subprocess `python scripts/run_{job}_sync.py --mode last_week`
- Возвращает `{job_name, status: "running", started_at, sync_log_id}`

`GET /api/marketing/sync/{job_name}/status`:
- Читает свежую запись из `marketing.sync_log` по `job_name`
- Возвращает `{status, started_at, finished_at, rows_processed, expected_rows, error}`

Frontend: при клике на «Обновить» в `UpdateBar` → POST → `useQuery({queryKey: ['sync-status', job], refetchInterval: 2000, enabled: isSyncing})`. UpdateBar показывает live-progress `«Обновление: 234 / 1396 строк»`. Пользователь не блокируется (long-running 5-10 минут — фоновая задача).

**Отвергнутая альтернатива:** Supabase Edge Function. Минус — timeout 25s по дефолту, новая инфраструктура, новые секреты. Endpoint в existing FastAPI на сервере — проще.

### 2.7. View `marketing.search_query_stats_aggregated` — переключение на `search_queries_weekly`

Текущий RPC агрегирует из `crm.substitute_article_metrics_weekly` (legacy) — заведомо неполные данные для брендов. **Реальные метрики теперь в `marketing.search_queries_weekly`** (по `search_word`).

Новый RPC делает JOIN:
- `crm.substitute_articles.code ↔ marketing.search_queries_weekly.search_word` (для WW-кодов и номенклатур)
- `crm.branded_queries.query ↔ marketing.search_queries_weekly.search_word` (для брендов)

Это закрывает баг «бренды с нулями» без миграций и новых таблиц.

## 3. Frontend Design (детально)

### 3.1. MarketingLayout

Новый файл `wookiee-hub/src/layouts/MarketingLayout.tsx`. Структура из JSX:773-776:
- `data-section="marketing"` для активации stone-палитры
- Sub-sidebar `w-44` с заголовком «МАРКЕТИНГ» и двумя пунктами (`Промокоды` `Percent`, `Поисковые запросы` `Hash`)
- `<Outlet />` для дочерних страниц

Регистрация в `router.tsx`: оборачиваем оба marketing-роута:
```ts
{ path: "/marketing", element: <MarketingLayout />, children: [
  { path: "promo-codes", lazy: () => import('./pages/marketing/promo-codes') },
  { path: "search-queries", lazy: () => import('./pages/marketing/search-queries') },
]}
```

### 3.2. Локальные UI-компоненты для маркетинга

`components/marketing/`:
- `Badge.tsx` — реплика JSX:199-203 (4 цвета green/blue/amber/gray, compact mode)
- `Button.tsx` — primary `bg-stone-900` / secondary outline (опционально, минимально)
- `Input.tsx` — стиль из JSX `iCls` const

CRM-компоненты не импортируются. Текущие импорты `@/components/crm/ui/{Badge,Drawer,Button,Input}` в `AddPromoPanel`/`AddBrandQueryPanel`/`AddWWPanel`/`PromoDetailPanel`/`SearchQueryDetailPanel` — заменяются на локальные.

### 3.3. Типография

Подключение в `index.css`:
```css
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Instrument+Serif:ital@0;1&display=swap');
```

Заголовки страниц:
```jsx
<h1 className="text-stone-900" style={{ fontFamily: "'Instrument Serif', serif", fontSize: 24, fontStyle: 'italic' }}>
  Поисковые запросы
</h1>
```

### 3.4. SearchQueriesTable

**Колонки (11):** Запрос / Артикул / Канал / Кампания / Частота / Перех. / CR→корз / Корз. / CR→зак / Заказы / CRV (JSX:589-599 точно).

**Фильтры (вверху страницы, JSX:554-568):**
- Pills «Модель»: `Все` + uniq из `model_hint` view
- Pills «Канал»: `Все` + uniq из `channel` view (label, не slug)

**Над таблицей (JSX:575-583):**
- Text search (по query/art/nm/ww/campaign/model/channel)
- DateRange (default `WEEK_DATES[36]` ≈ 4 недели назад → today)
- GroupBySelector (новый компонент)
- Счётчик `N записей`

**Группировка** — три пресета (см. 2.2). Дефолт `direction` рендерит 4 секции с иконками 🔤/📦/👥/👤 (`SectionHeader` обновляется).

**Sticky tfoot** — сумы по видимым строкам (JSX:634-645): Частота / Перех / CR→корз / Корз / CR→зак / Заказы / CRV.

**Хуки:** существующие `useSearchQueries`, `useSearchQueryStats` — без изменений API. Новый `useGroupByPref('marketing.search-queries')` для persistence.

### 3.5. SearchQueryDetailPanel

Split-pane (`w-[420px]`, JSX:387-462).

**Шапка:** query font-mono + StatusEditor + channel badge + campaign hint + close button.

**Meta-блок** (если есть nm): Номенклатура / WW-код / Артикул / Модель (JSX:405-414).

**Воронка за период** (JSX:417-432) — 7 строк:
- Частота (большая)
- Переходы (большая)
- CR перех → корзина (маленькая, indented)
- Корзина (большая)
- CR корзина → заказ (маленькая, indented)
- Заказы (большая)
- CR перех → заказ (итоговый, отделён бордером)

**Weekly table** (JSX:436-458) с toggle `«За период» / «Все»`. Колонки: Нед / Част / Перех / Корз / Зак / CRV. Empty state для брендов в Phase 2A: «Метрики появятся после Phase 2B».

**StatusEditor** (JSX:352-374): dropdown с 3 опциями (Используется/Свободен/Архив), badge с галочкой на текущем. Bidirectional маппинг к БД (см. 2.3).

### 3.6. AddWWPanel

Каскадная форма (JSX:465-494):
1. SelectMenu «Модель» — options из `useModeli()` (existing hook)
2. SelectMenu «Цвет» — options зависят от модели (через `useArtikulyForModel`)
3. SelectMenu «Размер» (XS/S/M/L/XL)
4. Auto-resolved SKU карточка: `Привязан: Wendy/white_S` + `NM: 163151603` (JSX:483) или `SKU не найден` в amber (JSX:484)
5. Input «WW-код» (uppercase, font-mono)
6. SelectMenu «Канал» — options из `useChannels()`, `allowAdd` (новый канал → `INSERT INTO marketing.channels`)
7. SelectMenu «Кампания / блогер» — options из distinct `campaign_name` БД, `allowAdd`
8. Submit → `useCreateSubstituteArticle()`

Disabled submit пока не: `matched && ww && channel`.

### 3.7. AddBrandQueryPanel

Минимальная форма (текущая реализация ОК, лёгкий refactor под визуал):
- Input «Запрос» (например `wooki`)
- SelectMenu «Бренд» (default `Wookiee`)
- SelectMenu «Модель» (опционально) — `useModeli`
- Submit → `useCreateBrandQuery()`

### 3.8. PromoCodesTable

**Колонки (7, JSX:727-728):** Код / Канал / Скидка / Статус / Продажи шт / Продажи ₽ / Ср. чек ₽.

**Над таблицей (JSX:720-724):** text search + DateRange + GroupBySelector. **Pills фильтров НЕТ** (как в эталоне).

**KPI карточки (JSX:708-713):** Активных / Продажи шт / Продажи ₽ / Ср. чек ₽ — за выбранный период.

**Статус-бейдж в строке (JSX:731):** вычисляемый
```ts
const st = p.status === 'unidentified' ? { label: 'Не идентиф.', color: 'amber' }
         : p.qty === 0                 ? { label: 'Нет данных', color: 'gray' }
                                       : { label: 'Активен', color: 'green' }
```
Не editable в строке. Editable только через PromoDetailPanel (см. 3.9).

**Sticky tfoot** (JSX:742-749): сумма по видимым.

### 3.9. PromoDetailPanel

Split-pane (`w-[400px]`, JSX:660-693).

**Шапка:** code font-mono + computed status badge + channel badge + (Edit3 pencil) + close (JSX:667-671).

**Edit-mode toggle:** Edit3 button переключает `isEdit`. В режиме edit все поля становятся `<Input>` (JSX:674-676):
- `code` (font-mono uppercase, editable as label)
- `channel` (SelectMenu allowAdd)
- `discount_pct` (number)
- `valid_from` / `valid_until` (date)

**`external_uuid` — read-only**, отображается мелким шрифтом отдельно (защита id-стабильности для ETL-сцепки).

**Buttons (JSX:677):** Сохранить (primary) / Отмена. Save → `useUpdatePromoCode()` (новый hook).

**KPI блок:** Продажи шт / Продажи ₽ / Ср. чек ₽ (JSX:681-685).

**Товарная разбивка** (JSX:687) — таблица SKU + модель + qty + amount. Источник: `marketing.promo_product_breakdown` (JOIN на promo_code_id). Подключаем `useQuery`. Empty state: «Данные собираются».

**По неделям** (JSX:688) — Нед / Зак / Продажи / Возвр. Источник: `marketing.promo_stats_weekly`.

### 3.10. AddPromoPanel

Текущая форма (Phase 2) — лёгкий refactor под визуал. Поля:
- Input «Код»
- SelectMenu «Канал» (allowAdd, options из `useChannels()`)
- Input «Скидка %» (number)
- Input «Начало» / «Окончание» (date)
- Submit → `useCreatePromoCode()`

### 3.11. UpdateBar

JSX:315-332 — обновляется компонент:
- CheckCircle icon emerald-500
- Timestamp (DD MMM YYYY, HH:MM МСК) из последней записи `marketing.sync_log` для job
- Статус «✓ N нед (DD.MM–DD.MM), пропусков нет» / «✗ Ошибка: ...»
- Кнопка «Обновить» с `RefreshCw` icon, `animate-spin` когда `isSyncing`
- Прогресс-текст «Обновление: 234 / 1396 строк» во время sync

### 3.12. GroupBySelector

Новый компонент `components/marketing/GroupBySelector.tsx`. SelectMenu (не нативный select) для визуальной consistency с v4.

Props: `{ value, onChange, options, scope }`. Внутри использует `useGroupByPref(scope)` (новый хук с persistence через ui_preferences).

### 3.13. Responsive

Breakpoint `lg:` (1024px):
- `lg:`: split-pane панель
- `< lg`: drawer fallback (используем существующий `@/components/crm/ui/Drawer` только в этом случае — оправданное исключение из правила 3.2)

## 4. Backend Design (детально)

### 4.1. Миграции БД

**B.0.1** `database/marketing/views/2026-05-13-search-queries-unified-v2.sql`:
```sql
CREATE OR REPLACE VIEW marketing.search_queries_unified AS
WITH all_q AS (
  SELECT 'B'::text || bq.id::text AS unified_id,
         'brand'::text AS entity_type,
         'brand'::text AS group_kind,
         bq.query AS query_text,
         NULL::text AS sku_label,
         NULL::bigint AS nm_id,
         NULL::text AS ww_code,
         NULL::text AS campaign_name,
         NULL::text AS creator_ref,
         (SELECT m.kod FROM public.modeli_osnova m WHERE m.id = bq.model_osnova_id) AS model_hint,
         (SELECT ch.label FROM marketing.channels ch WHERE ch.slug = 'brand') AS channel,
         bq.status,
         bq.created_at,
         bq.updated_at
  FROM crm.branded_queries bq
  UNION ALL
  SELECT 'S'::text || sa.id::text,
         CASE
           WHEN sa.code LIKE 'WW%' THEN 'ww_code'
           WHEN sa.code ~ '^[0-9]+$' THEN 'nomenclature'
           ELSE 'other'
         END,
         CASE
           WHEN sa.purpose = 'creators' AND sa.campaign_name ~* '^креатор[_ ]' THEN 'cr_personal'
           WHEN sa.purpose = 'creators' THEN 'cr_general'
           ELSE 'external'
         END,
         sa.code,
         sa.sku_label,
         NULL::bigint, -- nm_id is in sku_label or substitute_article_id JOIN
         CASE WHEN sa.code LIKE 'WW%' THEN sa.code ELSE NULL END,
         sa.campaign_name,
         sa.creator_ref,
         (SELECT m.kod FROM public.modeli_osnova m WHERE m.id =
           (SELECT a.model_osnova_id FROM public.artikuly a WHERE a.id = sa.artikul_id)) AS model_hint,
         (SELECT ch.label FROM marketing.channels ch WHERE ch.slug = sa.purpose) AS channel,
         sa.status,
         sa.created_at,
         sa.updated_at
  FROM crm.substitute_articles sa
)
SELECT * FROM all_q;
```

Новые поля по сравнению с текущим view: `entity_type`, `model_hint`, `channel` (label-resolved).

**B.0.2** `database/marketing/rpcs/2026-05-13-search-query-stats-aggregated-v2.sql`:
```sql
CREATE OR REPLACE FUNCTION marketing.search_query_stats_aggregated(p_from DATE, p_to DATE)
RETURNS TABLE (unified_id TEXT, frequency BIGINT, transitions BIGINT, additions BIGINT, orders BIGINT)
LANGUAGE sql STABLE
AS $$
  SELECT u.unified_id,
         COALESCE(SUM(w.frequency), 0)::bigint,
         COALESCE(SUM(w.open_card), 0)::bigint,
         COALESCE(SUM(w.add_to_cart), 0)::bigint,
         COALESCE(SUM(w.orders), 0)::bigint
  FROM marketing.search_queries_unified u
  LEFT JOIN marketing.search_queries_weekly w
    ON w.search_word = u.query_text
   AND w.week_start BETWEEN p_from AND p_to
  GROUP BY u.unified_id;
$$;
```

**B.0.3** Сидер-миграция для отсутствующего канала 'ooo' (`database/marketing/migrations/2026-05-13-add-ooo-channel.sql`):
```sql
INSERT INTO marketing.channels (slug, label) VALUES ('ooo', 'ООО') ON CONFLICT (slug) DO NOTHING;
```

### 4.2. Bridge-логика в sync-скриптах

**`services/sheets_sync/sync/sync_search_queries.py`** — новая функция перед `_sync_search_words`:

```python
def _ensure_db_words_in_sheets(ws_sheet, db_io) -> int:
    """Bridge: read crm.* tables, add missing words to Sheets col A in correct section."""
    db_words = db_io.fetch_all_search_words()  # SELECT code/query + purpose
    sheet_words = set(ws_sheet.col_values(1)[2:])  # skip header rows

    # Parse section dividers from col A
    sections = _parse_section_dividers(ws_sheet)  # {'external': row_29, 'cr_general': row_54, ...}

    inserts = []
    for word, purpose in db_words:
        if word not in sheet_words:
            target_row = sections.get(purpose, len(ws_sheet.col_values(1)) + 1)
            inserts.append((word, target_row))

    if inserts:
        # Batch insert via gspread.batch_update preserving order
        _batch_insert_rows(ws_sheet, inserts)

    return len(inserts)
```

**`services/sheets_sync/sync/sync_promocodes.py`** — аналогично для dictionary sheet.

### 4.3. Sync API в `analytics_api`

Новый файл `services/analytics_api/marketing.py`:

```python
from fastapi import APIRouter, BackgroundTasks
import subprocess, asyncio
from datetime import datetime

router = APIRouter(prefix="/api/marketing")

JOB_SCRIPTS = {
    "search-queries": "scripts/run_search_queries_sync.py",
    "promocodes": "scripts/run_wb_promocodes_sync.py",
}

@router.post("/sync/{job_name}")
async def trigger_sync(job_name: str, bg: BackgroundTasks):
    if job_name not in JOB_SCRIPTS:
        raise HTTPException(404)
    # log entry in marketing.sync_log
    sync_log_id = await create_sync_log_entry(job_name)
    bg.add_task(run_sync_subprocess, job_name, sync_log_id)
    return {"job_name": job_name, "status": "running", "sync_log_id": sync_log_id}

@router.get("/sync/{job_name}/status")
async def sync_status(job_name: str):
    return await fetch_latest_sync_log(job_name)
```

Регистрация в `services/analytics_api/app.py`: `app.include_router(marketing.router)`.

### 4.4. Что НЕ делаем в Phase 2B

- ~~Новые таблицы `crm.branded_query_metrics_weekly`~~ — данные уже в `marketing.search_queries_weekly` по `search_word`
- ~~Pull-back из Sheets~~ — уже работает в sync v2.0.0/v2.1.0 (двусторонняя запись)
- ~~Миграция enum статусов~~ — UI-маппинг
- ~~Колонка `sku_label` в `crm.substitute_articles`~~ — уже есть в `marketing.search_query_product_breakdown.sku_label`
- ~~Supabase Edge Function~~ — endpoint в analytics_api

## 5. Sequencing & Deliverables

### Branch / PRs
- Feature branch: `feature/marketing-v4-fidelity`
- PR #1: Phase 2A (фронт)
- PR #2: Phase 2B (бэк + sync bridge + endpoint)

### Phase 2A — Frontend Fidelity (волны)

**A.0 — Foundation (1 коммит, ~80 LOC)**
1. `feat(marketing): add MarketingLayout with sub-sidebar + data-section attribute`

**A.1 — Visual & Typography (4 коммита)**
1. `feat(marketing): inject stone palette via [data-section="marketing"] CSS-variable override`
2. `feat(marketing): add local Badge/Button/Input components for marketing (decoupled from CRM)`
3. `feat(marketing): load Instrument Serif font via Google Fonts`
4. `feat(marketing): apply v4 typography to page headers (Instrument Serif italic 24px)`

**A.2 — Status & Labels (2 коммита)**
1. `feat(marketing): bidirectional UI<->DB status mapping (free<->paused, archive<->archived)`
2. `feat(marketing): use marketing.channels.label in pills + table cells (not slug)`

**A.3 — Layout & Components Refactor (3 коммита)**
1. `refactor(marketing): replace Drawer with split-pane (responsive lg: fallback)`
2. `refactor(marketing): align SectionHeader with v4 (icon + count + chevron)`
3. `feat(marketing): align AddWWPanel cascade with v4 (Модель→Цвет→Размер→auto-SKU)`

**A.4 — Configurable Grouping (3 коммита)**
1. `refactor(catalog): extract getUiPref/setUiPref to lib/ui-preferences.ts`
2. `feat(marketing): GroupBySelector + 3 presets for search-queries (direction default)`
3. `feat(marketing): GroupBySelector for promo-codes (channel default)`

**A.5 — Edit Flows (4 коммита)**
1. `feat(marketing): useUpdatePromoCode mutation hook`
2. `feat(marketing): edit-mode in PromoDetailPanel (Edit3 toggle + Save/Cancel)`
3. `feat(marketing): connect product-breakdown to PromoDetailPanel`
4. `feat(marketing): wire StatusEditor mutation in SearchQueryDetailPanel`

**A.6 — Detail Funnel (2 коммита)**
1. `feat(marketing): full funnel rendering in SearchQueryDetailPanel (7 rows + final CR)`
2. `feat(marketing): weekly stats toggle (period vs all) with empty state for brands`

**A.7 — Tests (1 коммит)**
1. `test(marketing): update SectionHeader + SelectMenu tests after refactor`

Итого Phase 2A: **20 коммитов**.

### Phase 2B — Backend (волны)

**B.0 — SQL Migrations (3 коммита)**
1. `feat(marketing-db): update search_queries_unified view with entity_type + model_hint + channel`
2. `feat(marketing-db): rewrite search_query_stats_aggregated RPC to JOIN marketing.search_queries_weekly`
3. `feat(marketing-db): seed marketing.channels with 'ooo' label`

**B.1 — Sync Bridge (2 коммита)**
1. `feat(search-queries-sync): bridge crm tables → sheets col A before WB pull (section-aware insert)`
2. `feat(promocodes-sync): bridge crm.promo_codes → dictionary sheet`

**B.2 — Sync API (3 коммита)**
1. `feat(analytics-api): /api/marketing/sync/{job} POST + status endpoints with background subprocess`
2. `feat(marketing-hub): wire UpdateBar refresh button to sync endpoint with live progress`
3. `chore(marketing): runbook for fresh data bootstrap after view changes`

Итого Phase 2B: **8 коммитов**. **Общий итог: 28 коммитов, 2 PR, ~5-7 рабочих дней.**

### Граф зависимостей
```
A.0 ─ A.1 ─┬─ A.3 ─ A.4 ─ A.5 ─ A.6 ─ A.7 ─> PR #1 ─> main
           │
           A.2 ─┘

                                              B.0 ─ B.1 ─ B.2 ─> PR #2 ─> main
```

## 6. UAT чеклист

**Phase 2A done когда:**
- [ ] `/marketing/search-queries`: заголовок Instrument Serif italic, sub-sidebar слева, split-pane панель справа когда клик на запрос
- [ ] Группы 🔤 / 📦 / 👥 / 👤 в дефолтном пресете «По направлению»
- [ ] Dropdown «Группировка» переключает группы, выбор сохраняется при F5
- [ ] Pills модель / канал работают (фильтруют видимые строки)
- [ ] Каналы отображаются как label («Бренд», «Яндекс», «Adblogger», «Креаторы»), не slug
- [ ] Date range — дефолт 4 недели назад → сегодня
- [ ] Клик на WW-код → справа деталка с полной воронкой (6 метрик + 2 промежуточных CR + итоговый CRV)
- [ ] StatusEditor: клик → меню → выбор «Архив» → бэйдж меняется, сохраняется в БД (F5 показывает «Архив»)
- [ ] «+ Добавить WW-код» → каскадная форма → создаёт запись, появляется в таблице с нулями
- [ ] `/marketing/promo-codes`: KPI карточки наверху, таблица, item.code в font-mono
- [ ] Клик на промокод → справа деталка, кнопка-карандаш переводит в edit, поля становятся редактируемыми (кроме UUID), Сохранить → данные в БД обновляются
- [ ] Товарная разбивка показывает SKU + qty + сумму для промокодов с данными в `marketing.promo_product_breakdown`
- [ ] Статус-бейдж в таблице промокодов вычисляется правильно (unidentified→амбер, qty=0→серый, иначе→зелёный)
- [ ] UpdateBar показывает timestamp последнего sync + кнопку «Обновить» (в Phase 2A — мок-кнопка)
- [ ] На экране < 1024px split-pane заменяется drawer'ом
- [ ] CRM-секция (`/influence`) визуально не изменилась (никаких регрессий)

**Phase 2B done когда:**
- [ ] Группа «Брендированные запросы» в UI показывает не нули — `wooki`, `Wendy`, `Audrey` имеют частоту/переходы/корзины/заказы
- [ ] Добавляю в UI новый WW-код → жму «Обновить» в UpdateBar
- [ ] UpdateBar показывает live-progress «Обновление: N / M строк»
- [ ] Через ~5-10 минут sync завершается, бэйдж зелёный «✓ ... обновлено»
- [ ] В деталке нового WW-кода появляются метрики за последнюю неделю
- [ ] То же для нового промокода (если уже есть продажи на WB)
- [ ] `marketing.sync_log` пополняется записями при каждом нажатии «Обновить» (1 row на запуск)
- [ ] В Sheets col A появляются новые слова, добавленные через UI (в правильной секции по purpose)

## 7. Rollback план

**Phase 2A rollback:**
- `git revert -m 1 <pr-1-merge-sha>` — одна команда
- Бэк не затронут — данные в БД остаются, cron sync продолжает работать
- Visual возвращается к Phase 2 state

**Phase 2B rollback:**
- Frontend revert не трогает view/RPC (frontend читает supersets новых полей, обратная совместимость)
- View/RPC откат: каждая миграция имеет down-парную (`CREATE OR REPLACE` восстанавливает предыдущее определение)
- Bridge-логика в sync: при ошибке падает в legacy-режим (читает только Sheets), не блокер. Новые UI-записи без метрик — но и не было их до Phase 2B
- Endpoint в analytics_api: если падает — frontend показывает ошибку «Sync временно недоступен», cron остаётся работать

## 8. Открытые риски

1. **Bridge порядок при первом деплое.** После деплоя Phase 2A юзеры могут добавлять записи через UI до того как B.1 будет в проде. Эти записи получат метрики только после деплоя B.1 + первого запуска sync. Окно ~1-2 дня. **Mitigation:** деплоить Phase 2A и 2B в пределах одной недели.

2. **`ui_preferences` без user_id.** Текущая таблица (`scope`, `key`, `value`) **глобальная**. Все пользователи Hub делят одно значение группировки. Для одного-пользователя-Wookiee сейчас ОК. **Mitigation:** при добавлении команды — расширить схему с `user_id`. Не блокер.

3. **WB API длительность 5-10 минут.** Sync subprocess может длиться долго. UpdateBar показывает прогресс. Если процесс падает — `marketing.sync_log.status = failed`, UpdateBar показывает ошибку. **Mitigation:** уже встроен retry в существующем sync (commit `d14a1f7`).

4. **Channel label inconsistency.** Промо канал «другое» в v4 vs «Прочее» в БД. Принимаем БД source-of-truth. Косметика.

5. **Manual edits в Sheets могут конфликтовать с bridge.** Если пользователь сам редактирует Sheets между запусками sync, bridge может перезаписать. **Mitigation:** bridge **только добавляет** недостающие строки, не редактирует существующие. INSERT-only логика.

6. **Тесты Phase 2 могут сломаться при refactor.** `SectionHeader.test.tsx` и `SelectMenu.test.tsx` обновляются в A.7. Если ломаются другие тесты в `__tests__/` — фиксим в той же волне.

## 9. Из чего НЕ состоит этот дизайн

- Никаких изменений в Catalog / Operations / Community / Influence / Analytics
- Никаких новых таблиц БД в маркетинге (используем существующие)
- Никаких изменений в WB API integration (sync v2.0.0/v2.1.0 нетронут кроме bridge prelude)
- Никаких e2e Playwright-тестов — отдельный QA-этап после Phase 2A+B
- Никакого нового real-time подписочного слоя — refresh через React Query invalidate

## Ссылки

- Эталон: `docs/superpowers/specs/wookiee_marketing_v4.jsx`
- Phase 1 verification: `docs/superpowers/plans/2026-05-09-marketing-hub-impl-v2-phase1-verification.md`
- Phase 2 verification: `docs/superpowers/plans/2026-05-09-marketing-hub-impl-v2-phase2-verification.md`
- Sync v2.0.0 commits: `39e4146` + `05e007a` + `d14a1f7`
- Promocodes sync v2.1.0 commits: `f301f41` + `fe47c74` + `33585e5`
- Catalog grouping pattern: `wookiee-hub/src/pages/catalog/matrix.tsx:54-172`
- ui_preferences helpers: `wookiee-hub/src/lib/catalog/service.ts:1750-1771`
