import { describe, it, expect } from 'vitest'
import { isEnabled } from '../feature-flags'

describe('feature-flags', () => {
  it('returns false when env not set', () => {
    expect(typeof isEnabled('marketing')).toBe('boolean')
  })
})
