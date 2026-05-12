import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect } from 'vitest'
import { MarketingLayout } from '../marketing-layout'

describe('MarketingLayout', () => {
  it('renders sub-sidebar with МАРКЕТИНГ heading and 2 nav items', () => {
    render(
      <MemoryRouter initialEntries={['/marketing/search-queries']}>
        <Routes>
          <Route path="/marketing" element={<MarketingLayout />}>
            <Route path="search-queries" element={<div>Search Page</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    )
    expect(screen.getByText('МАРКЕТИНГ')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Промокоды/i })).toHaveAttribute('href', '/marketing/promo-codes')
    expect(screen.getByRole('link', { name: /Поисковые запросы/i })).toHaveAttribute('href', '/marketing/search-queries')
    expect(screen.getByText('Search Page')).toBeInTheDocument()
  })

  it('sets data-section="marketing" on root element', () => {
    const { container } = render(
      <MemoryRouter><MarketingLayout /></MemoryRouter>
    )
    expect(container.querySelector('[data-section="marketing"]')).not.toBeNull()
  })
})
