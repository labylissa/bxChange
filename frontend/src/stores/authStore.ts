import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: string
  email: string
  full_name: string
  role: string
  tenant_id: string | null
}

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  login: (accessToken: string, refreshToken: string, user: User) => void
  logout: () => void
  refreshTokens: (accessToken: string, refreshToken: string) => void
  setUser: (user: User) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      login: (accessToken, refreshToken, user) =>
        set({ accessToken, refreshToken, user, isAuthenticated: true }),
      logout: () =>
        set({ accessToken: null, refreshToken: null, user: null, isAuthenticated: false }),
      refreshTokens: (accessToken, refreshToken) =>
        set({ accessToken, refreshToken }),
      setUser: (user) => set({ user }),
    }),
    { name: 'bxchange-auth' }
  )
)

// Role selectors — use these instead of reading user.role directly
export const useIsSuperAdmin = () =>
  useAuthStore((s) => s.user?.role === 'super_admin')

export const useIsAdmin = () =>
  useAuthStore((s) => s.user?.role === 'admin' || s.user?.role === 'super_admin')

export const useIsDeveloper = () =>
  useAuthStore((s) => ['super_admin', 'admin', 'developer'].includes(s.user?.role ?? ''))

export const useIsViewer = () =>
  useAuthStore((s) => s.isAuthenticated)
