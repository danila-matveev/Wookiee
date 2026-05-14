import type React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { SearchQueriesTable } from '../SearchQueriesTable'

vi.mock('@/hooks/marketing/use-search-queries', () => ({
  useSearchQueries: () => ({
    data: [{
      unified_id: 'S1', source_id: 1, source_table: 'substitute_articles',
      group_kind: 'external', query_text: '163151603', artikul_id: 1,
      nomenklatura_wb: '163151603', ww_code: null, campaign_name: null,
      purpose: 'yandex', model_hint: 'Wendy', creator_ref: null,
      status: 'active', created_at: '2026-01-01', updated_at: '2026-01-01',
    }],
    isLoading: false,
    error: null,
  }),
  useSearchQueryStats: () => ({
    // RPC v2 shape — `additions`, NOT `cart_adds`
    data: [{ unified_id: 'S1', frequency: 1000, transitions: 100, additions: 25, orders: 5 }],
    isLoading: false,
    error: null,
  }),
  useUpdateSearchQueryStatus: () => ({
    mutate: () => {},
    isError: false,
  }),
}))

vi.mock('@/hooks/marketing/use-channels', () => ({
  useChannelLabelLookup: () => (s: string) => s,
}))

vi.mock('@/hooks/marketing/use-group-by-pref', () => ({
  useGroupByPref: () => ({ value: 'none', setValue: () => {} }),
}))

vi.mock('@/components/marketing/UpdateBar', () => ({ UpdateBar: () => null }))
vi.mock('@/components/marketing/DateRange', () => ({ DateRange: () => null }))

const wrap = (ui: React.ReactNode) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MemoryRouter>
      <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('SearchQueriesTable — additions field rendering (RPC v2)', () => {
  it('renders Корз. column + tfoot total with `additions` value (25), not 0', () => {
    wrap(<SearchQueriesTable />)
    // The number 25 must appear in BOTH the row cell AND the tfoot total
    // (single row with additions=25 ⇒ row sum = 25).
    // If the frontend still reads `s.cart_adds`, undefined ⇒ both cells empty.
    const matches = screen.getAllByText('25')
    expect(matches.length).toBeGreaterThanOrEqual(2)
  })

  it('does not render 0 placeholder for the additions cell', () => {
    wrap(<SearchQueriesTable />)
    // Sanity: ensure '0' is not what got rendered for additions.
    // (We avoid a strict assertion here — '0' may legitimately appear elsewhere.)
    // Instead, assert presence of the formatted CR→корз percentage 25%.
    // 25.0% appears in both row + tfoot (same single-row dataset).
    expect(screen.getAllByText('25.0%').length).toBeGreaterThanOrEqual(1)
  })
})
