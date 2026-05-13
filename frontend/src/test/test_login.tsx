import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import Login from '../pages/Login'
import { sessionManager } from '../services/auth'

vi.mock('../services/auth', () => ({
  sessionManager: {
    setCredentials: vi.fn(),
    getSession: vi.fn().mockReturnValue(null),
  },
}))

describe('Login Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders login form', async () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    )

    expect(screen.getByLabelText(/管理员账号/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/密码/i)).toBeInTheDocument()
  })

  it('shows password visibility toggle', async () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    )

    const showButton = screen.getByText(/Show/i)
    expect(showButton).toBeInTheDocument()

    fireEvent.click(showButton)
    expect(screen.getByText(/Hide/i)).toBeInTheDocument()
  })

  it('navigates to home after successful login', async () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    )

    fireEvent.change(screen.getByLabelText(/管理员账号/i), {
      target: { value: 'testuser' },
    })
    fireEvent.change(screen.getByLabelText(/密码/i), {
      target: { value: 'testpass' },
    })

    const submitButton = screen.getByRole('button', { name: /Connect to Network/i })
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(sessionManager.setCredentials).toHaveBeenCalledWith('testuser', 'testpass')
    })
  })
})
