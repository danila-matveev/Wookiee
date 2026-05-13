import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import '@testing-library/jest-dom'
import { SectionHeader } from '../SectionHeader'

describe('SectionHeader', () => {
  it('renders icon, label, count', () => {
    const onToggle = vi.fn()
    render(
      <table><tbody>
        <SectionHeader icon="🔤" label="Брендированные запросы" count={15} collapsed={false} onToggle={onToggle} />
      </tbody></table>,
    )
    expect(screen.getByText(/🔤 Брендированные запросы/)).toBeInTheDocument()
    expect(screen.getByText('15')).toBeInTheDocument()
  })

  it('calls onToggle on click', () => {
    const onToggle = vi.fn()
    render(
      <table><tbody>
        <SectionHeader icon="📦" label="X" count={1} collapsed={false} onToggle={onToggle} />
      </tbody></table>,
    )
    fireEvent.click(screen.getByText(/📦 X/))
    expect(onToggle).toHaveBeenCalled()
  })
})
