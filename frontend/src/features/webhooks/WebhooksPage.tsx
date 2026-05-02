import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Play, Plus, Trash2, Search } from 'lucide-react'
import { webhooksApi } from '@/lib/api/webhooks'
import type { WebhookEndpoint } from '@/lib/api/webhooks'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { useToast } from '@/stores/toastStore'
import { WebhookForm } from './WebhookForm'

const EVENT_LABELS: Record<string, string> = {
  'execution.success': 'Succès',
  'execution.failure': 'Échec',
  'execution.all': 'Tous',
}

function statusBadgeVariant(code: number | null): 'green' | 'red' | 'gray' {
  if (code === null) return 'gray'
  if (code >= 200 && code < 300) return 'green'
  return 'red'
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })
}

interface WebhookRowProps {
  webhook: WebhookEndpoint
  connectorId?: string
  onEdit: (wh: WebhookEndpoint) => void
  onDelete: (wh: WebhookEndpoint) => void
}

function WebhookRow({ webhook, connectorId, onEdit, onDelete }: WebhookRowProps) {
  const qc = useQueryClient()
  const toast = useToast()
  const key = ['webhooks', connectorId]

  const [testResult, setTestResult] = useState<{ ok: boolean; code: number | null } | null>(null)

  const toggle = useMutation({
    mutationFn: () => webhooksApi.toggle(webhook.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  })

  const test = useMutation({
    mutationFn: () => webhooksApi.test(webhook.id),
    onSuccess: (r) => {
      setTestResult({ ok: r.ok, code: r.status_code })
      setTimeout(() => setTestResult(null), 4000)
      toast.success(r.ok ? `Webhook testé — HTTP ${r.status_code}` : `Erreur HTTP ${r.status_code ?? 'timeout'}`)
    },
    onError: () => toast.error('Erreur lors du test'),
  })

  return (
    <tr className="hover:bg-gray-50 transition-colors">
      <td className="px-4 py-3">
        <button onClick={() => onEdit(webhook)} className="text-sm font-medium text-gray-900 hover:text-brand-600 text-left">{webhook.name}</button>
      </td>
      <td className="px-4 py-3 max-w-xs">
        <span className="text-xs font-mono text-gray-500 truncate block" title={webhook.url}>{webhook.url}</span>
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-1">
          {webhook.events.map((ev) => (
            <span key={ev} className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-brand-50 text-brand-700 border border-brand-100">
              {EVENT_LABELS[ev] ?? ev}
            </span>
          ))}
        </div>
      </td>
      <td className="px-4 py-3">
        <button onClick={() => toggle.mutate()} disabled={toggle.isPending}
          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none ${webhook.is_active ? 'bg-brand-600' : 'bg-gray-200'}`}>
          <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${webhook.is_active ? 'translate-x-4' : 'translate-x-1'}`} />
        </button>
      </td>
      <td className="px-4 py-3 text-xs text-gray-500">{formatDateTime(webhook.last_triggered_at)}</td>
      <td className="px-4 py-3">
        {webhook.last_status_code !== null
          ? <Badge variant={statusBadgeVariant(webhook.last_status_code)}>{webhook.last_status_code}</Badge>
          : <span className="text-xs text-gray-400">—</span>}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <button onClick={() => test.mutate()} disabled={test.isPending} title="Tester"
            className="text-gray-400 hover:text-brand-600 disabled:opacity-50 p-1 rounded hover:bg-brand-50">
            <Play className="h-3.5 w-3.5" />
          </button>
          <button onClick={() => onDelete(webhook)} title="Supprimer"
            className="text-gray-400 hover:text-red-500 p-1 rounded hover:bg-red-50">
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
        {testResult !== null && (
          <p className={`text-xs mt-0.5 ${testResult.ok ? 'text-green-600' : 'text-red-600'}`}>
            {testResult.ok ? `OK ${testResult.code}` : `Erreur ${testResult.code ?? 'timeout'}`}
          </p>
        )}
      </td>
    </tr>
  )
}

interface Props { connectorId?: string }

export function WebhooksPage({ connectorId }: Props) {
  const qc = useQueryClient()
  const toast = useToast()
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<WebhookEndpoint | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<WebhookEndpoint | null>(null)
  const [search, setSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState('all')

  const { data: webhooks, isLoading } = useQuery({
    queryKey: ['webhooks', connectorId],
    queryFn: () => webhooksApi.list(connectorId),
  })

  const del = useMutation({
    mutationFn: () => webhooksApi.delete(deleteTarget!.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['webhooks', connectorId] }); toast.success('Webhook supprimé'); setDeleteTarget(null) },
    onError: () => toast.error('Erreur lors de la suppression'),
  })

  const filtered = (webhooks ?? []).filter((wh) => {
    const q = search.toLowerCase()
    if (q && !wh.name.toLowerCase().includes(q) && !wh.url.toLowerCase().includes(q)) return false
    if (activeFilter === 'active' && !wh.is_active) return false
    if (activeFilter === 'inactive' && wh.is_active) return false
    return true
  })

  const openCreate = () => { setEditing(null); setFormOpen(true) }
  const openEdit = (wh: WebhookEndpoint) => { setEditing(wh); setFormOpen(true) }
  const closeForm = () => { setFormOpen(false); setEditing(null) }

  if (isLoading) return <div className="flex justify-center py-8"><Spinner /></div>

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-gray-900">Webhooks</h2>
          {webhooks && <span className="text-xs text-gray-400">({webhooks.length})</span>}
        </div>
        <Button size="sm" onClick={openCreate} className="flex items-center gap-1.5">
          <Plus className="h-3.5 w-3.5" /> Nouveau webhook
        </Button>
      </div>

      {formOpen && (
        <Card>
          <WebhookForm connectorId={connectorId ?? ''} webhook={editing ?? undefined} onDone={closeForm} onCancel={closeForm} />
        </Card>
      )}

      {(webhooks?.length ?? 0) > 0 && (
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input type="text" value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Rechercher un webhook…"
              className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <select value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)}
            className="pl-3 pr-8 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
            <option value="all">Tous</option>
            <option value="active">Actifs</option>
            <option value="inactive">Inactifs</option>
          </select>
        </div>
      )}

      {!webhooks?.length && !formOpen ? (
        <Card>
          <div className="flex flex-col items-center py-12 gap-3 text-center">
            <div className="p-4 bg-gray-100 rounded-full"><Play className="h-7 w-7 text-gray-400" /></div>
            <p className="font-medium text-gray-700">Aucun webhook configuré</p>
            <p className="text-sm text-gray-500">Recevez des notifications HTTP après chaque exécution.</p>
            <Button size="sm" onClick={openCreate} className="flex items-center gap-1.5">
              <Plus className="h-3.5 w-3.5" /> Créer un webhook
            </Button>
          </div>
        </Card>
      ) : webhooks?.length ? (
        <Card padding="none">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  {['Nom', 'URL', 'Événements', 'Actif', 'Dernier déclenchement', 'Code HTTP', ''].map((h) => (
                    <th key={h} className="px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filtered.map((wh) => (
                  <WebhookRow key={wh.id} webhook={wh} connectorId={connectorId} onEdit={openEdit} onDelete={setDeleteTarget} />
                ))}
              </tbody>
            </table>
            {filtered.length === 0 && (
              <div className="text-center py-8 text-gray-500 text-sm">Aucun webhook ne correspond à votre recherche.</div>
            )}
          </div>
        </Card>
      ) : null}

      {deleteTarget && (
        <ConfirmModal
          title="Supprimer le webhook"
          message={`Supprimer "${deleteTarget.name}" ? Les notifications vers cette URL seront arrêtées.`}
          confirmLabel="Supprimer"
          danger
          loading={del.isPending}
          onConfirm={() => del.mutate()}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  )
}
