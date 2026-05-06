# Influencer CRM v2 — Design Spec

**Date:** 2026-05-06  
**Status:** Approved

---

## 1. Goal

Превратить Influence CRM из канбан-доски в аналитический инструмент для маркетолога,
закупающего внешний трафик на WB/OZON: богатые таблицы по блогерам и интеграциям,
ключевые метрики (CPM, ROMI, Δплан/факт) прямо в списке, фильтры по платформе/стадии/периоду,
и исправить критические баги (ETL сбрасывает стадии, календарь не показывает интеграции).

---

## 2. Что НЕ меняется

- Схема БД: миграций нет — все нужные данные уже есть в `crm.*`
- BFF API-контракт: существующие эндпоинты не ломаются
- Auth: X-API-Key без изменений
- Канбан-доска: остаётся, дополняется переключателем

---

## 3. Архитектура изменений

### Backend (Plan A)

| Файл | Изменение |
|------|-----------|
| `services/sheets_etl/loader.py` | add `no_update_cols` param to `upsert()` |
| `services/sheets_etl/run.py` | pass `no_update_cols=["stage"]` for integrations upsert |
| `shared/data_layer/influencer_crm/integrations.py` | add `primary_substitute_code` subquery + `q` filter |
| `services/influencer_crm/routers/integrations.py` | add `q: str | None` param |
| `services/influencer_crm/schemas/integration.py` | add `primary_substitute_code: str | None` field |
| `shared/data_layer/influencer_crm/bloggers.py` | add `channel` filter + new `list_bloggers_summary()` |
| `services/influencer_crm/routers/bloggers.py` | add `channel` param + `GET /bloggers/summary` route |
| `services/influencer_crm/schemas/blogger.py` | add `BloggerSummaryOut` schema |

### Frontend (Plan B)

| Файл | Изменение |
|------|-----------|
| `src/api/crm/integrations.ts` | add `primary_substitute_code`, `q` param |
| `src/api/crm/bloggers.ts` | add `BloggerSummaryOut`, `listBloggersSummary()` |
| `src/pages/influence/integrations/IntegrationFilters.tsx` | NEW — shared filter bar |
| `src/pages/influence/integrations/IntegrationsTableView.tsx` | NEW — virtual table |
| `src/pages/influence/integrations/IntegrationsKanbanPage.tsx` | add toggle + filters + default dates |
| `src/pages/influence/integrations/KanbanCard.tsx` | richer card: handle, channel, cost, views |
| `src/pages/influence/bloggers/BloggersTableView.tsx` | NEW — blogger analytics table |
| `src/pages/influence/bloggers/BloggersPage.tsx` | add toggle + platform filter + richer cards |
| `src/pages/influence/integrations/IntegrationEditDrawer.tsx` | D1: ad_format filtered by channel |
| `src/pages/influence/calendar/CalendarPage.tsx` | E2: fix to show all integrations |
| `src/components/layout/top-bar.tsx` | F3: verify/fix breadcrumbs for /influence/* |

---

## 4. Ключевые решения (из multi-agent review)

### Метрики в таблице интеграций
- **CPM** = `fact_cpm` из API (не пересчитывать на фронте)
- **CPC** = `fact_cpc` из API
- **ROMI** = `fact_revenue / total_cost` — лейбл «ROMI по выручке (без себ-ти)»
- **Δплан/факт** = `(fact_cpm - plan_cpm) / plan_cpm * 100%` — цветной бейдж (зелёный/красный)
- Все null → отображать `—`, никогда `0` или `∞`

### avg_cpm_fact по блогеру — взвешенное
```sql
CASE WHEN SUM(i.fact_views) > 0
  THEN ROUND(SUM(i.total_cost::numeric) / NULLIF(SUM(i.fact_views), 0) * 1000, 2)
  ELSE NULL
END AS avg_cpm_fact
```
Вместо `AVG(fact_cpm)` — корректная формула.

### View state
- URL params: `?view=table` / `?view=cards` — sharable, back/forward работают
- Default: `cards` для блогеров, `kanban` для интеграций

### Виртуализация
- `@tanstack/react-virtual` для таблиц с 689+ строками

### Default date range (интеграции)
- Первый день прошлого месяца → последний день текущего месяца
- Отображается как label "Прошлый + текущий месяц", легко сбрасывается

### D1 — форматы по каналу
```ts
const CHANNEL_FORMATS: Record<Channel, AdFormat[]> = {
  instagram: ['story', 'short_video', 'long_video', 'image_post', 'integration', 'live_stream'],
  telegram:  ['long_post', 'image_post', 'integration'],
  tiktok:    ['short_video', 'live_stream'],
  youtube:   ['long_video', 'short_video', 'integration', 'live_stream'],
  vk:        ['long_post', 'image_post', 'short_video', 'live_stream'],
  rutube:    ['long_video', 'short_video'],
};
```

### E1 — ETL не перезаписывает стадии
`upsert()` в loader.py получает `no_update_cols: list[str] = []`. При upsert интеграций
`no_update_cols=["stage"]` — стадия устанавливается только при INSERT, не UPDATE.

### BFF: /bloggers/summary vs /bloggers
Отдельный эндпоинт — не ломает существующий, у которого другой use-case (autocomplete в формах).
Маршрут `/bloggers/summary` регистрируется **до** `/bloggers/{id}` чтобы FastAPI не пытался
распарсить "summary" как integer id.

---

## 5. Вне скоупа (Phase 3)

- Страница "По товарам" (аналитика по моделям/артикулам)
- Окно атрибуции WB (лаг 3-14 дней)
- История CPM блогера (мини-график)
- Парсинг аватаров из соцсетей
- WB vs OZON разбивка заказов
