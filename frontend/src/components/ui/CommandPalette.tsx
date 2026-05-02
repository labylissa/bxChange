import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search, LayoutDashboard, Plug, GitMerge, ScrollText, Key, Settings,
  Webhook, Clock, BookOpen, Shield, CreditCard, Lock, ArrowRight,
} from 'lucide-react'

interface Command {
  id: string
  label: string
  description?: string
  icon: React.ElementType
  action: () => void
  group: string
}

interface Props {
  open: boolean
  onClose: () => void
}

export function CommandPalette({ open, onClose }: Props) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const nav = (path: string) => { navigate(path); onClose() }

  const commands: Command[] = [
    { id: 'dash', label: 'Dashboard', icon: LayoutDashboard, action: () => nav('/dashboard'), group: 'Navigation' },
    { id: 'conn', label: 'Connecteurs', icon: Plug, action: () => nav('/dashboard/connectors'), group: 'Navigation' },
    { id: 'pipe', label: 'Pipelines', icon: GitMerge, action: () => nav('/dashboard/pipelines'), group: 'Navigation' },
    { id: 'logs', label: 'Logs', icon: ScrollText, action: () => nav('/dashboard/logs'), group: 'Navigation' },
    { id: 'keys', label: 'API Keys', icon: Key, action: () => nav('/dashboard/api-keys'), group: 'Navigation' },
    { id: 'sec', label: 'Sécurité', icon: Lock, action: () => nav('/dashboard/security'), group: 'Navigation' },
    { id: 'wh', label: 'Webhooks', icon: Webhook, action: () => nav('/dashboard/webhooks'), group: 'Navigation' },
    { id: 'sj', label: 'Planification', icon: Clock, action: () => nav('/dashboard/scheduled-jobs'), group: 'Navigation' },
    { id: 'docs', label: 'API Docs', icon: BookOpen, action: () => nav('/dashboard/api-docs'), group: 'Navigation' },
    { id: 'billing', label: 'Facturation', icon: CreditCard, action: () => nav('/dashboard/billing'), group: 'Navigation' },
    { id: 'settings', label: 'Paramètres', icon: Settings, action: () => nav('/dashboard/settings'), group: 'Navigation' },
    { id: 'team', label: 'Équipe', icon: Shield, action: () => nav('/dashboard/team'), group: 'Navigation' },
    { id: 'new-conn', label: 'Nouveau connecteur', description: 'Ouvrir le wizard connecteur', icon: Plug, action: () => nav('/dashboard/connectors'), group: 'Actions rapides' },
    { id: 'new-pipe', label: 'Nouveau pipeline', description: 'Créer un pipeline', icon: GitMerge, action: () => nav('/dashboard/pipelines/new'), group: 'Actions rapides' },
    { id: 'new-key', label: 'Nouvelle clé API', description: 'Générer une clé API', icon: Key, action: () => nav('/dashboard/api-keys'), group: 'Actions rapides' },
    { id: 'errors', label: 'Voir les erreurs récentes', description: 'Filtrer les logs en erreur', icon: ScrollText, action: () => nav('/dashboard/logs'), group: 'Actions rapides' },
  ]

  const filtered = query.trim()
    ? commands.filter((c) =>
        c.label.toLowerCase().includes(query.toLowerCase()) ||
        c.description?.toLowerCase().includes(query.toLowerCase())
      )
    : commands

  const groups = [...new Set(filtered.map((c) => c.group))]

  useEffect(() => {
    if (open) {
      setQuery('')
      setSelected(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  useEffect(() => {
    setSelected(0)
  }, [query])

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onClose(); return }
      if (e.key === 'ArrowDown') { e.preventDefault(); setSelected((s) => Math.min(s + 1, filtered.length - 1)) }
      if (e.key === 'ArrowUp') { e.preventDefault(); setSelected((s) => Math.max(s - 1, 0)) }
      if (e.key === 'Enter') { e.preventDefault(); filtered[selected]?.action() }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, filtered, selected, onClose])

  if (!open) return null

  let globalIndex = -1

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] px-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl border border-gray-200 w-full max-w-lg overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100">
          <Search className="h-4 w-4 text-gray-400 flex-shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Rechercher une page ou une action…"
            className="flex-1 text-sm text-gray-900 placeholder-gray-400 focus:outline-none"
          />
          <kbd className="hidden sm:flex items-center gap-1 px-1.5 py-0.5 text-xs text-gray-400 border border-gray-200 rounded">
            Esc
          </kbd>
        </div>

        <div className="max-h-80 overflow-y-auto py-2">
          {filtered.length === 0 ? (
            <p className="text-center text-sm text-gray-400 py-8">Aucun résultat pour «&nbsp;{query}&nbsp;»</p>
          ) : (
            groups.map((group) => (
              <div key={group}>
                <p className="px-4 py-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">{group}</p>
                {filtered.filter((c) => c.group === group).map((cmd) => {
                  globalIndex++
                  const idx = globalIndex
                  return (
                    <button
                      key={cmd.id}
                      onClick={cmd.action}
                      onMouseEnter={() => setSelected(idx)}
                      className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                        selected === idx ? 'bg-brand-50 text-brand-700' : 'text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      <cmd.icon className={`h-4 w-4 flex-shrink-0 ${selected === idx ? 'text-brand-600' : 'text-gray-400'}`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{cmd.label}</p>
                        {cmd.description && (
                          <p className="text-xs text-gray-400 truncate">{cmd.description}</p>
                        )}
                      </div>
                      {selected === idx && <ArrowRight className="h-3.5 w-3.5 text-brand-400 flex-shrink-0" />}
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </div>

        <div className="px-4 py-2 border-t border-gray-100 flex items-center gap-4 text-xs text-gray-400">
          <span><kbd className="font-mono">↑↓</kbd> naviguer</span>
          <span><kbd className="font-mono">↵</kbd> ouvrir</span>
          <span><kbd className="font-mono">Esc</kbd> fermer</span>
        </div>
      </div>
    </div>
  )
}
