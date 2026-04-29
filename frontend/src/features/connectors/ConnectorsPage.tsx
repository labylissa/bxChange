import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Plus, Plug, Wifi, Globe, Play, Pencil, Trash2 } from 'lucide-react'
import type { Connector } from '@/lib/api/connectors'
import { connectorsApi } from '@/lib/api/connectors'
import { quotaApi } from '@/lib/api/admin'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { ConnectorWizard } from './wizard/ConnectorWizard'

function statusVariant(status: string): 'green' | 'red' | 'gray' | 'yellow' {
  if (status === 'active') return 'green'
  if (status === 'error') return 'red'
  if (status === 'disabled') return 'gray'
  return 'yellow'
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60_000)
  if (m < 1) return "à l'instant"
  if (m < 60) return `il y a ${m} min`
  const h = Math.floor(m / 60)
  if (h < 24) return `il y a ${h}h`
  return `il y a ${Math.floor(h / 24)}j`
}

function ConnectorCard({ connector, onDelete }: { connector: Connector; onDelete: (id: string) => void }) {
  const navigate = useNavigate()
  const isDeleting = false

  return (
    <Card className="flex flex-col gap-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${connector.type === 'soap' ? 'bg-purple-50' : 'bg-blue-50'}`}>
            {connector.type === 'soap'
              ? <Wifi className="h-5 w-5 text-purple-600" />
              : <Globe className="h-5 w-5 text-blue-600" />
            }
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 text-sm">{connector.name}</h3>
            <p className="text-xs text-gray-400 mt-0.5">{relativeTime(connector.created_at)}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={connector.type === 'soap' ? 'blue' : 'gray'}>
            {connector.type.toUpperCase()}
          </Badge>
          <Badge variant={statusVariant(connector.status)}>
            {connector.status}
          </Badge>
        </div>
      </div>

      {(connector.base_url || connector.wsdl_url) && (
        <p className="text-xs text-gray-400 truncate font-mono">
          {connector.base_url ?? connector.wsdl_url}
        </p>
      )}

      <div className="flex items-center gap-2 pt-1 border-t border-gray-100">
        <Button
          size="sm"
          variant="secondary"
          onClick={() => navigate(`/dashboard/connectors/${connector.id}`)}
          className="flex items-center gap-1"
        >
          <Play className="h-3 w-3" /> Tester
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => navigate(`/dashboard/connectors/${connector.id}`)}
          className="flex items-center gap-1"
        >
          <Pencil className="h-3 w-3" /> Éditer
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            if (confirm(`Supprimer "${connector.name}" ?`)) onDelete(connector.id)
          }}
          loading={isDeleting}
          className="flex items-center gap-1 ml-auto text-red-500 hover:bg-red-50"
        >
          <Trash2 className="h-3 w-3" />
        </Button>
      </div>
    </Card>
  )
}

function QuotaBar({ count, limit }: { count: number; limit: number | null }) {
  if (limit === null) return null
  const pct = Math.min(100, Math.round((count / limit) * 100))
  const isWarning = pct >= 80
  const isMaxed = count >= limit

  return (
    <Card padding="sm" className={isMaxed ? 'border-red-200 bg-red-50' : isWarning ? 'border-yellow-200 bg-yellow-50' : ''}>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-medium text-gray-700">
          {count} / {limit} connecteurs utilisés
        </span>
        <span className={`text-xs font-semibold ${isMaxed ? 'text-red-600' : isWarning ? 'text-yellow-700' : 'text-gray-500'}`}>
          {pct}%
        </span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full transition-all ${isMaxed ? 'bg-red-500' : isWarning ? 'bg-yellow-500' : 'bg-brand-600'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {isMaxed && (
        <p className="text-xs text-red-600 mt-1.5">
          Quota atteint. Contactez votre administrateur pour augmenter la limite.
        </p>
      )}
    </Card>
  )
}

export function ConnectorsPage() {
  const [wizardOpen, setWizardOpen] = useState(false)
  const qc = useQueryClient()

  const { data: connectors, isLoading } = useQuery({
    queryKey: ['connectors'],
    queryFn: connectorsApi.getConnectors,
    refetchInterval: 30_000,
  })

  const { data: quota } = useQuery({
    queryKey: ['quota'],
    queryFn: quotaApi.getQuota,
    refetchInterval: 60_000,
  })

  const deleteConnector = useMutation({
    mutationFn: (id: string) => connectorsApi.deleteConnector(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['connectors'] }),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Connecteurs</h1>
        <Button
          onClick={() => setWizardOpen(true)}
          className="flex items-center gap-2"
          disabled={quota?.connector_limit !== null && quota?.connector_limit !== undefined && quota.connector_count >= quota.connector_limit}
        >
          <Plus className="h-4 w-4" /> Nouveau connecteur
        </Button>
      </div>

      {quota && <QuotaBar count={quota.connector_count} limit={quota.connector_limit} />}

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      )}

      {!isLoading && connectors?.length === 0 && (
        <div className="flex flex-col items-center justify-center py-24 text-center gap-4">
          <div className="p-4 bg-gray-100 rounded-full">
            <Plug className="h-8 w-8 text-gray-400" />
          </div>
          <div>
            <p className="font-medium text-gray-700">Aucun connecteur</p>
            <p className="text-sm text-gray-500 mt-1">Créez votre premier connecteur pour commencer.</p>
          </div>
          <Button onClick={() => setWizardOpen(true)} className="flex items-center gap-2">
            <Plus className="h-4 w-4" /> Créer un connecteur
          </Button>
        </div>
      )}

      {!isLoading && connectors && connectors.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {connectors.map((c) => (
            <ConnectorCard
              key={c.id}
              connector={c}
              onDelete={(id) => deleteConnector.mutate(id)}
            />
          ))}
        </div>
      )}

      {wizardOpen && <ConnectorWizard onClose={() => setWizardOpen(false)} />}
    </div>
  )
}
