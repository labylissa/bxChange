import { useLocation, useNavigate } from 'react-router-dom'
import { LogOut, User, ChevronRight, Menu, Search } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { Button } from '@/components/ui/Button'

const PATH_LABELS: Record<string, string> = {
  dashboard: 'Dashboard',
  connectors: 'Connecteurs',
  logs: 'Logs',
  'api-keys': 'API Keys',
  settings: 'Paramètres',
  webhooks: 'Webhooks',
  'scheduled-jobs': 'Planification',
  pipelines: 'Pipelines',
  team: 'Équipe',
  billing: 'Facturation',
  security: 'Sécurité',
  'api-docs': 'API Docs',
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
  onSearchOpen: () => void
}

export function Header({ onMenuToggle, onSearchOpen }: HeaderProps) {
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
        <button
          onClick={onSearchOpen}
          className="hidden sm:flex items-center gap-2 px-3 py-1.5 text-sm text-gray-400 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          title="Recherche rapide (Ctrl+K)"
        >
          <Search className="h-3.5 w-3.5" />
          <span className="text-xs">Rechercher…</span>
          <kbd className="text-xs bg-white border border-gray-200 rounded px-1 py-0.5 font-mono text-gray-400">⌘K</kbd>
        </button>

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
