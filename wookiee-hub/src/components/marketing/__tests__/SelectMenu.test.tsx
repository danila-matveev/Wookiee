import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import '@testing-library/jest-dom'
import { SelectMenu } from '../SelectMenu'

describe('SelectMenu', () => {
  it('opens, lists options, calls onChange', async () => {
    const handle = vi.fn()
    render(<SelectMenu value="" options={['A','B','C']} onChange={handle} />)
    await userEvent.click(screen.getByRole('button'))
    await userEvent.click(await screen.findByText('B'))
    expect(handle).toHaveBeenCalledWith('B')
  })

  it('keyboard nav: ArrowDown + Enter selects', async () => {
    const handle = vi.fn()
    render(<SelectMenu value="" options={['A','B','C']} onChange={handle} />)
    await userEvent.click(screen.getByRole('button'))
    await userEvent.keyboard('{ArrowDown}{ArrowDown}{Enter}')
    // cmdk default behavior — first ArrowDown highlights first item
    expect(handle).toHaveBeenCalled()
  })

  it('Esc closes popover', async () => {
    render(<SelectMenu value="" options={['A']} onChange={() => {}} />)
    await userEvent.click(screen.getByRole('button'))
    expect(await screen.findByText('A')).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByText('A')).not.toBeInTheDocument())
  })

  it('allowAdd inserts new value via Enter', async () => {
    const handle = vi.fn()
    render(<SelectMenu value="" options={['A']} onChange={handle} allowAdd />)
    await userEvent.click(screen.getByRole('button'))
    await userEvent.click(await screen.findByText(/Добавить новый/))
    const input = await screen.findByPlaceholderText(/Новое значение/)
    await userEvent.type(input, 'Новый канал{Enter}')
    expect(handle).toHaveBeenCalledWith('Новый канал')
  })

  it('aria-expanded toggles', async () => {
    render(<SelectMenu value="" options={['A']} onChange={() => {}} />)
    const trigger = screen.getByRole('button')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
  })
})
