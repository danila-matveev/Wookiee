import { Download } from 'lucide-react';
import { type ReactNode, useMemo, useState } from 'react';
import {
  type Channel,
  type IntegrationOut,
  type Marketplace,
  STAGE_LABELS,
  type Stage,
} from '@/api/integrations';
import { useIntegrations } from '@/hooks/use-integrations';
import { PageHeader } from '@/layout/PageHeader';
import { Button } from '@/ui/Button';
import { KpiCard } from '@/ui/KpiCard';
import { QueryStatusBoundary } from '@/ui/QueryStatusBoundary';
import { Skeleton } from '@/ui/Skeleton';
import { SlicesFilters, type SlicesFilterValue } from './SlicesFilters';

const MARKETPLACE_LABEL: Record<Marketplace, string> = {
  wb: 'WB',
  ozon: 'OZON',
  both: 'WB+OZON',
};

const CHANNEL_LABEL: Record<Channel, string> = {
  instagram: 'Instagram',
  telegram: 'Telegram',
  tiktok: 'TikTok',
  youtube: 'YouTube',
  vk: 'VK',
  rutube: 'Rutube',
};

// --- Decimal helpers (BigInt cents) ---------------------------------------
// We can't use Decimal natively in JS, so we represent money as BigInt cents.
// This avoids float drift across many rows and survives any intermediate maths.
function toCents(value: string | null | undefined): bigint {
  if (!value) return 0n;
  const trimmed = value.trim();
  if (trimmed === '') return 0n;
  const negative = trimmed.startsWith('-');
  const unsigned = negative ? trimmed.slice(1) : trimmed;
  const [whole, frac = ''] = unsigned.split('.');
  const fracPadded = (frac + '00').slice(0, 2);
  const digits = (whole || '0') + fracPadded;
  // Defensive: ignore any garbage non-digit chars rather than crashing.
  if (!/^\d+$/.test(digits)) return 0n;
  const n = BigInt(digits);
  return negative ? -n : n;
}

function formatCents(cents: bigint): string {
  const negative = cents < 0n;
  const abs = negative ? -cents : cents;
  const padded = abs.toString().padStart(3, '0');
  const whole = padded.slice(0, -2);
  const frac = padded.slice(-2);
  return `${negative ? '-' : ''}${whole}.${frac}`;
}

function sumDecimal(values: (string | null | undefined)[]): bigint {
  let sum = 0n;
  for (const v of values) sum += toCents(v);
  return sum;
}

function formatRub(cents: bigint): string {
  // Display in whole rubles for KPI cards — kopeks would clutter the metric.
  const rubles = cents / 100n;
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(Number(rubles));
}

function formatInt(value: number): string {
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(value);
}

function formatPct(value: number): string {
  if (!Number.isFinite(value)) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

function computeKpis(items: IntegrationOut[]) {
  const spendCents = sumDecimal(items.map((i) => i.total_cost));
  const revenueCents = sumDecimal(items.map((i) => i.fact_revenue));
  const reach = items.reduce((s, i) => s + (i.fact_views ?? 0), 0);
  const orders = items.reduce((s, i) => s + (i.fact_orders ?? 0), 0);

  // ROMI = (revenue − spend) / spend × 100. Can't do this in pure BigInt without
  // losing precision on a percentage, so do the final ratio in Number once we have
  // aggregated cents. Acceptable: we lost zero precision while accumulating.
  let romi = Number.NaN;
  if (spendCents > 0n) {
    const profit = revenueCents - spendCents;
    romi = (Number(profit) / Number(spendCents)) * 100;
  }

  return { spendCents, revenueCents, reach, orders, romi };
}

// --- CSV export ----------------------------------------------------------
function exportCsv(rows: IntegrationOut[]) {
  const header = [
    'date',
    'blogger_id',
    'marketplace',
    'channel',
    'stage',
    'total_cost',
    'fact_views',
    'fact_orders',
    'fact_revenue',
  ];
  const escapeCell = (s: unknown) => `"${String(s ?? '').replace(/"/g, '""')}"`;
  const lines = [
    header.join(','),
    ...rows.map((r) =>
      [
        r.publish_date,
        r.blogger_id,
        r.marketplace,
        r.channel,
        r.stage,
        r.total_cost,
        r.fact_views,
        r.fact_orders,
        r.fact_revenue,
      ]
        .map(escapeCell)
        .join(','),
    ),
  ];
  // ﻿ BOM helps Excel auto-detect UTF-8 with Cyrillic.
  const blob = new Blob(['﻿' + lines.join('\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `slices-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// --- Page ----------------------------------------------------------------
export function SlicesPage() {
  const [filters, setFilters] = useState<SlicesFilterValue>({});

  // Large limit: T16 is read-only analytics — we want the whole window in memory
  // for client-side aggregation. The BFF caps at 1000.
  const { data, isLoading, error } = useIntegrations({
    marketplace: filters.marketplace,
    date_from: filters.date_from,
    date_to: filters.date_to,
    marketer_id: filters.marketer_id,
    limit: 1000,
  });

  const items = useMemo(() => data?.items ?? [], [data?.items]);
  const kpis = useMemo(() => computeKpis(items), [items]);

  return (
    <>
      <PageHeader
        title="Срезы интеграций"
        sub="Агрегированные метрики по фильтрам. CSV-выгрузка по текущему срезу."
        actions={
          <Button
            variant="secondary"
            onClick={() => exportCsv(items)}
            disabled={items.length === 0}
          >
            <Download size={16} /> Экспорт CSV
          </Button>
        }
      />

      <SlicesFilters value={filters} onChange={setFilters} />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <KpiCard
          title="Расход"
          value={`${formatRub(kpis.spendCents)} ₽`}
          accent="primary"
          hint={`${items.length} интеграций`}
        />
        <KpiCard title="Просмотры" value={formatInt(kpis.reach)} accent="info" />
        <KpiCard title="Заказы" value={formatInt(kpis.orders)} accent="success" />
        <KpiCard
          title="ROMI"
          value={formatPct(kpis.romi)}
          accent="pink"
          hint={`Выручка ${formatRub(kpis.revenueCents)} ₽`}
        />
      </div>

      <QueryStatusBoundary
        isLoading={isLoading}
        error={error}
        isEmpty={items.length === 0}
        loadingFallback={<Skeleton className="h-64" />}
        emptyTitle="Нет интеграций под фильтр"
        emptyDescription="Уберите часть фильтров или расширьте период."
      >
        <ResultsTable rows={items} />
      </QueryStatusBoundary>
    </>
  );
}

interface ResultsTableProps {
  rows: IntegrationOut[];
}

function ResultsTable({ rows }: ResultsTableProps) {
  return (
    <div className="bg-card border border-border-strong rounded-lg shadow-warm overflow-hidden">
      <table className="w-full">
        <caption className="sr-only">
          Список интеграций с метриками по дате, блогеру, маркетплейсу и каналу
        </caption>
        <thead>
          <tr>
            <Th>Дата</Th>
            <Th>Блогер</Th>
            <Th>Маркетплейс</Th>
            <Th>Канал</Th>
            <Th>Стадия</Th>
            <Th className="text-right">Стоимость, ₽</Th>
            <Th className="text-right">Просмотры</Th>
            <Th className="text-right">Заказы</Th>
            <Th className="text-right">Выручка, ₽</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-border">
              <td className="px-3.5 py-3 font-mono text-sm text-fg">
                {formatDate(r.publish_date)}
              </td>
              <td className="px-3.5 py-3 text-sm text-fg">Блогер #{r.blogger_id}</td>
              <td className="px-3.5 py-3 text-sm text-fg">{MARKETPLACE_LABEL[r.marketplace]}</td>
              <td className="px-3.5 py-3 text-sm text-fg">{channelLabel(r.channel)}</td>
              <td className="px-3.5 py-3 text-sm text-muted-fg">
                {STAGE_LABELS[r.stage as Stage] ?? r.stage}
              </td>
              <td className="px-3.5 py-3 font-mono text-sm text-right text-fg">
                {formatRub(toCents(r.total_cost))}
              </td>
              <td className="px-3.5 py-3 font-mono text-sm text-right text-muted-fg">
                {r.fact_views == null ? '—' : formatInt(r.fact_views)}
              </td>
              <td className="px-3.5 py-3 font-mono text-sm text-right text-muted-fg">
                {r.fact_orders == null ? '—' : formatInt(r.fact_orders)}
              </td>
              <td className="px-3.5 py-3 font-mono text-sm text-right text-muted-fg">
                {r.fact_revenue == null ? '—' : formatRub(toCents(r.fact_revenue))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Th({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <th
      className={`bg-muted text-[11.5px] uppercase tracking-wider text-muted-fg font-semibold px-3.5 py-2.5 text-left ${className}`}
    >
      {children}
    </th>
  );
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const yy = d.getFullYear();
    return `${dd}.${mm}.${yy}`;
  } catch {
    return iso;
  }
}

function channelLabel(channel: string): string {
  return CHANNEL_LABEL[channel as Channel] ?? channel;
}

export default SlicesPage;

// Re-exports for tests / consumers.
export { computeKpis, exportCsv, formatCents, sumDecimal, toCents };
