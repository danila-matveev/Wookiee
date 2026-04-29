import { describe, expect, it } from 'vitest';
import { decodeCursor, encodeCursor } from './cursor';

describe('cursor', () => {
  it('encode/decode round-trips', () => {
    const c = encodeCursor('2026-04-28T12:00:00+00:00', 42);
    const d = decodeCursor(c);
    expect(d).toEqual({ updatedAt: '2026-04-28T12:00:00+00:00', id: 42 });
  });

  it('returns null for garbage input', () => {
    expect(decodeCursor('not-base64!')).toBeNull();
    expect(decodeCursor('')).toBeNull();
  });

  it('produces base64-of-json shape (must match Python encode_cursor)', () => {
    const c = encodeCursor('2026-04-28T12:00:00+00:00', 42);
    const decoded = JSON.parse(atob(c));
    expect(decoded).toEqual(['2026-04-28T12:00:00+00:00', 42]);
  });
});
