import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import '@testing-library/jest-dom'
import type { PromoCodeRow, PromoStatWeekly } from '@/types/marketing'

// --- Mocks ---------------------------------------------------------------

const mutateAsyncMock = vi.fn(async (_input: unknown) => undefined)

vi.mock('@/hooks/marketing/use-promo-codes', () => ({
  usePromoCodes: () => ({ data: PROMOS_FIXTURE, isLoading: false }),
  useUpdatePromoCode: () => ({
    mutateAsync: mutateAsyncMock,
    isPending: false,
  }),
}))

vi.mock('@/hooks/marketing/use-channels', () => ({
  useChannels: () => ({
    data: [
      { id: 1, slug: 'instagram', label: 'Instagram', is_active: true },
      { id: 2, slug: 'vk',        label: 'ВКонтакте', is_active: true },
    ],
  }),
}))

vi.mock('@/api/marketing/promo-codes', async () => {
  return {
    fetchPromoStatsForCode: vi.fn(async () => [] as PromoStatWeekly[]),
  }
})

const PROMOS_FIXTURE: PromoCodeRow[] = [
  {
    id: 42,
    code: 'SUMMER25',
    name: null,
    external_uuid: 'uuid-aaa-bbb',
    channel: 'instagram',
    discount_pct: 25,
    valid_from: '2026-06-01',
    valid_until: '2026-08-31',
    status: 'active',
    notes: null,
    created_at: '2026-05-01T00:00:00Z',
    updated_at: '2026-05-01T00:00:00Z',
  },
]

// --- Helpers -------------------------------------------------------------

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

// Import AFTER vi.mock above so module-init sees the mocks.
import { PromoDetailPanel } from '../PromoDetailPanel'

describe('PromoDetailPanel — edit mode', () => {
  beforeEach(() => {
    mutateAsyncMock.mockClear()
  })

  it('renders external_uuid as small mono-font read-only label', () => {
    render(<PromoDetailPanel promoId={42} onClose={() => {}} mode="inline" />, { wrapper })
    expect(screen.getByText(/uuid-aaa-bbb/i)).toBeInTheDocument()
  })

  it('pencil click switches fields into editable inputs', async () => {
    const user = userEvent.setup()
    render(<PromoDetailPanel promoId={42} onClose={() => {}} mode="inline" />, { wrapper })

    // before edit: no Save button
    expect(screen.queryByRole('button', { name: /сохранить/i })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /edit/i }))

    // Discount becomes a number input with current value
    const discountInput = screen.getByDisplayValue('25') as HTMLInputElement
    expect(discountInput.tagName).toBe('INPUT')
    expect(discountInput.type).toBe('number')

    // Save/Cancel buttons appear
    expect(screen.getByRole('button', { name: /сохранить/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /отмена/i })).toBeInTheDocument()
  })

  it('Save calls mutateAsync with edited shape and clears edit mode', async () => {
    const user = userEvent.setup()
    render(<PromoDetailPanel promoId={42} onClose={() => {}} mode="inline" />, { wrapper })

    await user.click(screen.getByRole('button', { name: /edit/i }))

    const discountInput = screen.getByDisplayValue('25')
    await user.clear(discountInput)
    await user.type(discountInput, '30')

    await user.click(screen.getByRole('button', { name: /сохранить/i }))

    await waitFor(() => expect(mutateAsyncMock).toHaveBeenCalledTimes(1))
    const payload = mutateAsyncMock.mock.calls[0][0] as Record<string, unknown>
    expect(payload).toMatchObject({
      id: 42,
      code: 'SUMMER25',
      channel: 'instagram',
      discount_pct: 30,
      valid_from: '2026-06-01',
      valid_until: '2026-08-31',
    })
    // external_uuid is read-only → must NOT be in the payload
    expect('external_uuid' in payload).toBe(false)

    // Edit mode cleared: Save button gone
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /сохранить/i })).not.toBeInTheDocument(),
    )
  })

  it('Cancel reverts edits without calling the mutation', async () => {
    const user = userEvent.setup()
    render(<PromoDetailPanel promoId={42} onClose={() => {}} mode="inline" />, { wrapper })

    await user.click(screen.getByRole('button', { name: /edit/i }))

    const discountInput = screen.getByDisplayValue('25')
    await user.clear(discountInput)
    await user.type(discountInput, '99')

    await user.click(screen.getByRole('button', { name: /отмена/i }))

    expect(mutateAsyncMock).not.toHaveBeenCalled()

    // Back in view mode: edit button visible, no input with '99'
    expect(screen.queryByDisplayValue('99')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument()

    // Re-entering edit should show the ORIGINAL value (25), not 99
    await user.click(screen.getByRole('button', { name: /edit/i }))
    expect(screen.getByDisplayValue('25')).toBeInTheDocument()
  })

  it('inline mode preserves header close button', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<PromoDetailPanel promoId={42} onClose={onClose} mode="inline" />, { wrapper })
    // close button is the only Закрыть-style button — find by aria-label
    const closeBtn = screen.getByRole('button', { name: /закрыть/i })
    await user.click(closeBtn)
    expect(onClose).toHaveBeenCalled()
  })
})
