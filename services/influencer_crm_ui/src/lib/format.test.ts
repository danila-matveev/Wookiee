import { describe, expect, it } from 'vitest';
import { formatDate, formatInt, formatMonth, formatPct, formatRub } from './format';

describe('format', () => {
  it('formatInt — Russian thousands separator', () => {
    // ru-RU uses NBSP as thousands separator
    expect(formatInt(1234567)).toMatch(/1.234.567/);
    expect(formatInt(0)).toBe('0');
    expect(formatInt(null)).toBe('—');
    expect(formatInt(Number.NaN)).toBe('—');
  });

  it('formatRub — currency with rouble sign and no fractional digits', () => {
    const rub = formatRub('15000');
    expect(rub).toMatch(/15.000/);
    expect(rub).toMatch(/₽/);
    expect(formatRub(null)).toBe('—');
    expect(formatRub('')).toBe('—');
    expect(formatRub('not-a-number')).toBe('—');
  });

  it('formatDate — DD MMM YYYY ru-RU', () => {
    const d = formatDate('2026-04-28T10:00:00Z');
    expect(d).toMatch(/2026/);
    expect(formatDate(null)).toBe('—');
    expect(formatDate('garbage')).toBe('—');
  });

  it('formatMonth — full month name + year', () => {
    const m = formatMonth('2026-04-28T10:00:00Z');
    expect(m).toMatch(/2026/);
    expect(m.toLowerCase()).toMatch(/апрель/);
    expect(formatMonth(null)).toBe('—');
  });

  it('formatPct — fixed fraction digits', () => {
    expect(formatPct(12.345)).toBe('12.3%');
    expect(formatPct(12.345, 2)).toBe('12.35%');
    expect(formatPct(null)).toBe('—');
    expect(formatPct(Number.NaN)).toBe('—');
  });
});
