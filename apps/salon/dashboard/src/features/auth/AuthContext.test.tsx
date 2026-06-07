import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { AuthProvider, useAuth } from './AuthContext'

vi.mock('@/shared/lib/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

import { api } from '@/shared/lib/api'

function TestConsumer() {
  const { user, isLoading } = useAuth()
  if (isLoading) return <div>loading</div>
  return <div>{user ? user.username : 'guest'}</div>
}

describe('AuthContext', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
  })

  it('loads authenticated user from /auth/me', async () => {
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          status: 'success',
          user: { username: 'admin@salao.com', role: 'org_admin', organization_id: '22222222-2222-2222-2222-222222222222' },
        })
      }
      return Promise.resolve({ status: 'success', data: [] })
    })

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByText('admin@salao.com')).toBeInTheDocument()
    })
  })

  it('sets guest when session check fails', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('Unauthorized'))

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByText('guest')).toBeInTheDocument()
    })
  })
})
