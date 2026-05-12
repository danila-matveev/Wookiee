import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import '@testing-library/jest-dom'
import type { SearchQueryRow, SearchQueryWeeklyStat } from '@/types/marketing'

// --- Mocks ---------------------------------------------------------------

const mutateMock = vi.fn((_input: unknown) => undefined)
let weeklyFixture: SearchQueryWeeklyStat[] = []

vi.mock('@/hooks/marketing/use-search-queries', () => ({
  useSearchQueries: () => ({ data: ROWS_FIXTURE, isLoading: false }),
  useSearchQueryWeekly: () => ({ data: weeklyFixture, isLoading: false, error: null }),
  useUpdateSearchQueryStatus: () => ({
    mutate: mutateMock,
    isPending: false,
    isError: false,
  }),
}))

const ROWS_FIXTURE: SearchQueryRow[] = [
  {
    unified_id: 'S101',
    source_id: 101,
    source_table: 'substitute_articles',
    group_kind: 'external',
    query_text: 'WW123',
    artikul_id: 555,
    nomenklatura_wb: '11111111',
    ww_code: 'WW123',
    campaign_name: null,
    purpose: 'bloggers',
    model_hint: 'wendy',
    creator_ref: null,
    status: 'archived', // DB shape — UI must render as 'archive'
    created_at: '2026-05-01T00:00:00Z',
    updated_at: '2026-05-01T00:00:00Z',
  },
]

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

// Import AFTER vi.mock so module-init sees the mocks.
import { SearchQueryDetailPanel } from '../SearchQueryDetailPanel'

describe('SearchQueryDetailPanel — status editor wiring', () => {
  beforeEach(() => {
    mutateMock.mockClear()
    weeklyFixture = []
  })

  it('renders DB status (archived) as UI label (Архив)', () => {
    render(
      <SearchQueryDetailPanel
        unifiedId="S101"
        dateFrom="2026-04-01"
        dateTo="2026-05-12"
        onClose={() => {}}
        mode="inline"
      />,
      { wrapper },
    )
    // STATUS_LABELS.archive === 'Архив'
    expect(screen.getByText('Архив')).toBeInTheDocument()
  })

  it('clicking status dropdown and selecting "Используется" fires mutation with StatusUI value', async () => {
    const user = userEvent.setup()
    render(
      <SearchQueryDetailPanel
        unifiedId="S101"
        dateFrom="2026-04-01"
        dateTo="2026-05-12"
        onClose={() => {}}
        mode="inline"
      />,
      { wrapper },
    )

    // Open dropdown by clicking the trigger (the visible "Архив" badge button)
    await user.click(screen.getByText('Архив'))

    // Click the "Используется" option in dropdown
    const activeOption = await screen.findByText('Используется')
    await user.click(activeOption)

    await waitFor(() => expect(mutateMock).toHaveBeenCalledTimes(1))
    const payload = mutateMock.mock.calls[0][0] as Record<string, unknown>
    // Hook contract: { unifiedId, status: StatusUI }
    expect(payload).toMatchObject({
      unifiedId: 'S101',
      status: 'active',
    })
  })
})

describe('SearchQueryDetailPanel — funnel block', () => {
  beforeEach(() => {
    mutateMock.mockClear()
    weeklyFixture = []
  })

  it('renders all 7 funnel rows with values and CRs from weekly stats in range', () => {
    weeklyFixture = [
      {
        search_query_id: 101,
        week_start: '2026-04-21',
        frequency: 10_000,
        transitions: 1_000,
        additions: 200,
        orders: 50,
      },
    ]

    render(
      <SearchQueryDetailPanel
        unifiedId="S101"
        dateFrom="2026-04-01"
        dateTo="2026-05-12"
        onClose={() => {}}
        mode="inline"
      />,
      { wrapper },
    )

    const funnel = screen.getByTestId('funnel-block')
    expect(funnel).toBeInTheDocument()
    const f = within(funnel)

    // 4 main numeric rows
    expect(f.getByText('Частота')).toBeInTheDocument()
    expect(f.getByText('10 000')).toBeInTheDocument()
    expect(f.getByText('Переходы')).toBeInTheDocument()
    expect(f.getByText('1 000')).toBeInTheDocument()
    expect(f.getByText('Корзина')).toBeInTheDocument()
    expect(f.getByText('200')).toBeInTheDocument()
    expect(f.getByText('Заказы')).toBeInTheDocument()
    expect(f.getByText('50')).toBeInTheDocument()

    // 2 intermediate CR sub-rows (indented)
    expect(f.getByText('CR перех → корзина')).toBeInTheDocument()
    expect(f.getByText('20.0%')).toBeInTheDocument() // 200/1000
    expect(f.getByText('CR корзина → заказ')).toBeInTheDocument()
    expect(f.getByText('25.0%')).toBeInTheDocument() // 50/200

    // Final CR row (divider-bordered)
    expect(f.getByText('CR перех → заказ')).toBeInTheDocument()
    expect(f.getByText('5.0%')).toBeInTheDocument() // 50/1000
  })

  it('renders all 7 row labels with zero values and "—" CRs when stats are empty', () => {
    weeklyFixture = []

    render(
      <SearchQueryDetailPanel
        unifiedId="S101"
        dateFrom="2026-04-01"
        dateTo="2026-05-12"
        onClose={() => {}}
        mode="inline"
      />,
      { wrapper },
    )

    const funnel = screen.getByTestId('funnel-block')
    const f = within(funnel)

    // All 7 row labels present
    expect(f.getByText('Частота')).toBeInTheDocument()
    expect(f.getByText('Переходы')).toBeInTheDocument()
    expect(f.getByText('CR перех → корзина')).toBeInTheDocument()
    expect(f.getByText('Корзина')).toBeInTheDocument()
    expect(f.getByText('CR корзина → заказ')).toBeInTheDocument()
    expect(f.getByText('Заказы')).toBeInTheDocument()
    expect(f.getByText('CR перех → заказ')).toBeInTheDocument()

    // CRs avoid div-by-zero → render "—"
    const dashes = f.getAllByText('—')
    expect(dashes.length).toBe(3) // 3 CR rows when denominators are 0
  })
})
