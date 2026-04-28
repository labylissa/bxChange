import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Plug, ScrollText, Key, Settings, Zap } from 'lucide-react'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/dashboard/connectors', label: 'Connecteurs', icon: Plug },
  { to: '/dashboard/logs', label: 'Logs', icon: ScrollText },
  { to: '/dashboard/api-keys', label: 'API Keys', icon: Key },
  { to: '/dashboard/settings', label: 'Paramètres', icon: Settings },
]

export function Sidebar() {
  return (
    <aside className="w-64 min-h-screen bg-white border-r border-gray-200 flex flex-col">
      <div className="h-16 flex items-center gap-2 px-6 border-b border-gray-200">
        <Zap className="h-6 w-6 text-brand-600" />
        <span className="text-lg font-bold text-brand-700">bxChange</span>
      </div>

      <nav className="flex-1 py-4 px-3 flex flex-col gap-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/dashboard'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-brand-50 text-brand-700'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
              }`
            }
          >
            <Icon className="h-4 w-4 flex-shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
