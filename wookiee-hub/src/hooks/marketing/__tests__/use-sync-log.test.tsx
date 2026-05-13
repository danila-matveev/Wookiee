import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

vi.mock('@/lib/supabase', () => ({
  supabase: { schema: () => ({ from: () => ({}) }) },
}))

import { useTriggerSync, useSyncStatus } from '../use-sync-log'

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
  return { wrapper, qc }
}

const fetchMock = vi.fn() as unknown as typeof fetch & ReturnType<typeof vi.fn>

beforeEach(() => {
  ;(fetchMock as unknown as ReturnType<typeof vi.fn>).mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useTriggerSync', () => {
  it('POSTs to /api/marketing/sync/{job} with X-API-Key and returns sync_log_id', async () => {
    ;(fetchMock as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        job_name: 'search-queries',
        status: 'running',
        sync_log_id: 42,
        started_at: '2026-05-12T10:00:00+00:00',
      }),
    } as Response)

    const { wrapper } = makeWrapper()
    const { result } = renderHook(() => useTriggerSync(), { wrapper })

    let mutationResult: unknown
    await act(async () => {
      mutationResult = await result.current.mutateAsync('search-queries')
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(String(url)).toContain('/api/marketing/sync/search-queries')
    expect((init as RequestInit).method).toBe('POST')
    const headers = (init as RequestInit).headers as Record<string, string>
    expect('X-API-Key' in headers).toBe(true)

    expect(mutationResult).toMatchObject({ sync_log_id: 42, status: 'running' })
  })

  it('throws on non-OK response', async () => {
    ;(fetchMock as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      text: async () => 'boom',
    } as Response)

    const { wrapper } = makeWrapper()
    const { result } = renderHook(() => useTriggerSync(), { wrapper })

    await expect(
      act(async () => { await result.current.mutateAsync('promocodes') }),
    ).rejects.toThrow(/500/)
  })
})

describe('useSyncStatus', () => {
  it('hits /status endpoint and returns parsed response', async () => {
    ;(fetchMock as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: 'success',
        finished_at: '2026-05-12T10:05:00+00:00',
        rows_processed: 1396,
      }),
    } as Response)

    const { wrapper } = makeWrapper()
    const { result } = renderHook(() => useSyncStatus('search-queries'), { wrapper })

    await waitFor(() => expect(result.current.data).toBeDefined())

    const [url, init] = (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(String(url)).toContain('/api/marketing/sync/search-queries/status')
    const headers = (init as RequestInit).headers as Record<string, string>
    expect('X-API-Key' in headers).toBe(true)

    expect(result.current.data?.status).toBe('success')
    expect(result.current.data?.rows_processed).toBe(1396)
  })

  it('skips fetching when enabled=false', async () => {
    const { wrapper } = makeWrapper()
    const { result } = renderHook(() => useSyncStatus('promocodes', false), { wrapper })

    // Let any microtasks run; the query should never fire.
    await act(async () => { await Promise.resolve() })
    await act(async () => { await Promise.resolve() })

    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.current.data).toBeUndefined()
  })

  it('reports failed status with error_message', async () => {
    ;(fetchMock as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: 'failed',
        finished_at: '2026-05-12T10:05:00+00:00',
        rows_processed: null,
        error_message: 'Sheets API timeout',
      }),
    } as Response)

    const { wrapper } = makeWrapper()
    const { result } = renderHook(() => useSyncStatus('promocodes'), { wrapper })

    await waitFor(() => expect(result.current.data?.status).toBe('failed'))
    expect(result.current.data?.error_message).toBe('Sheets API timeout')
  })
})
