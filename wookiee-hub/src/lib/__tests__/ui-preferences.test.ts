import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock supabase before imports
vi.mock('@/lib/supabase', () => ({
  supabase: {
    from: vi.fn(),
  },
}))

import { supabase } from '@/lib/supabase'
import { getUiPref, setUiPref } from '../ui-preferences'

describe('ui-preferences', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getUiPref returns null when no record', async () => {
    ;(supabase.from as any).mockReturnValue({
      select: () => ({
        eq: () => ({
          eq: () => ({
            maybeSingle: () => Promise.resolve({ data: null, error: null }),
          }),
        }),
      }),
    })
    const v = await getUiPref<string>('test', 'k1')
    expect(v).toBe(null)
  })

  it('setUiPref upserts with onConflict', async () => {
    const upsertMock = vi.fn().mockResolvedValue({ error: null })
    ;(supabase.from as any).mockReturnValue({ upsert: upsertMock })
    await setUiPref('test', 'k1', 'value1')
    expect(upsertMock).toHaveBeenCalledWith(
      expect.objectContaining({ scope: 'test', key: 'k1', value: 'value1' }),
      { onConflict: 'scope,key' }
    )
  })
})
