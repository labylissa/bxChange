import { useLocation, useNavigate } from 'react-router-dom'
import { LogOut, User, ChevronRight, Menu } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { Button } from '@/components/ui/Button'

const PATH_LABELS: Record<string, string> = {
  dashboard: 'Dashboard',
  connectors: 'Connecteurs',
  logs: 'Logs',
  'api-keys': 'API Keys',
  settings: 'Paramètres',
}

function Breadcrumb() {
  const location = useLocation()
  const segments = location.pathname.split('/').filter(Boolean)

  return (
    <nav className="flex items-center gap-1 text-sm text-gray-600" aria-label="Breadcrumb">
      {segments.map((seg, i) => {
        const label = PATH_LABELS[seg] ?? seg
        const isLast = i === segments.length - 1
        return (
          <span key={i} className="flex items-center gap-1">
            {i > 0 && <ChevronRight className="h-3 w-3 text-gray-400 flex-shrink-0" />}
            <span className={isLast ? 'font-medium text-gray-900' : 'text-gray-500'}>
              {label}
            </span>
          </span>
        )
      })}
    </nav>
  )
}

interface HeaderProps {
  onMenuToggle: () => void
}

export function Header({ onMenuToggle }: HeaderProps) {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-4 gap-4 flex-shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onMenuToggle}
          className="md:hidden text-gray-500 hover:text-gray-700 flex-shrink-0"
          aria-label="Ouvrir le menu"
        >
          <Menu className="h-5 w-5" />
        </button>
        <Breadcrumb />
      </div>

      <div className="flex items-center gap-3 flex-shrink-0">
        <div className="hidden sm:flex items-center gap-2 text-sm text-gray-700">
          <User className="h-4 w-4 text-gray-400" />
          <span className="truncate max-w-[140px]">{user?.full_name ?? user?.email}</span>
        </div>
        <Button variant="ghost" size="sm" onClick={handleLogout} className="flex items-center gap-1">
          <LogOut className="h-4 w-4" />
          <span className="hidden sm:inline">Déconnexion</span>
        </Button>
      </div>
    </header>
  )
}
