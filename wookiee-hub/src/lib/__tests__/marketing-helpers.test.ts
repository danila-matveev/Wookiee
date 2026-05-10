import { describe, it, expect } from 'vitest'
import { parseUnifiedId, numToNumber } from '../marketing-helpers'

describe('parseUnifiedId', () => {
  it('parses B-prefix', () => expect(parseUnifiedId('B42')).toEqual({ source: 'branded_queries', id: 42 }))
  it('parses S-prefix', () => expect(parseUnifiedId('S100')).toEqual({ source: 'substitute_articles', id: 100 }))
  it('throws on bad prefix', () => expect(() => parseUnifiedId('X1')).toThrow())
  it('throws on non-numeric', () => expect(() => parseUnifiedId('Sabc')).toThrow())
  it('throws on prefix-only input', () => expect(() => parseUnifiedId('B')).toThrow())
})

describe('numToNumber', () => {
  it('coerces string', () => expect(numToNumber('123.45')).toBe(123.45))
  it('handles null', () => expect(numToNumber(null)).toBe(0))
  it('handles undefined', () => expect(numToNumber(undefined)).toBe(0))
  it('passes number', () => expect(numToNumber(7)).toBe(7))
})
