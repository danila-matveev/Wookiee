/**
 * Russian-locale formatters used across screens.
 *
 * Money is always passed as a string (Decimal-as-string from the BFF) — never
 * a JS Number — to preserve cent precision in line with the project's Decimal
 * rule. The conversion to Number happens only at format time and only after
 * NaN/range guards.
 */

const ruNumber = new Intl.NumberFormat('ru-RU');
const ruRub = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  maximumFractionDigits: 0,
});
const ruDate = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
});
const ruMonth = new Intl.DateTimeFormat('ru-RU', { month: 'long', year: 'numeric' });

export function formatInt(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return ruNumber.format(value);
}

/** Decimal-as-string → Russian rouble amount. Returns '—' for null/empty/NaN. */
export function formatRub(value: string | number | null | undefined): string {
  if (value == null || value === '') return '—';
  const num = typeof value === 'string' ? Number.parseFloat(value) : value;
  if (!Number.isFinite(num)) return '—';
  return ruRub.format(num);
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return ruDate.format(d);
}

export function formatMonth(iso: string | Date | null | undefined): string {
  if (!iso) return '—';
  const d = typeof iso === 'string' ? new Date(iso) : iso;
  if (Number.isNaN(d.getTime())) return '—';
  return ruMonth.format(d);
}

export function formatPct(value: number | null | undefined, fractionDigits = 1): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${value.toFixed(fractionDigits)}%`;
}
