import { useNavigate } from 'react-router-dom'
import { LogOut, User } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { Button } from '@/components/ui/Button'

export function Header() {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      <div />
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-sm text-gray-700">
          <User className="h-4 w-4 text-gray-400" />
          <span>{user?.full_name ?? user?.email}</span>
        </div>
        <Button variant="ghost" size="sm" onClick={handleLogout} className="flex items-center gap-1">
          <LogOut className="h-4 w-4" />
          Déconnexion
        </Button>
      </div>
    </header>
  )
}
