import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Mock supabase before importing hook/api
const updateChain = {
  update: vi.fn(),
  eq: vi.fn(),
}
const fromMock = vi.fn((_table: string) => updateChain)
const schemaMock = vi.fn((_name: string) => ({ from: fromMock }))

vi.mock('@/lib/supabase', () => ({
  supabase: {
    schema: (name: string) => schemaMock(name),
  },
}))

// Import after mock
import { useUpdatePromoCode } from '../use-promo-codes'

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('useUpdatePromoCode', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    updateChain.update.mockReturnValue(updateChain)
    updateChain.eq.mockResolvedValue({ error: null })
  })

  it('calls supabase.schema(crm).from(promo_codes).update(...).eq(id, <id>)', async () => {
    const { result } = renderHook(() => useUpdatePromoCode(), { wrapper })

    result.current.mutate({
      id: 42,
      code: 'SUMMER25',
      channel: 'instagram',
      discount_pct: 25,
      valid_from: '2026-06-01',
      valid_until: '2026-08-31',
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(schemaMock).toHaveBeenCalledWith('crm')
    expect(fromMock).toHaveBeenCalledWith('promo_codes')

    const patch = updateChain.update.mock.calls[0][0] as Record<string, unknown>
    expect(patch.code).toBe('SUMMER25')
    expect(patch.channel).toBe('instagram')
    expect(patch.discount_pct).toBe(25)
    expect(patch.valid_from).toBe('2026-06-01')
    expect(patch.valid_until).toBe('2026-08-31')
    expect(typeof patch.updated_at).toBe('string')
    // external_uuid is read-only: must NOT appear in the patch
    expect('external_uuid' in patch).toBe(false)

    expect(updateChain.eq).toHaveBeenCalledWith('id', 42)
  })

  it('omits unset fields from the patch (partial update)', async () => {
    const { result } = renderHook(() => useUpdatePromoCode(), { wrapper })

    result.current.mutate({ id: 7, discount_pct: 10 })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const patch = updateChain.update.mock.calls[0][0] as Record<string, unknown>
    expect(patch.discount_pct).toBe(10)
    expect(typeof patch.updated_at).toBe('string')
    expect('code' in patch).toBe(false)
    expect('channel' in patch).toBe(false)
    expect('valid_from' in patch).toBe(false)
    expect('valid_until' in patch).toBe(false)
    expect('external_uuid' in patch).toBe(false)
  })

  it('throws when supabase returns an error', async () => {
    updateChain.eq.mockResolvedValueOnce({ error: { message: 'permission denied' } })

    const { result } = renderHook(() => useUpdatePromoCode(), { wrapper })
    result.current.mutate({ id: 1, code: 'X' })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect((result.current.error as Error).message).toBe('permission denied')
  })

  it('invalidates the promo-codes list query on success', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const customWrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    )

    const { result } = renderHook(() => useUpdatePromoCode(), { wrapper: customWrapper })
    result.current.mutate({ id: 1, code: 'X' })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const calls = invalidateSpy.mock.calls.map((c) => c[0])
    const hit = calls.some((arg) => {
      const key = (arg as { queryKey?: unknown[] })?.queryKey
      if (!Array.isArray(key)) return false
      return key.includes('promo-codes')
    })
    expect(hit).toBe(true)
  })
})
