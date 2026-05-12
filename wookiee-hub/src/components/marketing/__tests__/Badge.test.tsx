import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Badge } from '../Badge'

describe('Badge', () => {
  it('renders label with green color classes', () => {
    render(<Badge color="green" label="Используется" />)
    const el = screen.getByText('Используется')
    expect(el.className).toContain('bg-emerald-50')
    expect(el.className).toContain('text-emerald-700')
  })

  it('shows dot when not compact', () => {
    const { container } = render(<Badge color="blue" label="Свободен" />)
    expect(container.querySelector('.bg-blue-500')).not.toBeNull()
  })

  it('hides dot in compact mode', () => {
    const { container } = render(<Badge color="amber" label="Не идентиф." compact />)
    expect(container.querySelector('.bg-amber-500')).toBeNull()
  })

  it('falls back to gray for unknown color', () => {
    render(<Badge color={'unknown' as any} label="X" />)
    expect(screen.getByText('X').className).toContain('bg-stone-100')
  })
})
