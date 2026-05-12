import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      signInWithPassword: vi.fn(),
      signInWithOtp: vi.fn(),
    },
  },
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

import { LoginPage } from '@/pages/auth/login'
import { supabase } from '@/lib/supabase'

function renderLogin() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  )
}

function switchToPasswordMode() {
  fireEvent.click(screen.getByRole('button', { name: /войти с паролем/i }))
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders email field in magic-link mode by default', () => {
    renderLogin()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/пароль/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /получить ссылку для входа/i })).toBeInTheDocument()
  })

  it('switches to password mode and reveals password field', () => {
    renderLogin()
    switchToPasswordMode()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/пароль/i)).toBeInTheDocument()
  })

  it('does not render a signup link', () => {
    renderLogin()
    expect(screen.queryByText(/зарегистрироваться/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/sign up/i)).not.toBeInTheDocument()
  })

  it('calls signInWithPassword on submit in password mode', async () => {
    vi.mocked(supabase.auth.signInWithPassword).mockResolvedValue({
      data: { user: { id: '1' }, session: {} },
      error: null,
    } as any)

    renderLogin()
    switchToPasswordMode()
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'a@b.com' } })
    fireEvent.change(screen.getByLabelText(/пароль/i), { target: { value: 'pass' } })
    fireEvent.click(screen.getByRole('button', { name: /^войти$/i }))

    await waitFor(() => {
      expect(supabase.auth.signInWithPassword).toHaveBeenCalledWith({
        email: 'a@b.com',
        password: 'pass',
      })
    })
  })

  it('shows error message on failed password login', async () => {
    vi.mocked(supabase.auth.signInWithPassword).mockResolvedValue({
      data: { user: null, session: null },
      error: { message: 'Invalid credentials' },
    } as any)

    renderLogin()
    switchToPasswordMode()
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'bad@b.com' } })
    fireEvent.change(screen.getByLabelText(/пароль/i), { target: { value: 'wrong' } })
    fireEvent.click(screen.getByRole('button', { name: /^войти$/i }))

    await waitFor(() => {
      expect(screen.getByText(/неверный логин или пароль/i)).toBeInTheDocument()
    })
  })
})
