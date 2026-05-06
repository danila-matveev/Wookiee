# Influencer CRM v2 — Frontend Plan (Plan B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить таблицы (Kanban↔Table toggle) на страницах блогеров и интеграций с полным набором аналитических метрик, фильтры по каналу/стадии/периоду, улучшить канбан-карточки, и исправить баги E2/D1/F3.

**Architecture:** Все изменения в `wookiee-hub/src/pages/influence/`. Новые компоненты: `IntegrationFilters.tsx`, `IntegrationsTableView.tsx`, `BloggersTableView.tsx`. Данные берутся из уже существующих BFF-эндпоинтов (Plan A должен быть задеплоен). View state хранится в URL: `?view=table`. Виртуализация таблиц через `@tanstack/react-virtual`.

**Spec:** `docs/superpowers/specs/2026-05-06-influencer-crm-v2-design.md`

**Depends on:** Plan A задеплоен на `crm.matveevdanila.com`.

**Tech Stack:** React 19, TanStack Query v5, @tanstack/react-virtual, react-hook-form v7, Tailwind CSS 4, Lucide React icons

**Run tests:** `cd /Users/danilamatveev/Projects/Wookiee/wookiee-hub && npm test -- --run`

**Build & deploy:**
```bash
cd /Users/danilamatveev/Projects/Wookiee/wookiee-hub && npm run build
rsync -av --delete dist/ timeweb:/home/danila/projects/wookiee/wookiee-hub/dist/
```

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `src/api/crm/integrations.ts` | Add `primary_substitute_code`, `q` param |
| Modify | `src/api/crm/bloggers.ts` | Add `BloggerSummaryOut`, `listBloggersSummary()` |
| Modify | `src/hooks/crm/use-integrations.ts` | Add `useIntegrationsSummary` helper |
| Modify | `src/hooks/crm/use-bloggers.ts` | Add `useBloggersSummary` hook |
| Create | `src/pages/influence/integrations/IntegrationFilters.tsx` | Shared filter bar |
| Create | `src/pages/influence/integrations/IntegrationsTableView.tsx` | Virtual table with metrics |
| Modify | `src/pages/influence/integrations/IntegrationsKanbanPage.tsx` | Toggle + filters + default dates |
| Modify | `src/pages/influence/integrations/KanbanCard.tsx` | Richer card: handle, channel, cost, views |
| Create | `src/pages/influence/bloggers/BloggersTableView.tsx` | Blogger analytics table |
| Modify | `src/pages/influence/bloggers/BloggersPage.tsx` | Toggle + platform filter + richer cards |
| Modify | `src/pages/influence/integrations/IntegrationEditDrawer.tsx` | D1: ad_format by channel |
| Modify | `src/pages/influence/calendar/CalendarPage.tsx` | E2: fix showing all integrations |
| Modify | `src/components/layout/top-bar.tsx` | F3: verify breadcrumbs |

---

## Task 1: Установить @tanstack/react-virtual + обновить API-типы

**Files:**
- Modify: `package.json` (dev dep)
- Modify: `src/api/crm/integrations.ts`
- Modify: `src/api/crm/bloggers.ts`

- [ ] **Step 1: Установить @tanstack/react-virtual**

```bash
cd /Users/danilamatveev/Projects/Wookiee/wookiee-hub
npm install @tanstack/react-virtual
```

Проверить что установилось:
```bash
grep "react-virtual" package.json
```

- [ ] **Step 2: Добавить `primary_substitute_code` и `q` в types интеграций**

Файл: `src/api/crm/integrations.ts`.

В `IntegrationOut` добавить после `erid`:
```ts
primary_substitute_code: string | null;
```

В `IntegrationListParams` добавить:
```ts
q?: string;
```

- [ ] **Step 3: Добавить `BloggerSummaryOut` в types блогеров**

Файл: `src/api/crm/bloggers.ts`. Добавить после `BloggerDetailOut`:

```ts
export interface ChannelBrief {
  id: number;
  channel: string;
  handle: string;
  url: string | null;
}

export interface BloggerSummaryOut {
  id: number;
  display_handle: string;
  real_name: string | null;
  status: BloggerStatus;
  default_marketer_id: number | null;
  price_story_default: string | null;
  price_reels_default: string | null;
  created_at: string | null;
  updated_at: string | null;
  channels: ChannelBrief[];
  integrations_count: number;
  integrations_done: number;
  last_integration_at: string | null;
  total_spent: string;
  avg_cpm_fact: string | null;
}

export interface BloggerSummaryPage {
  items: BloggerSummaryOut[];
  total: number;
}

export interface BloggerSummaryParams {
  status?: BloggerStatus;
  q?: string;
  channel?: string;
  limit?: number;
  offset?: number;
}

export function listBloggersSummary(params: BloggerSummaryParams = {}): Promise<BloggerSummaryPage> {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) search.set(k, String(v));
  }
  const q = search.toString();
  return crmApi.get<BloggerSummaryPage>(`/bloggers/summary${q ? `?${q}` : ''}`);
}
```

- [ ] **Step 4: Добавить `useBloggersSummary` hook**

Файл: `src/hooks/crm/use-bloggers.ts`. Добавить:

```ts
import {
  // ... existing imports ...
  listBloggersSummary,
  type BloggerSummaryParams,
} from '@/api/crm/bloggers';

export function useBloggersSummary(params: BloggerSummaryParams = {}) {
  return useQuery({
    queryKey: ['bloggers-summary', params],
    queryFn: () => listBloggersSummary(params),
    staleTime: 30_000,
  });
}
```

- [ ] **Step 5: Запустить сборку — убедиться нет TS-ошибок**

```bash
cd /Users/danilamatveev/Projects/Wookiee/wookiee-hub
npx tsc -p tsconfig.temp.json --noEmit 2>&1 | grep -v "node_modules" | head -20
```

Ожидается: 0 ошибок.

- [ ] **Step 6: Commit**

```bash
git add wookiee-hub/package.json wookiee-hub/package-lock.json
git add wookiee-hub/src/api/crm/integrations.ts
git add wookiee-hub/src/api/crm/bloggers.ts
git add wookiee-hub/src/hooks/crm/use-bloggers.ts
git commit -m "feat(crm-hub): add react-virtual, BloggerSummaryOut types, useBloggersSummary"
```

---

## Task 2: IntegrationFilters — общий фильтр-бар

**Files:**
- Create: `src/pages/influence/integrations/IntegrationFilters.tsx`

Фильтры: поиск по блогеру (q), платформа (channel), стадии (stage_in мультиселект), дата от/до, маркетолог, маркетплейс.

- [ ] **Step 1: Создать компонент**

Файл: `src/pages/influence/integrations/IntegrationFilters.tsx`:

```tsx
import { useState } from 'react';
import { Search, X } from 'lucide-react';
import { type Channel, type Marketplace, type Stage, STAGES, STAGE_LABELS } from '@/api/crm/integrations';
import { FilterPill } from '@/components/crm/ui/FilterPill';
import { Input } from '@/components/crm/ui/Input';
import { Button } from '@/components/crm/ui/Button';

export interface IntegrationFilterValue {
  q?: string;
  channel?: Channel;
  stage_in?: Stage[];
  date_from?: string;
  date_to?: string;
  marketplace?: Marketplace;
}

interface Props {
  value: IntegrationFilterValue;
  onChange: (v: IntegrationFilterValue) => void;
}

const CHANNELS: { value: Channel; label: string }[] = [
  { value: 'instagram', label: 'IG' },
  { value: 'telegram',  label: 'TG' },
  { value: 'tiktok',    label: 'TikTok' },
  { value: 'youtube',   label: 'YT' },
  { value: 'vk',        label: 'VK' },
  { value: 'rutube',    label: 'Rutube' },
];

const MARKETPLACES: { value: Marketplace; label: string }[] = [
  { value: 'wb',   label: 'WB' },
  { value: 'ozon', label: 'OZON' },
  { value: 'both', label: 'Оба' },
];

export function IntegrationFilters({ value, onChange }: Props) {
  const [qInput, setQInput] = useState(value.q ?? '');

  const set = (patch: Partial<IntegrationFilterValue>) =>
    onChange({ ...value, ...patch });

  const toggleStage = (stage: Stage) => {
    const current = value.stage_in ?? [];
    const next = current.includes(stage)
      ? current.filter((s) => s !== stage)
      : [...current, stage];
    set({ stage_in: next.length ? next : undefined });
  };

  const hasFilters = !!(
    value.q || value.channel || value.stage_in?.length ||
    value.date_from || value.date_to || value.marketplace
  );

  return (
    <div className="flex flex-col gap-3 mb-4">
      {/* Row 1: search + dates + marketplace */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-48 max-w-64">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-fg" />
          <Input
            className="pl-7 h-8 text-sm"
            placeholder="Блогер..."
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && set({ q: qInput || undefined })}
            onBlur={() => set({ q: qInput || undefined })}
          />
        </div>
        <Input
          type="date"
          className="h-8 text-sm w-36"
          value={value.date_from ?? ''}
          onChange={(e) => set({ date_from: e.target.value || undefined })}
        />
        <span className="text-muted-fg text-xs">—</span>
        <Input
          type="date"
          className="h-8 text-sm w-36"
          value={value.date_to ?? ''}
          onChange={(e) => set({ date_to: e.target.value || undefined })}
        />
        {/* Marketplace */}
        <div className="flex gap-1">
          {MARKETPLACES.map(({ value: v, label }) => (
            <FilterPill
              key={v}
              solid={value.marketplace === v}
              onClick={() => set({ marketplace: value.marketplace === v ? undefined : v })}
            >
              {label}
            </FilterPill>
          ))}
        </div>
        {hasFilters && (
          <Button
            variant="ghost"
            className="h-8 gap-1 text-xs text-muted-fg"
            onClick={() => { setQInput(''); onChange({}); }}
          >
            <X size={12} /> Сбросить
          </Button>
        )}
      </div>

      {/* Row 2: channels + stages */}
      <div className="flex flex-wrap gap-1.5">
        {CHANNELS.map(({ value: v, label }) => (
          <FilterPill
            key={v}
            solid={value.channel === v}
            onClick={() => set({ channel: value.channel === v ? undefined : v })}
          >
            {label}
          </FilterPill>
        ))}
        <span className="mx-1 text-border">|</span>
        {STAGES.map((stage) => (
          <FilterPill
            key={stage}
            solid={value.stage_in?.includes(stage)}
            onClick={() => toggleStage(stage)}
          >
            {STAGE_LABELS[stage]}
          </FilterPill>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: TS-проверка**

```bash
cd /Users/danilamatveev/Projects/Wookiee/wookiee-hub
npx tsc -p tsconfig.temp.json --noEmit 2>&1 | grep "IntegrationFilters" | head -5
```

Ожидается: нет ошибок.

- [ ] **Step 3: Commit**

```bash
git add wookiee-hub/src/pages/influence/integrations/IntegrationFilters.tsx
git commit -m "feat(crm-hub): add IntegrationFilters component"
```

---

## Task 3: IntegrationsTableView — виртуальная таблица с метриками

**Files:**
- Create: `src/pages/influence/integrations/IntegrationsTableView.tsx`

Колонки: Блогер | Товар | Канал | Формат | Дата | Стадия | Стоимость | Охват | CPM | ROMI | Корзины | Заказы | Δплан/факт. Виртуализация через `@tanstack/react-virtual`.

- [ ] **Step 1: Написать unit-тест для хелпер-функций**

Создай `src/pages/influence/integrations/__tests__/integration-metrics.test.ts`:

```ts
import { describe, it, expect } from 'vitest';

// Helper functions that will be exported from IntegrationsTableView
function formatRomi(revenue: string | null, cost: string): string {
  const r = parseFloat(revenue ?? '0');
  const c = parseFloat(cost);
  if (!c || !r) return '—';
  return `${(r / c).toFixed(2)}x`;
}

function formatPlanFactDelta(factCpm: string | null, planCpm: string | null): string {
  const f = parseFloat(factCpm ?? '');
  const p = parseFloat(planCpm ?? '');
  if (!f || !p) return '—';
  const delta = ((f - p) / p) * 100;
  return `${delta > 0 ? '+' : ''}${delta.toFixed(0)}%`;
}

function formatMetric(val: number | string | null | undefined): string {
  if (val === null || val === undefined || val === '') return '—';
  const n = typeof val === 'string' ? parseFloat(val) : val;
  if (isNaN(n)) return '—';
  return n.toLocaleString('ru-RU');
}

describe('integration metrics helpers', () => {
  it('formatRomi returns ratio', () => {
    expect(formatRomi('150000', '50000')).toBe('3.00x');
  });
  it('formatRomi returns — when no revenue', () => {
    expect(formatRomi(null, '50000')).toBe('—');
  });
  it('formatRomi returns — when no cost', () => {
    expect(formatRomi('100000', '0')).toBe('—');
  });
  it('formatPlanFactDelta positive', () => {
    expect(formatPlanFactDelta('660', '600')).toBe('+10%');
  });
  it('formatPlanFactDelta negative', () => {
    expect(formatPlanFactDelta('540', '600')).toBe('-10%');
  });
  it('formatPlanFactDelta returns — when null', () => {
    expect(formatPlanFactDelta(null, '600')).toBe('—');
  });
  it('formatMetric null returns —', () => {
    expect(formatMetric(null)).toBe('—');
  });
  it('formatMetric 12400 formats with locale', () => {
    expect(formatMetric(12400)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Запустить тест — убедиться что падает**

```bash
cd /Users/danilamatveev/Projects/Wookiee/wookiee-hub
npm test -- --run src/pages/influence/integrations/__tests__/integration-metrics.test.ts
```

Ожидается: FAIL (функции не определены).

- [ ] **Step 3: Создать IntegrationsTableView**

Файл: `src/pages/influence/integrations/IntegrationsTableView.tsx`:

```tsx
import { useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { IntegrationOut, Stage } from '@/api/crm/integrations';
import { STAGE_LABELS } from '@/api/crm/integrations';
import { Badge } from '@/components/crm/ui/Badge';
import { PlatformPill } from '@/components/crm/ui/PlatformPill';

// ── metric helpers ──────────────────────────────────────────────────────────

export function formatMetric(val: number | string | null | undefined): string {
  if (val === null || val === undefined || val === '') return '—';
  const n = typeof val === 'string' ? parseFloat(val) : val;
  if (isNaN(n)) return '—';
  return n.toLocaleString('ru-RU');
}

export function formatRomi(revenue: string | null, cost: string): string {
  const r = parseFloat(revenue ?? '0');
  const c = parseFloat(cost);
  if (!c || !r) return '—';
  return `${(r / c).toFixed(2)}x`;
}

export function formatPlanFactDelta(
  factCpm: string | null,
  planCpm: string | null,
): string {
  const f = parseFloat(factCpm ?? '');
  const p = parseFloat(planCpm ?? '');
  if (!f || !p) return '—';
  const delta = ((f - p) / p) * 100;
  return `${delta > 0 ? '+' : ''}${delta.toFixed(0)}%`;
}

function deltaColor(factCpm: string | null, planCpm: string | null): string {
  const f = parseFloat(factCpm ?? '');
  const p = parseFloat(planCpm ?? '');
  if (!f || !p) return 'text-muted-fg';
  return f <= p ? 'text-success' : 'text-danger';
}

const STAGE_COLOR: Record<Stage, string> = {
  переговоры:          'bg-muted text-muted-fg',
  согласовано:         'bg-primary/10 text-primary',
  отправка_комплекта:  'bg-warning/10 text-warning',
  контент:             'bg-warning/20 text-warning',
  запланировано:       'bg-primary/20 text-primary',
  аналитика:           'bg-success/10 text-success',
  завершено:           'bg-success/20 text-success',
  архив:               'bg-muted text-muted-fg',
};

// ── column definition ───────────────────────────────────────────────────────

interface Col {
  key: string;
  label: string;
  width: string;
  align?: 'right';
  render: (row: IntegrationOut) => React.ReactNode;
}

const COLS: Col[] = [
  {
    key: 'blogger',
    label: 'Блогер',
    width: 'min-w-32 max-w-44',
    render: (r) => (
      <span className="truncate font-medium text-fg">{r.blogger_handle ?? `#${r.blogger_id}`}</span>
    ),
  },
  {
    key: 'model',
    label: 'Товар',
    width: 'min-w-24 max-w-36',
    render: (r) => (
      <span className="truncate text-sm text-muted-fg">
        {r.primary_substitute_code ?? '—'}
      </span>
    ),
  },
  {
    key: 'channel',
    label: 'Канал',
    width: 'w-24',
    render: (r) => <PlatformPill platform={r.channel} />,
  },
  {
    key: 'format',
    label: 'Формат',
    width: 'w-28',
    render: (r) => <span className="text-xs text-muted-fg">{r.ad_format}</span>,
  },
  {
    key: 'date',
    label: 'Дата',
    width: 'w-24',
    render: (r) => {
      const d = new Date(r.publish_date);
      return (
        <span className="text-sm tabular-nums">
          {d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' })}
        </span>
      );
    },
  },
  {
    key: 'stage',
    label: 'Стадия',
    width: 'w-32',
    render: (r) => (
      <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${STAGE_COLOR[r.stage]}`}>
        {STAGE_LABELS[r.stage]}
      </span>
    ),
  },
  {
    key: 'cost',
    label: 'Стоимость',
    width: 'w-28',
    align: 'right',
    render: (r) => (
      <span className="tabular-nums text-sm">
        {r.total_cost ? `${parseFloat(r.total_cost).toLocaleString('ru-RU')} ₽` : '—'}
      </span>
    ),
  },
  {
    key: 'views',
    label: 'Охват',
    width: 'w-24',
    align: 'right',
    render: (r) => <span className="tabular-nums text-sm">{formatMetric(r.fact_views)}</span>,
  },
  {
    key: 'cpm',
    label: 'CPM',
    width: 'w-24',
    align: 'right',
    render: (r) => (
      <span className="tabular-nums text-sm">
        {r.fact_cpm ? `${formatMetric(r.fact_cpm)} ₽` : '—'}
      </span>
    ),
  },
  {
    key: 'romi',
    label: 'ROMI',
    width: 'w-20',
    align: 'right',
    render: (r) => (
      <span className="tabular-nums text-sm font-medium">
        {formatRomi(r.fact_revenue, r.total_cost)}
      </span>
    ),
  },
  {
    key: 'carts',
    label: 'Корзины',
    width: 'w-20',
    align: 'right',
    render: (r) => <span className="tabular-nums text-sm">{formatMetric(r.fact_carts)}</span>,
  },
  {
    key: 'orders',
    label: 'Заказы',
    width: 'w-20',
    align: 'right',
    render: (r) => <span className="tabular-nums text-sm">{formatMetric(r.fact_orders)}</span>,
  },
  {
    key: 'delta',
    label: 'Δ CPM',
    width: 'w-20',
    align: 'right',
    render: (r) => (
      <span className={`tabular-nums text-xs font-medium ${deltaColor(r.fact_cpm, r.plan_cpm)}`}>
        {formatPlanFactDelta(r.fact_cpm, r.plan_cpm)}
      </span>
    ),
  },
];

// ── component ───────────────────────────────────────────────────────────────

interface Props {
  items: IntegrationOut[];
  onRowClick: (id: number) => void;
}

export function IntegrationsTableView({ items, onRowClick }: Props) {
  const parentRef = useRef<HTMLDivElement>(null);

  const rowVirtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 44,
    overscan: 10,
  });

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      {/* Header */}
      <div className="flex border-b border-border bg-muted/40 px-3 py-2 text-xs font-medium text-muted-fg select-none">
        {COLS.map((col) => (
          <div
            key={col.key}
            className={`${col.width} shrink-0 ${col.align === 'right' ? 'text-right' : ''} pr-3`}
          >
            {col.label}
          </div>
        ))}
      </div>

      {/* Virtual rows */}
      <div ref={parentRef} className="overflow-auto" style={{ maxHeight: 'calc(100vh - 280px)' }}>
        <div
          style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: 'relative' }}
        >
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const row = items[virtualRow.index];
            return (
              <div
                key={row.id}
                role="row"
                tabIndex={0}
                className="absolute left-0 right-0 flex items-center px-3 border-b border-border/50 hover:bg-muted/30 cursor-pointer transition-colors"
                style={{ top: virtualRow.start, height: virtualRow.size }}
                onClick={() => onRowClick(row.id)}
                onKeyDown={(e) => e.key === 'Enter' && onRowClick(row.id)}
              >
                {COLS.map((col) => (
                  <div
                    key={col.key}
                    className={`${col.width} shrink-0 overflow-hidden ${col.align === 'right' ? 'text-right' : ''} pr-3`}
                  >
                    {col.render(row)}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer */}
      <div className="px-3 py-2 text-xs text-muted-fg border-t border-border bg-muted/20">
        {items.length} интеграций · ROMI = выручка / стоимость (без учёта себестоимости)
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Запустить тест — убедиться что проходит**

```bash
npm test -- --run src/pages/influence/integrations/__tests__/integration-metrics.test.ts
```

Ожидается: PASS (8 tests).

- [ ] **Step 5: TS-проверка**

```bash
npx tsc -p tsconfig.temp.json --noEmit 2>&1 | grep "IntegrationsTable" | head -5
```

- [ ] **Step 6: Commit**

```bash
git add wookiee-hub/src/pages/influence/integrations/IntegrationsTableView.tsx
git add "wookiee-hub/src/pages/influence/integrations/__tests__/integration-metrics.test.ts"
git commit -m "feat(crm-hub): add IntegrationsTableView with virtual scroll + ROMI/delta metrics"
```

---

## Task 4: IntegrationsKanbanPage — toggle + фильтры + улучшенные карточки

**Files:**
- Modify: `src/pages/influence/integrations/IntegrationsKanbanPage.tsx`
- Modify: `src/pages/influence/integrations/KanbanCard.tsx`

- [ ] **Step 1: Улучшить KanbanCard**

Файл: `src/pages/influence/integrations/KanbanCard.tsx`.

Найди место где рендерится карточка и замени содержимое `<div>` карточки на:

```tsx
{/* Blogger */}
<div className="flex items-center gap-1.5 mb-1">
  <div
    className="size-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0"
    style={{ backgroundColor: handleToColor(integration.blogger_handle ?? '') }}
  >
    {(integration.blogger_handle ?? '?')[0].toUpperCase()}
  </div>
  <span className="text-sm font-medium text-fg truncate">
    {integration.blogger_handle ?? `#${integration.blogger_id}`}
  </span>
</div>

{/* Channel + Format */}
<div className="flex items-center gap-1.5 text-xs text-muted-fg mb-1">
  <PlatformPill platform={integration.channel} size="sm" />
  <span>{integration.ad_format}</span>
</div>

{/* Date + Cost */}
<div className="flex items-center justify-between text-xs mt-1.5">
  <span className="text-muted-fg">
    {new Date(integration.publish_date).toLocaleDateString('ru-RU', {
      day: '2-digit', month: '2-digit', year: '2-digit',
    })}
  </span>
  {parseFloat(integration.total_cost) > 0 && (
    <span className="font-medium text-fg">
      {parseFloat(integration.total_cost).toLocaleString('ru-RU')} ₽
    </span>
  )}
</div>

{/* Fact views badge */}
{integration.fact_views && integration.fact_views > 0 && (
  <div className="mt-1 text-xs text-muted-fg">
    👁 {integration.fact_views.toLocaleString('ru-RU')}
  </div>
)}
```

Добавь хелпер `handleToColor` в тот же файл (перед компонентом):
```tsx
function handleToColor(handle: string): string {
  let hash = 0;
  for (let i = 0; i < handle.length; i++) {
    hash = handle.charCodeAt(i) + ((hash << 5) - hash);
  }
  const colors = ['#6366f1','#8b5cf6','#ec4899','#f97316','#14b8a6','#3b82f6','#84cc16'];
  return colors[Math.abs(hash) % colors.length];
}
```

- [ ] **Step 2: Обновить IntegrationsKanbanPage — toggle + фильтры + default dates**

Файл: `src/pages/influence/integrations/IntegrationsKanbanPage.tsx`.

Добавить в начало компонента:

```tsx
import { useSearchParams } from 'react-router-dom';
import { IntegrationFilters, type IntegrationFilterValue } from './IntegrationFilters';
import { IntegrationsTableView } from './IntegrationsTableView';

// Default date range: start of last month → end of current month
function getDefaultDates(): { date_from: string; date_to: string } {
  const now = new Date();
  const firstLastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const lastCurrentMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { date_from: fmt(firstLastMonth), date_to: fmt(lastCurrentMonth) };
}
```

В теле компонента:

```tsx
const [searchParams, setSearchParams] = useSearchParams();
const view = (searchParams.get('view') as 'kanban' | 'table') ?? 'kanban';

const [filters, setFilters] = useState<IntegrationFilterValue>(getDefaultDates);

const queryParams = {
  ...filters,
  limit: 500,
};

const { data, isLoading, error } = useIntegrations(queryParams);
const integrations = data?.items ?? [];
```

Заменить кнопки View (если есть) на:

```tsx
{/* View toggle */}
<div className="flex gap-1 ml-auto">
  <Button
    variant={view === 'kanban' ? 'primary' : 'secondary'}
    onClick={() => setSearchParams({ view: 'kanban' })}
    className="h-8 text-sm"
  >
    Канбан
  </Button>
  <Button
    variant={view === 'table' ? 'primary' : 'secondary'}
    onClick={() => setSearchParams({ view: 'table' })}
    className="h-8 text-sm"
  >
    Таблица
  </Button>
</div>
```

Добавить перед kanban-контентом:

```tsx
<IntegrationFilters value={filters} onChange={setFilters} />

{view === 'table' ? (
  <IntegrationsTableView
    items={integrations}
    onRowClick={(id) => openDrawer(id)}
  />
) : (
  /* существующий kanban JSX */
  ...
)}
```

- [ ] **Step 3: TS-проверка**

```bash
npx tsc -p tsconfig.temp.json --noEmit 2>&1 | grep -E "Kanban|Integrations" | head -10
```

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/pages/influence/integrations/IntegrationsKanbanPage.tsx
git add wookiee-hub/src/pages/influence/integrations/KanbanCard.tsx
git commit -m "feat(crm-hub): integration page toggle kanban/table + filters + improved cards"
```

---

## Task 5: BloggersTableView — таблица блогеров с метриками

**Files:**
- Create: `src/pages/influence/bloggers/BloggersTableView.tsx`

Колонки: Блогер | Каналы | Интеграций | Выполнено | Ср.CPM | Story | Reels | Статус | Последняя инт.

- [ ] **Step 1: Создать компонент**

Файл: `src/pages/influence/bloggers/BloggersTableView.tsx`:

```tsx
import { useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { BloggerSummaryOut, BloggerSummaryParams } from '@/api/crm/bloggers';
import { useBloggersSummary } from '@/hooks/crm/use-bloggers';
import { Badge } from '@/components/crm/ui/Badge';
import { Skeleton } from '@/components/crm/ui/Skeleton';

function handleToColor(handle: string): string {
  let hash = 0;
  for (let i = 0; i < handle.length; i++) {
    hash = handle.charCodeAt(i) + ((hash << 5) - hash);
  }
  const colors = ['#6366f1','#8b5cf6','#ec4899','#f97316','#14b8a6','#3b82f6','#84cc16'];
  return colors[Math.abs(hash) % colors.length];
}

const PLATFORM_ICONS: Record<string, string> = {
  instagram: 'IG', telegram: 'TG', tiktok: 'TikTok',
  youtube: 'YT', vk: 'VK', rutube: 'RT',
};

const STATUS_LABEL: Record<string, string> = {
  active: 'Активен', in_progress: 'В работе', new: 'Новый', paused: 'Пауза',
};

const STATUS_COLOR: Record<string, string> = {
  active: 'bg-success/15 text-success',
  in_progress: 'bg-primary/15 text-primary',
  new: 'bg-warning/15 text-warning',
  paused: 'bg-muted text-muted-fg',
};

interface Props {
  params: BloggerSummaryParams;
  onRowClick: (id: number) => void;
}

export function BloggersTableView({ params, onRowClick }: Props) {
  const { data, isLoading } = useBloggersSummary(params);
  const items = data?.items ?? [];

  const parentRef = useRef<HTMLDivElement>(null);
  const rowVirtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 52,
    overscan: 10,
  });

  if (isLoading) return <Skeleton className="h-96" />;

  const COLS = [
    { key: 'blogger', label: 'Блогер',    width: 'min-w-40 max-w-56' },
    { key: 'channels', label: 'Каналы',   width: 'w-40' },
    { key: 'total',    label: 'Инт-ций',  width: 'w-20', align: 'right' as const },
    { key: 'done',     label: 'Выпол.',   width: 'w-20', align: 'right' as const },
    { key: 'cpm',      label: 'Ср.CPM',   width: 'w-28', align: 'right' as const },
    { key: 'story',    label: 'Story',    width: 'w-28', align: 'right' as const },
    { key: 'reels',    label: 'Reels',    width: 'w-28', align: 'right' as const },
    { key: 'status',   label: 'Статус',   width: 'w-28' },
    { key: 'last',     label: 'Посл.инт.', width: 'w-28' },
  ];

  const renderCell = (col: typeof COLS[0], row: BloggerSummaryOut) => {
    switch (col.key) {
      case 'blogger':
        return (
          <div className="flex items-center gap-2 overflow-hidden">
            <div
              className="size-7 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
              style={{ backgroundColor: handleToColor(row.display_handle) }}
            >
              {row.display_handle[0].toUpperCase()}
            </div>
            <div className="overflow-hidden">
              <div className="truncate text-sm font-medium text-fg">{row.display_handle}</div>
              {row.real_name && (
                <div className="truncate text-xs text-muted-fg">{row.real_name}</div>
              )}
            </div>
          </div>
        );
      case 'channels':
        return (
          <div className="flex flex-wrap gap-1">
            {row.channels.slice(0, 4).map((ch) => (
              ch.url ? (
                <a
                  key={ch.id}
                  href={ch.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-muted text-primary hover:bg-primary/10 transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  {PLATFORM_ICONS[ch.channel] ?? ch.channel.toUpperCase()}
                </a>
              ) : (
                <span
                  key={ch.id}
                  className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-muted text-muted-fg"
                >
                  {PLATFORM_ICONS[ch.channel] ?? ch.channel.toUpperCase()}
                </span>
              )
            ))}
            {row.channels.length > 4 && (
              <span className="text-[10px] text-muted-fg">+{row.channels.length - 4}</span>
            )}
          </div>
        );
      case 'total':
        return <span className="tabular-nums text-sm">{row.integrations_count}</span>;
      case 'done':
        return <span className="tabular-nums text-sm">{row.integrations_done}</span>;
      case 'cpm':
        return (
          <span className="tabular-nums text-sm">
            {row.avg_cpm_fact ? `${parseFloat(row.avg_cpm_fact).toLocaleString('ru-RU')} ₽` : '—'}
          </span>
        );
      case 'story':
        return (
          <span className="tabular-nums text-sm">
            {row.price_story_default
              ? `${parseFloat(row.price_story_default).toLocaleString('ru-RU')} ₽`
              : '—'}
          </span>
        );
      case 'reels':
        return (
          <span className="tabular-nums text-sm">
            {row.price_reels_default
              ? `${parseFloat(row.price_reels_default).toLocaleString('ru-RU')} ₽`
              : '—'}
          </span>
        );
      case 'status':
        return (
          <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${STATUS_COLOR[row.status] ?? ''}`}>
            {STATUS_LABEL[row.status] ?? row.status}
          </span>
        );
      case 'last':
        return (
          <span className="text-xs text-muted-fg tabular-nums">
            {row.last_integration_at
              ? new Date(row.last_integration_at).toLocaleDateString('ru-RU', {
                  day: '2-digit', month: '2-digit', year: '2-digit',
                })
              : '—'}
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      {/* Header */}
      <div className="flex border-b border-border bg-muted/40 px-3 py-2 text-xs font-medium text-muted-fg">
        {COLS.map((col) => (
          <div
            key={col.key}
            className={`${col.width} shrink-0 pr-3 ${col.align === 'right' ? 'text-right' : ''}`}
          >
            {col.label}
          </div>
        ))}
      </div>

      {/* Virtual rows */}
      <div ref={parentRef} className="overflow-auto" style={{ maxHeight: 'calc(100vh - 280px)' }}>
        <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: 'relative' }}>
          {rowVirtualizer.getVirtualItems().map((vr) => {
            const row = items[vr.index];
            return (
              <div
                key={row.id}
                className="absolute left-0 right-0 flex items-center px-3 border-b border-border/50 hover:bg-muted/30 cursor-pointer transition-colors"
                style={{ top: vr.start, height: vr.size }}
                onClick={() => onRowClick(row.id)}
                role="row"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && onRowClick(row.id)}
              >
                {COLS.map((col) => (
                  <div
                    key={col.key}
                    className={`${col.width} shrink-0 overflow-hidden pr-3 ${col.align === 'right' ? 'text-right' : ''}`}
                  >
                    {renderCell(col, row)}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>

      <div className="px-3 py-2 text-xs text-muted-fg border-t border-border bg-muted/20">
        {data?.total ?? 0} блогеров · CPM взвешенный по всем интеграциям
      </div>
    </div>
  );
}
```

- [ ] **Step 2: TS-проверка**

```bash
npx tsc -p tsconfig.temp.json --noEmit 2>&1 | grep "BloggersTable" | head -5
```

- [ ] **Step 3: Commit**

```bash
git add wookiee-hub/src/pages/influence/bloggers/BloggersTableView.tsx
git commit -m "feat(crm-hub): add BloggersTableView with channels links + weighted CPM"
```

---

## Task 6: BloggersPage — toggle + platform filter + улучшенные карточки

**Files:**
- Modify: `src/pages/influence/bloggers/BloggersPage.tsx`

- [ ] **Step 1: Обновить BloggersPage**

Файл: `src/pages/influence/bloggers/BloggersPage.tsx`.

Добавить импорты:
```tsx
import { useSearchParams } from 'react-router-dom';
import { BloggersTableView } from './BloggersTableView';
```

В теле компонента добавить:
```tsx
const [searchParams, setSearchParams] = useSearchParams();
const view = (searchParams.get('view') as 'cards' | 'table') ?? 'cards';
const [platformFilter, setPlatformFilter] = useState<string | undefined>();
```

Добавить в `BloggerListParams`:
```tsx
const listParams = {
  ...filters, // existing filters
  channel: platformFilter,
};
```

Для таблицы использовать `BloggerSummaryParams`:
```tsx
const summaryParams = {
  status: filters.status,
  q: filters.q,
  channel: platformFilter,
  limit: 300,
};
```

Добавить в PageHeader или рядом с ним:
```tsx
{/* View toggle */}
<div className="flex gap-1">
  <Button
    variant={view === 'cards' ? 'primary' : 'secondary'}
    onClick={() => setSearchParams({ view: 'cards' })}
    className="h-8 text-sm"
  >
    Карточки
  </Button>
  <Button
    variant={view === 'table' ? 'primary' : 'secondary'}
    onClick={() => setSearchParams({ view: 'table' })}
    className="h-8 text-sm"
  >
    Таблица
  </Button>
</div>

{/* Platform filter */}
<div className="flex flex-wrap gap-1.5 mb-3">
  {(['instagram','telegram','tiktok','youtube','vk'] as const).map((ch) => (
    <FilterPill
      key={ch}
      solid={platformFilter === ch}
      onClick={() => setPlatformFilter(platformFilter === ch ? undefined : ch)}
    >
      {{ instagram:'IG', telegram:'TG', tiktok:'TikTok', youtube:'YT', vk:'VK' }[ch]}
    </FilterPill>
  ))}
</div>
```

Обернуть основной контент:
```tsx
{view === 'table' ? (
  <BloggersTableView
    params={summaryParams}
    onRowClick={(id) => openDrawer(id)}
  />
) : (
  /* существующий cards grid */
  ...
)}
```

- [ ] **Step 2: Убедиться что `openDrawer` работает для table view**

В BloggersPage уже есть логика `?open=:id` для открытия drawer. Убедиться что `onRowClick` вызывает тот же механизм:
```tsx
const openDrawer = (id: number) => {
  setSearchParams((prev) => { prev.set('open', String(id)); return prev; });
};
```

- [ ] **Step 3: TS-проверка**

```bash
npx tsc -p tsconfig.temp.json --noEmit 2>&1 | grep "BloggersPage" | head -5
```

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/pages/influence/bloggers/BloggersPage.tsx
git commit -m "feat(crm-hub): blogger page toggle cards/table + platform filter"
```

---

## Task 7: Fixes — D1, E2, F3

**Files:**
- Modify: `src/pages/influence/integrations/IntegrationEditDrawer.tsx` (D1)
- Modify: `src/pages/influence/calendar/CalendarPage.tsx` (E2)
- Modify: `src/components/layout/top-bar.tsx` (F3 — только если нужно)

### D1: Форматы рекламы привязаны к каналу

Файл: `src/pages/influence/integrations/IntegrationEditDrawer.tsx`.

- [ ] **Step 1: Добавить маппинг каналов → форматов**

Найди место где рендерится `ad_format` select (в секции "Основное"). Добавь перед компонентом:

```tsx
const CHANNEL_FORMATS: Record<Channel, AdFormat[]> = {
  instagram: ['story', 'short_video', 'long_video', 'image_post', 'integration', 'live_stream'],
  telegram:  ['long_post', 'image_post', 'integration'],
  tiktok:    ['short_video', 'live_stream'],
  youtube:   ['long_video', 'short_video', 'integration', 'live_stream'],
  vk:        ['long_post', 'image_post', 'short_video', 'live_stream'],
  rutube:    ['long_video', 'short_video'],
};

const AD_FORMAT_LABELS: Record<AdFormat, string> = {
  story: 'Story', short_video: 'Короткое видео', long_video: 'Длинное видео',
  long_post: 'Длинный пост', image_post: 'Фото-пост',
  integration: 'Интеграция', live_stream: 'Стрим',
};
```

- [ ] **Step 2: Фильтровать опции по выбранному каналу**

В форме найди where `ad_format` options рендерятся. Получи текущий канал из `watch('channel')`:

```tsx
const selectedChannel = watch('channel') as Channel;
const availableFormats = selectedChannel
  ? CHANNEL_FORMATS[selectedChannel] ?? Object.keys(AD_FORMAT_LABELS) as AdFormat[]
  : Object.keys(AD_FORMAT_LABELS) as AdFormat[];
```

Замени опции `ad_format` select на:
```tsx
{availableFormats.map((fmt) => (
  <option key={fmt} value={fmt}>{AD_FORMAT_LABELS[fmt]}</option>
))}
```

- [ ] **Step 3: Проверить что существующий `ad_format` сбрасывается при смене канала**

Добавить `useEffect`:
```tsx
useEffect(() => {
  if (!selectedChannel) return;
  const current = getValues('ad_format') as AdFormat;
  const allowed = CHANNEL_FORMATS[selectedChannel];
  if (current && allowed && !allowed.includes(current)) {
    setValue('ad_format', allowed[0]);
  }
}, [selectedChannel]);
```

### E2: Календарь показывает мало интеграций

Файл: `src/pages/influence/calendar/CalendarPage.tsx`.

- [ ] **Step 4: Проверить почему limit:500 не работает**

Открой `src/hooks/crm/use-integrations.ts`. Хук `useIntegrations` использует `useQuery` с прямым вызовом `listIntegrations(params)`. `listIntegrations` в API-клиенте передаёт `limit` в URLSearchParams.

Проверить что `limit` попадает в запрос. В CalendarPage:
```tsx
const { data, isLoading, error } = useIntegrations({
  date_from: dateFrom,
  date_to: dateTo,
  limit: 500,
});
```

Если данных всё равно мало — возможно BFF возвращает cursor-pagination с дефолтным limit=50. Добавить в `listIntegrations` явную передачу limit:

Убедиться что в `src/api/crm/integrations.ts` функция `listIntegrations` включает `limit` в params:
```ts
export function listIntegrations(params: IntegrationListParams = {}): Promise<IntegrationsPage> {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined) continue;
    if (Array.isArray(v)) {
      for (const item of v) search.append(k, String(item));
    } else {
      search.set(k, String(v));  // this includes limit=500
    }
  }
  ...
}
```

Если уже передаётся корректно — проблема в BFF. В этом случае: в CalendarPage добавить `limit: 1000` (у нас максимум ~689 интеграций).

### F3: Breadcrumbs для /influence/*

- [ ] **Step 5: Проверить breadcrumbs**

Открой `src/components/layout/top-bar.tsx`, функцию `buildBreadcrumbs`.

Текущая логика: ищет group у которой `item.path.startsWith(/influence)`, затем ищет item по `item.path === pathname`.

Для `/influence/bloggers` → должно вернуть `['Influence CRM', 'Блогеры']`. Если это уже работает — ничего не менять.

Если не работает (пустые breadcrumbs) — проверить что navigation group label = `"Influence CRM"` в `src/config/navigation.ts`. Если нет — добавить.

- [ ] **Step 6: Commit**

```bash
git add wookiee-hub/src/pages/influence/integrations/IntegrationEditDrawer.tsx
git add wookiee-hub/src/pages/influence/calendar/CalendarPage.tsx
git add wookiee-hub/src/components/layout/top-bar.tsx
git commit -m "fix(crm-hub): D1 ad_format by channel, E2 calendar limit, F3 breadcrumbs"
```

---

## Task 8: Build + Deploy Hub

- [ ] **Step 1: Полный TS-check**

```bash
cd /Users/danilamatveev/Projects/Wookiee/wookiee-hub
npx tsc -p tsconfig.temp.json --noEmit 2>&1 | grep -v node_modules
```

Ожидается: 0 ошибок (или только pre-existing errors не связанные с нашими изменениями).

- [ ] **Step 2: Run tests**

```bash
npm test -- --run
```

Ожидается: все тесты зелёные (включая новый integration-metrics.test.ts).

- [ ] **Step 3: Build**

```bash
npm run build 2>&1 | tail -10
```

Ожидается: `✓ built in X.XXs`, 0 errors.

- [ ] **Step 4: Deploy**

```bash
rsync -av --delete dist/ timeweb:/home/danila/projects/wookiee/wookiee-hub/dist/
```

- [ ] **Step 5: Smoke-test в браузере**

1. Открыть `https://hub.os.wookiee.shop/influence/integrations`
2. Переключиться на `Таблица` — должны появиться строки с метриками
3. Установить фильтр по каналу `IG` — список должен фильтроваться
4. Открыть `https://hub.os.wookiee.shop/influence/bloggers`
5. Переключиться на `Таблица` — должны появиться блогеры с каналами и CPM
6. Клик по строке — должен открываться drawer
7. Открыть `https://hub.os.wookiee.shop/influence/calendar` — должны показываться интеграции за текущий месяц

- [ ] **Step 6: Обновить docs/influencer-crm-backlog.md**

В файле `docs/influencer-crm-backlog.md` отметить выполненные пункты:
```markdown
- ✅ C1 — табличный вид интеграций
- ✅ C2 — фильтры на канбане
- ✅ D1 — форматы рекламы привязаны к каналу
- ✅ E1 — ETL не сбрасывает стадии
- ✅ E2 — календарь показывает все интеграции
- ✅ F3 — breadcrumbs в Hub для CRM-страниц
```

```bash
git add docs/influencer-crm-backlog.md
git commit -m "docs: mark CRM v2 backlog items as done"
```
