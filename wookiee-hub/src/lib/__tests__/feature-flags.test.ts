import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

describe('feature-flags', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('isEnabled("marketing") returns true when VITE_FEATURE_MARKETING="true"', async () => {
    vi.stubEnv('VITE_FEATURE_MARKETING', 'true')
    const { isEnabled } = await import('../feature-flags')
    expect(isEnabled('marketing')).toBe(true)
  })

  it('isEnabled("marketing") returns false when VITE_FEATURE_MARKETING is unset', async () => {
    vi.stubEnv('VITE_FEATURE_MARKETING', '')
    const { isEnabled } = await import('../feature-flags')
    expect(isEnabled('marketing')).toBe(false)
  })

  it('isEnabled("marketing") returns false for non-"true" values like "1"', async () => {
    vi.stubEnv('VITE_FEATURE_MARKETING', '1')
    const { isEnabled } = await import('../feature-flags')
    expect(isEnabled('marketing')).toBe(false)
  })
})
