import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'

interface RoleGuardProps {
  /** Minimum role required: 'super_admin' | 'admin' | 'developer' | 'viewer' */
  requiredRole: 'super_admin' | 'admin' | 'developer' | 'viewer'
  /** Where to redirect when access is denied (default: /dashboard) */
  redirectTo?: string
}

const ROLE_LEVEL: Record<string, number> = {
  super_admin: 4,
  admin: 3,
  developer: 2,
  viewer: 1,
}

export function RoleGuard({ requiredRole, redirectTo = '/dashboard' }: RoleGuardProps) {
  const role = useAuthStore((s) => s.user?.role ?? '')
  const hasAccess = (ROLE_LEVEL[role] ?? 0) >= (ROLE_LEVEL[requiredRole] ?? 99)
  return hasAccess ? <Outlet /> : <Navigate to={redirectTo} replace />
}
