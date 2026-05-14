import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect } from 'vitest'
import { MarketingLayout } from '../marketing-layout'

describe('MarketingLayout', () => {
  it('renders Outlet content without sub-sidebar', () => {
    render(
      <MemoryRouter initialEntries={['/marketing/search-queries']}>
        <Routes>
          <Route path="/marketing" element={<MarketingLayout />}>
            <Route path="search-queries" element={<div>Search Page</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    )
    expect(screen.getByText('Search Page')).toBeInTheDocument()
    // Section sidebar removed: МАРКЕТИНГ heading and nav links should not be present
    expect(screen.queryByText('МАРКЕТИНГ')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Промокоды/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Поисковые запросы/i })).not.toBeInTheDocument()
  })

  it('sets data-section="marketing" on root element', () => {
    const { container } = render(
      <MemoryRouter><MarketingLayout /></MemoryRouter>
    )
    expect(container.querySelector('[data-section="marketing"]')).not.toBeNull()
  })
})
