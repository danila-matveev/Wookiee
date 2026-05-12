import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

vi.mock('@/lib/ui-preferences', () => ({
  getUiPref: vi.fn(),
  setUiPref: vi.fn().mockResolvedValue(undefined),
}))

import { getUiPref, setUiPref } from '@/lib/ui-preferences'
import { useGroupByPref } from '../use-group-by-pref'

describe('useGroupByPref', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('loads preference on mount and sets state', async () => {
    ;(getUiPref as any).mockResolvedValue('entity_type')
    const { result } = renderHook(() => useGroupByPref<'direction' | 'entity_type' | 'none'>('marketing.search-queries', 'direction'))
    await waitFor(() => expect(result.current.value).toBe('entity_type'))
  })

  it('falls back to default when no pref', async () => {
    ;(getUiPref as any).mockResolvedValue(null)
    const { result } = renderHook(() => useGroupByPref<'direction' | 'entity_type' | 'none'>('marketing.search-queries', 'direction'))
    await waitFor(() => expect(result.current.value).toBe('direction'))
  })

  it('persists on change', async () => {
    ;(getUiPref as any).mockResolvedValue('direction')
    const { result } = renderHook(() => useGroupByPref<'direction' | 'entity_type' | 'none'>('marketing.search-queries', 'direction'))
    await waitFor(() => expect(result.current.value).toBe('direction'))
    result.current.setValue('none')
    await waitFor(() =>
      expect(setUiPref).toHaveBeenCalledWith('marketing.search-queries', 'groupBy', 'none')
    )
  })
})
