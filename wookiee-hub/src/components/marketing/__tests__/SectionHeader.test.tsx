import { render, fireEvent, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import '@testing-library/jest-dom'
import { SectionHeader } from '../SectionHeader'

describe('SectionHeader', () => {
  it('renders label, icon, count', () => {
    render(<table><tbody><SectionHeader icon="📦" label="Артикулы" count={42} collapsed={false} onToggle={() => {}} /></tbody></table>)
    expect(screen.getByText(/Артикулы/)).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('calls onToggle on click', () => {
    const handle = vi.fn()
    render(<table><tbody><SectionHeader icon="📦" label="X" count={1} collapsed={true} onToggle={handle} /></tbody></table>)
    fireEvent.click(screen.getByRole('row'))
    expect(handle).toHaveBeenCalled()
  })
})
