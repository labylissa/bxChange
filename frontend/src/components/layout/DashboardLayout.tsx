import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { LicenseBanner } from '@/features/billing/LicenseBanner'
import { CommandPalette } from '@/components/ui/CommandPalette'
import { Sidebar } from './Sidebar'
import { Header } from './Header'

export function DashboardLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [cmdOpen, setCmdOpen] = useState(false)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setCmdOpen((o) => !o)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <LicenseBanner />
        <Header onMenuToggle={() => setSidebarOpen((o) => !o)} onSearchOpen={() => setCmdOpen(true)} />
        <main className="flex-1 overflow-auto p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
      <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
    </div>
  )
}
