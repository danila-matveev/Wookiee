import { useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { IntegrationOut, Stage } from '@/api/crm/integrations';
import { STAGE_LABELS } from '@/api/crm/integrations';
import { cn } from '@/lib/utils';

// ─── Exported helper functions (tested in integration-metrics.test.ts) ─────────

/** Format a number or null metric — null → "—", number → locale string */
export function formatMetric(value: number | null | undefined): string {
  if (value == null) return '—';
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(value);
}

/**
 * ROMI = fact_revenue / total_cost
 * Returns "—" when revenue is null/zero, or cost is 0.
 */
export function formatRomi(
  fact_revenue: string | null | undefined,
  total_cost: string | null | undefined,
): string {
  if (fact_revenue == null) return '—';
  const revenue = Number(fact_revenue);
  const cost = Number(total_cost ?? '0');
  if (!Number.isFinite(cost) || cost === 0) return '—';
  if (!Number.isFinite(revenue)) return '—';
  return `${(revenue / cost).toFixed(2)}x`;
}

/**
 * Δ CPM = (fact_cpm - plan_cpm) / plan_cpm * 100
 * Returns "+10%" / "-10%" / "—"
 */
export function formatPlanFactDelta(
  fact: string | null | undefined,
  plan: string | null | undefined,
): string {
  if (fact == null || plan == null) return '—';
  const f = Number(fact);
  const p = Number(plan);
  if (!Number.isFinite(f) || !Number.isFinite(p) || p === 0) return '—';
  const pct = Math.round(((f - p) / p) * 100);
  return pct >= 0 ? `+${pct}%` : `${pct}%`;
}

// ─── Stage badge colors ────────────────────────────────────────────────────────

const STAGE_COLOR: Record<Stage, string> = {
  переговоры: 'bg-amber-100 text-amber-800',
  согласовано: 'bg-blue-100 text-blue-800',
  отправка_комплекта: 'bg-indigo-100 text-indigo-800',
  контент: 'bg-purple-100 text-purple-800',
  запланировано: 'bg-sky-100 text-sky-800',
  аналитика: 'bg-teal-100 text-teal-800',
  завершено: 'bg-green-100 text-green-800',
  архив: 'bg-gray-100 text-gray-500',
};

// ─── Column definitions ────────────────────────────────────────────────────────

interface ColDef {
  key: string;
  label: string;
  width: number;
  align?: 'left' | 'right';
  render: (item: IntegrationOut) => string | React.ReactNode;
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const yy = String(d.getFullYear()).slice(2);
    return `${dd}.${mm}.${yy}`;
  } catch {
    return iso;
  }
}

function formatCost(value: string | null | undefined): string {
  if (value == null) return '—';
  const num = Number(value);
  if (!Number.isFinite(num) || num === 0) return '—';
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(num) + ' ₽';
}

const AD_FORMAT_LABELS: Record<string, string> = {
  story: 'Story',
  short_video: 'Reels/Short',
  long_video: 'Long Video',
  long_post: 'Long Post',
  image_post: 'Image Post',
  integration: 'Integration',
  live_stream: 'Live',
};

const CHANNEL_LABELS: Record<string, string> = {
  instagram: 'Instagram',
  telegram: 'Telegram',
  tiktok: 'TikTok',
  youtube: 'YouTube',
  vk: 'VK',
  rutube: 'Rutube',
};

const COLUMNS: ColDef[] = [
  {
    key: 'blogger',
    label: 'Блогер',
    width: 140,
    render: (item) => item.blogger_handle ?? `#${item.blogger_id}`,
  },
  {
    key: 'product',
    label: 'Товар',
    width: 100,
    render: (item) => item.primary_substitute_code ?? '—',
  },
  {
    key: 'channel',
    label: 'Канал',
    width: 90,
    render: (item) => CHANNEL_LABELS[item.channel] ?? item.channel,
  },
  {
    key: 'format',
    label: 'Формат',
    width: 110,
    render: (item) => AD_FORMAT_LABELS[item.ad_format] ?? item.ad_format,
  },
  {
    key: 'date',
    label: 'Дата',
    width: 80,
    render: (item) => formatDate(item.publish_date),
  },
  {
    key: 'stage',
    label: 'Стадия',
    width: 130,
    render: (item) => (
      <span
        className={cn(
          'inline-block rounded-full px-2 py-0.5 text-xs font-medium',
          STAGE_COLOR[item.stage] ?? 'bg-gray-100 text-gray-500',
        )}
      >
        {STAGE_LABELS[item.stage] ?? item.stage}
      </span>
    ),
  },
  {
    key: 'cost',
    label: 'Стоимость',
    width: 110,
    align: 'right',
    render: (item) => formatCost(item.total_cost),
  },
  {
    key: 'views',
    label: 'Охват',
    width: 90,
    align: 'right',
    render: (item) => formatMetric(item.fact_views),
  },
  {
    key: 'cpm',
    label: 'CPM',
    width: 90,
    align: 'right',
    render: (item) => {
      if (item.fact_cpm == null) return '—';
      const n = Number(item.fact_cpm);
      if (!Number.isFinite(n)) return '—';
      return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(n) + ' ₽';
    },
  },
  {
    key: 'romi',
    label: 'ROMI',
    width: 80,
    align: 'right',
    render: (item) => formatRomi(item.fact_revenue, item.total_cost),
  },
  {
    key: 'carts',
    label: 'Корзины',
    width: 80,
    align: 'right',
    render: (item) => formatMetric(item.fact_carts),
  },
  {
    key: 'orders',
    label: 'Заказы',
    width: 80,
    align: 'right',
    render: (item) => formatMetric(item.fact_orders),
  },
  {
    key: 'delta_cpm',
    label: 'Δ CPM',
    width: 80,
    align: 'right',
    render: (item) => {
      const delta = formatPlanFactDelta(item.fact_cpm, item.plan_cpm);
      if (delta === '—') return delta;
      const isPositive = delta.startsWith('+');
      // positive delta = fact > plan = overspend on CPM = bad
      return (
        <span className={isPositive ? 'text-red-600' : 'text-green-600'}>{delta}</span>
      );
    },
  },
];

// ─── Component ────────────────────────────────────────────────────────────────

export interface IntegrationsTableViewProps {
  items: IntegrationOut[];
  onRowClick: (id: number) => void;
}

const ROW_HEIGHT = 44;

export function IntegrationsTableView({ items, onRowClick }: IntegrationsTableViewProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });

  const totalHeight = virtualizer.getTotalSize();
  const virtualRows = virtualizer.getVirtualItems();

  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-border bg-surface">
      {/* Sticky header */}
      <div className="flex min-w-max border-b border-border bg-muted/40">
        {COLUMNS.map((col) => (
          <div
            key={col.key}
            style={{ width: col.width, minWidth: col.width }}
            className={cn(
              'px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-fg',
              col.align === 'right' ? 'text-right' : 'text-left',
            )}
          >
            {col.label}
          </div>
        ))}
      </div>

      {/* Scrollable virtual list */}
      <div ref={parentRef} className="flex-1 overflow-auto" style={{ height: 'calc(100vh - 280px)' }}>
        <div style={{ height: totalHeight, width: '100%', position: 'relative' }}>
          {virtualRows.map((virtualRow) => {
            const item = items[virtualRow.index];
            return (
              <button
                key={virtualRow.key}
                type="button"
                data-testid={`table-row-${item.id}`}
                onClick={() => onRowClick(item.id)}
                style={{
                  position: 'absolute',
                  top: virtualRow.start,
                  left: 0,
                  width: '100%',
                  height: ROW_HEIGHT,
                }}
                className={cn(
                  'flex min-w-max items-center border-b border-border/50',
                  'cursor-pointer text-left transition-colors',
                  'hover:bg-primary-light/30 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary/30',
                  virtualRow.index % 2 === 0 ? 'bg-surface' : 'bg-muted/20',
                )}
              >
                {COLUMNS.map((col) => (
                  <div
                    key={col.key}
                    style={{ width: col.width, minWidth: col.width }}
                    className={cn(
                      'truncate px-3 py-2.5 text-sm text-fg',
                      col.align === 'right' ? 'text-right' : 'text-left',
                    )}
                  >
                    {col.render(item)}
                  </div>
                ))}
              </button>
            );
          })}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-border bg-muted/20 px-4 py-2 text-xs text-muted-fg">
        <span>{items.length} строк</span>
        <span>ROMI = выручка / стоимость (без учёта себестоимости)</span>
      </div>
    </div>
  );
}

export default IntegrationsTableView;
