import { useMemo } from 'react';
import { STAGE_LABELS, type Stage } from '@/api/integrations';
import type { ProductDetailIntegrationOut } from '@/api/products';
import { useProduct } from '@/hooks/use-products';
import { Badge } from '@/ui/Badge';
import { EmptyState } from '@/ui/EmptyState';
import { Skeleton } from '@/ui/Skeleton';

const RU_MONTHS = [
  'январь',
  'февраль',
  'март',
  'апрель',
  'май',
  'июнь',
  'июль',
  'август',
  'сентябрь',
  'октябрь',
  'ноябрь',
  'декабрь',
];

// Money is a decimal string from BFF — sum via BigInt cents to avoid float drift.
// Matches the SlicesPage helpers; kept local to avoid a circular module dep.
function toCents(value: string | null | undefined): bigint {
  if (!value) return 0n;
  const trimmed = value.trim();
  if (trimmed === '') return 0n;
  const negative = trimmed.startsWith('-');
  const unsigned = negative ? trimmed.slice(1) : trimmed;
  const [whole, frac = ''] = unsigned.split('.');
  const fracPadded = `${frac}00`.slice(0, 2);
  const digits = (whole || '0') + fracPadded;
  if (!/^\d+$/.test(digits)) return 0n;
  const n = BigInt(digits);
  return negative ? -n : n;
}

function formatRub(cents: bigint): string {
  const rubles = cents / 100n;
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(Number(rubles));
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  return `${dd}.${mm}`;
}

function monthKey(iso: string): string {
  // YYYY-MM. We slice instead of constructing Date to dodge timezone shifts on
  // ISO date-only strings ("2026-05-12" → Date is UTC midnight, which can be
  // the previous day in negative timezones).
  return iso.slice(0, 7);
}

function monthLabel(key: string): string {
  const [yearStr, monthStr] = key.split('-');
  const monthIdx = Number(monthStr) - 1;
  const monthName = RU_MONTHS[monthIdx] ?? monthStr;
  return `${monthName} ${yearStr}`;
}

interface ProductSliceCardProps {
  modelOsnovaId: number;
  onClose: () => void;
}

export function ProductSliceCard({ modelOsnovaId, onClose }: ProductSliceCardProps) {
  const { data, isLoading, isError } = useProduct(modelOsnovaId);

  // Group integrations by YYYY-MM, descending. Within a group, keep BFF order
  // (already publish_date DESC).
  const grouped = useMemo(() => {
    const map = new Map<string, ProductDetailIntegrationOut[]>();
    for (const i of data?.integrations ?? []) {
      const k = monthKey(i.publish_date);
      const arr = map.get(k);
      if (arr) {
        arr.push(i);
      } else {
        map.set(k, [i]);
      }
    }
    return Array.from(map.entries()).sort((a, b) => (a[0] < b[0] ? 1 : -1));
  }, [data?.integrations]);

  return (
    <section className="bg-card border border-border-strong rounded-lg shadow-warm p-5 mt-6">
      <header className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="font-display text-xl font-semibold text-fg">
            {data?.model_name ?? '...'}
          </h2>
          <p className="text-sm text-muted-fg mt-0.5">Срез по интеграциям</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-muted-fg hover:text-fg text-sm cursor-pointer"
          aria-label="Закрыть срез"
        >
          Закрыть
        </button>
      </header>

      {/*
        Halo strip (substitute_articles): T17 deferral.
        BFF /products/:id currently returns only model-level aggregates +
        integrations. There is no endpoint that lists substitute_articles for a
        given model_osnova_id, and integration_substitute_articles join lives
        only inside the products repo CTE. We render a placeholder strip and
        keep the layout — once the BFF exposes substitute_articles per product,
        the data lands here unchanged.
      */}
      <div className="rounded-md border border-dashed border-border bg-muted/40 px-3.5 py-2.5 mb-5 text-xs text-muted-fg">
        Halo (substitute_articles) — ожидает расширения BFF.
      </div>

      {isLoading ? (
        <Skeleton className="h-48" />
      ) : isError ? (
        <EmptyState title="Не удалось загрузить срез" description="Попробуйте обновить страницу." />
      ) : grouped.length === 0 ? (
        <EmptyState
          title="Интеграций пока нет"
          description="По этой модели ещё не было интеграций."
        />
      ) : (
        <div className="flex flex-col gap-5">
          {grouped.map(([key, items]) => {
            const total = items.reduce((acc, i) => acc + toCents(i.total_cost), 0n);
            return (
              <div key={key}>
                <div className="flex items-baseline justify-between mb-2">
                  <h3 className="text-sm font-semibold text-fg capitalize">{monthLabel(key)}</h3>
                  <span className="font-mono text-sm text-muted-fg">
                    {formatRub(total)} ₽ • {items.length} шт
                  </span>
                </div>
                <ul className="divide-y divide-border border border-border rounded-md overflow-hidden">
                  {items.map((i) => (
                    <li
                      key={i.integration_id}
                      className="flex items-center justify-between gap-3 px-3.5 py-2.5 bg-card text-sm"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="font-mono text-xs text-muted-fg shrink-0">
                          {formatDate(i.publish_date)}
                        </span>
                        <span className="truncate text-fg">{i.blogger_handle}</span>
                        <Badge tone="secondary">{STAGE_LABELS[i.stage as Stage] ?? i.stage}</Badge>
                      </div>
                      <span className="font-mono text-sm text-fg shrink-0">
                        {formatRub(toCents(i.total_cost))} ₽
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

export default ProductSliceCard;
