import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ProtectedRoute } from './ProtectedRoute'

vi.mock('@/features/auth/AuthContext', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '@/features/auth/AuthContext'

function SecretPage() {
  return <div>secret content</div>
}

const authDefaults = {
  organizationId: undefined as string | undefined,
  organizationName: undefined as string | undefined,
  orgHeader: {} as Record<string, string>,
  organizations: [] as { id: string; name: string }[],
  setSelectedOrgId: () => {},
}

describe('ProtectedRoute', () => {
  it('redirects to login when not authenticated', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...authDefaults,
      user: null,
      isLoading: false,
      signOut: async () => {},
      session: null,
    })

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route path="/login" element={<div>login page</div>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/protected" element={<SecretPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('login page')).toBeInTheDocument()
  })

  it('renders child route when authenticated', () => {
    vi.mocked(useAuth).mockReturnValue({
      ...authDefaults,
      user: { username: 'admin', role: 'super_admin' },
      isLoading: false,
      signOut: async () => {},
      session: { user: { username: 'admin', role: 'super_admin' } },
    })

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route path="/login" element={<div>login page</div>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/protected" element={<SecretPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('secret content')).toBeInTheDocument()
  })
})
