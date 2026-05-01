import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Play, Plus, Trash2, Webhook } from 'lucide-react'
import { webhooksApi } from '@/lib/api/webhooks'
import type { WebhookEndpoint } from '@/lib/api/webhooks'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
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
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

interface WebhookRowProps {
  webhook: WebhookEndpoint
  connectorId?: string
  showConnector?: boolean
  onEdit: (wh: WebhookEndpoint) => void
}

function WebhookRow({ webhook, connectorId, onEdit }: WebhookRowProps) {
  const qc = useQueryClient()
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
    },
  })

  const del = useMutation({
    mutationFn: () => webhooksApi.delete(webhook.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  })

  return (
    <tr className="hover:bg-gray-50 transition-colors">
      <td className="px-4 py-3">
        <button
          onClick={() => onEdit(webhook)}
          className="text-sm font-medium text-gray-900 hover:text-brand-600 text-left"
        >
          {webhook.name}
        </button>
      </td>
      <td className="px-4 py-3 max-w-xs">
        <span className="text-xs font-mono text-gray-500 truncate block" title={webhook.url}>
          {webhook.url}
        </span>
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-1">
          {webhook.events.map((ev) => (
            <span
              key={ev}
              className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-brand-50 text-brand-700 border border-brand-100"
            >
              {EVENT_LABELS[ev] ?? ev}
            </span>
          ))}
        </div>
      </td>
      <td className="px-4 py-3">
        <button
          onClick={() => toggle.mutate()}
          disabled={toggle.isPending}
          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none ${webhook.is_active ? 'bg-brand-600' : 'bg-gray-200'}`}
          aria-label="Toggle"
        >
          <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${webhook.is_active ? 'translate-x-4' : 'translate-x-1'}`} />
        </button>
      </td>
      <td className="px-4 py-3 text-xs text-gray-500">{formatDateTime(webhook.last_triggered_at)}</td>
      <td className="px-4 py-3">
        {webhook.last_status_code !== null ? (
          <Badge variant={statusBadgeVariant(webhook.last_status_code)}>
            {webhook.last_status_code}
          </Badge>
        ) : (
          <span className="text-xs text-gray-400">—</span>
        )}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => test.mutate()}
            disabled={test.isPending}
            title="Tester"
            className="text-gray-400 hover:text-brand-600 disabled:opacity-50"
          >
            <Play className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => { if (confirm(`Supprimer "${webhook.name}" ?`)) del.mutate() }}
            className="text-gray-400 hover:text-red-500"
            title="Supprimer"
          >
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

interface Props {
  connectorId?: string
}

export function WebhooksPage({ connectorId }: Props) {
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<WebhookEndpoint | null>(null)

  const { data: webhooks, isLoading } = useQuery({
    queryKey: ['webhooks', connectorId],
    queryFn: () => webhooksApi.list(connectorId),
  })

  if (isLoading) return <div className="flex justify-center py-8"><Spinner /></div>

  const openCreate = () => { setEditing(null); setFormOpen(true) }
  const openEdit = (wh: WebhookEndpoint) => { setEditing(wh); setFormOpen(true) }
  const closeForm = () => { setFormOpen(false); setEditing(null) }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Webhook className="h-4 w-4 text-gray-500" />
          <h2 className="text-sm font-semibold text-gray-900">Webhooks</h2>
          {webhooks && (
            <span className="text-xs text-gray-400">({webhooks.length})</span>
          )}
        </div>
        <Button size="sm" onClick={openCreate} className="flex items-center gap-1.5">
          <Plus className="h-3.5 w-3.5" /> Nouveau webhook
        </Button>
      </div>

      {formOpen && (
        <Card>
          <WebhookForm
            connectorId={connectorId ?? ''}
            webhook={editing ?? undefined}
            onDone={closeForm}
            onCancel={closeForm}
          />
        </Card>
      )}

      {!webhooks?.length && !formOpen ? (
        <Card>
          <p className="text-sm text-gray-500 text-center py-4">
            Aucun webhook configuré. Créez-en un pour recevoir des notifications après chaque exécution.
          </p>
        </Card>
      ) : webhooks?.length ? (
        <Card padding="none">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  {['Nom', 'URL', 'Événements', 'Actif', 'Dernier déclenchement', 'Code HTTP', ''].map((h) => (
                    <th key={h} className="px-4 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wide">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {webhooks.map((wh) => (
                  <WebhookRow
                    key={wh.id}
                    webhook={wh}
                    connectorId={connectorId}
                    onEdit={openEdit}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}
    </div>
  )
}
