import { describe, it, expect } from 'vitest';
import {
  formatMetric,
  formatRomi,
  formatPlanFactDelta,
} from '../IntegrationsTableView';

describe('integration metrics helpers', () => {
  it('formatRomi returns ratio', () => {
    expect(formatRomi('150000', '50000')).toBe('3.00x');
  });
  it('formatRomi returns — when no revenue', () => {
    expect(formatRomi(null, '50000')).toBe('—');
  });
  it('formatRomi returns — when cost is 0', () => {
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
  it('formatMetric number returns string', () => {
    expect(typeof formatMetric(12400)).toBe('string');
    expect(formatMetric(12400)).not.toBe('—');
  });
});
