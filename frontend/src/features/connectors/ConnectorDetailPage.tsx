import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Pencil, Trash2, Plus, Minus } from 'lucide-react'
import { connectorsApi } from '@/lib/api/connectors'
import type { Execution } from '@/lib/api/executions'
import { executionsApi } from '@/lib/api/executions'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { Tabs } from '@/components/ui/Tabs'
import { JsonViewer } from '@/components/ui/JsonViewer'

const TABS = [
  { id: 'overview', label: 'Vue générale' },
  { id: 'test', label: 'Tester' },
  { id: 'transform', label: 'Transformer' },
  { id: 'history', label: 'Historique' },
]

function statusVariant(status: string): 'green' | 'red' | 'gray' | 'yellow' {
  if (status === 'active') return 'green'
  if (status === 'error') return 'red'
  if (status === 'disabled') return 'gray'
  return 'yellow'
}

// ── Test tab ────────────────────────────────────────────────────────────────
function TestTab({ connectorId, connectorType }: { connectorId: string; connectorType: string }) {
  const [operation, setOperation] = useState('')
  const [params, setParams] = useState<Array<{ key: string; value: string }>>([{ key: '', value: '' }])
  const [result, setResult] = useState<{ data: unknown; durationMs: number | null; status: string; errorMessage: string | null } | null>(null)

  const execute = useMutation({
    mutationFn: () => {
      const p: Record<string, unknown> = Object.fromEntries(params.filter((r) => r.key.trim()).map((r) => [r.key, r.value]))
      if (connectorType === 'soap' && operation.trim()) p['operation'] = operation.trim()
      return connectorsApi.executeConnector(connectorId, { params: p })
    },
    onSuccess: (data) => setResult({
      data: data.result,
      durationMs: data.duration_ms,
      status: data.status,
      errorMessage: data.error_message,
    }),
  })

  return (
    <div className="flex flex-col gap-5">
      <Card>
        <h3 className="text-sm font-medium text-gray-700 mb-3">Paramètres</h3>

        {connectorType === 'soap' && (
          <div className="mb-4">
            <label className="block text-xs text-gray-500 mb-1">Opération SOAP</label>
            <input
              className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="ex: GetQuote"
              value={operation}
              onChange={(e) => setOperation(e.target.value)}
            />
          </div>
        )}

        <div className="flex flex-col gap-2 mb-3">
          {params.map((row, i) => (
            <div key={i} className="flex gap-2 items-center">
              <input
                className="flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="Clé"
                value={row.key}
                onChange={(e) => {
                  const updated = [...params]; updated[i] = { ...updated[i], key: e.target.value }; setParams(updated)
                }}
              />
              <input
                className="flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="Valeur"
                value={row.value}
                onChange={(e) => {
                  const updated = [...params]; updated[i] = { ...updated[i], value: e.target.value }; setParams(updated)
                }}
              />
              <button
                onClick={() => setParams(params.filter((_, j) => j !== i))}
                className="text-gray-400 hover:text-red-500"
              >
                <Minus className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
        <button
          onClick={() => setParams([...params, { key: '', value: '' }])}
          className="text-xs text-brand-600 hover:underline flex items-center gap-1"
        >
          <Plus className="h-3 w-3" /> Ajouter un paramètre
        </button>
      </Card>

      <Button onClick={() => execute.mutate()} loading={execute.isPending} className="self-start">
        Exécuter
      </Button>

      {result && (
        <Card>
          <div className="flex items-center gap-3 mb-3">
            <Badge variant={result.status === 'success' ? 'green' : 'red'}>{result.status}</Badge>
            {result.durationMs != null && (
              <span className="text-xs text-gray-500">{result.durationMs} ms</span>
            )}
          </div>
          {result.errorMessage && (
            <div className="mb-3 rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700 font-mono">
              {result.errorMessage}
            </div>
          )}
          {result.data != null && <JsonViewer data={result.data} />}
        </Card>
      )}

      {execute.isError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          {(execute.error as Error).message}
        </div>
      )}
    </div>
  )
}

// ── Transform tab ───────────────────────────────────────────────────────────
function TransformTab({ connectorId }: { connectorId: string }) {
  const [rawXml, setRawXml] = useState('')
  const [transformConfig, setTransformConfig] = useState('{}')
  const [configError, setConfigError] = useState<string | null>(null)
  const [expandedStep, setExpandedStep] = useState<string | null>(null)

  const preview = useMutation({
    mutationFn: () => {
      let cfg: Record<string, unknown> | undefined
      try {
        cfg = JSON.parse(transformConfig)
        setConfigError(null)
      } catch {
        setConfigError('JSON invalide')
        throw new Error('JSON invalide')
      }
      return connectorsApi.previewTransform(connectorId, { raw_xml: rawXml, transform_config: cfg })
    },
  })

  return (
    <div className="flex flex-col gap-5">
      <Card>
        <h3 className="text-sm font-medium text-gray-700 mb-2">XML source</h3>
        <textarea
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-xs font-mono h-40 resize-y focus:outline-none focus:ring-2 focus:ring-brand-500"
          placeholder="<root><item>...</item></root>"
          value={rawXml}
          onChange={(e) => setRawXml(e.target.value)}
        />
      </Card>

      <Card>
        <h3 className="text-sm font-medium text-gray-700 mb-2">Transform config (JSON)</h3>
        <textarea
          className={`w-full rounded-lg border px-3 py-2 text-xs font-mono h-32 resize-y focus:outline-none focus:ring-2 focus:ring-brand-500 ${configError ? 'border-red-400' : 'border-gray-300'}`}
          value={transformConfig}
          onChange={(e) => setTransformConfig(e.target.value)}
        />
        {configError && <p className="text-xs text-red-600 mt-1">{configError}</p>}
      </Card>

      <Button onClick={() => preview.mutate()} loading={preview.isPending} className="self-start" disabled={!rawXml}>
        Prévisualiser
      </Button>

      {preview.data && (
        <div className="flex flex-col gap-3">
          <h3 className="text-sm font-semibold text-gray-700">Étapes de transformation</h3>
          {Object.entries(preview.data.steps)
            .filter(([k]) => k !== 'final')
            .map(([stepName, stepData]) => (
              <Card key={stepName} padding="sm" className="cursor-pointer" onClick={() => setExpandedStep(expandedStep === stepName ? null : stepName)}>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-700 capitalize">{stepName}</span>
                  <span className="text-xs text-gray-400">{expandedStep === stepName ? '▲' : '▼'}</span>
                </div>
                {expandedStep === stepName && (
                  <div className="mt-2">
                    <JsonViewer data={stepData} maxHeight="180px" />
                  </div>
                )}
              </Card>
            ))
          }
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Résultat final</h3>
            <JsonViewer data={preview.data.result} />
          </div>
        </div>
      )}
    </div>
  )
}

// ── History tab ─────────────────────────────────────────────────────────────
function HistoryTab({ connectorId }: { connectorId: string }) {
  const [selected, setSelected] = useState<Execution | null>(null)

  const { data: executions, isLoading } = useQuery({
    queryKey: ['executions', connectorId],
    queryFn: () => executionsApi.getExecutions({ connector_id: connectorId }),
  })

  function relTime(iso: string) {
    const diff = Date.now() - new Date(iso).getTime()
    const m = Math.floor(diff / 60_000)
    if (m < 1) return "à l'instant"
    if (m < 60) return `il y a ${m} min`
    return new Date(iso).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  }

  if (isLoading) return <div className="flex justify-center py-8"><Spinner /></div>

  return (
    <div className="flex gap-4">
      <Card padding="none" className="flex-1 min-w-0">
        {!executions?.length && (
          <p className="text-sm text-gray-500 p-4">Aucune exécution enregistrée.</p>
        )}
        <div className="divide-y divide-gray-50">
          {executions?.map((exec) => (
            <button
              key={exec.id}
              onClick={() => setSelected(exec)}
              className={`w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors ${selected?.id === exec.id ? 'bg-brand-50' : ''}`}
            >
              <div>
                <div className="flex items-center gap-2">
                  <Badge variant={exec.status === 'success' ? 'green' : 'red'} className="text-xs">
                    {exec.status}
                  </Badge>
                  {exec.http_status && <span className="text-xs text-gray-500">{exec.http_status}</span>}
                </div>
                <p className="text-xs text-gray-400 mt-1">{relTime(exec.created_at)}</p>
              </div>
              <span className="text-xs text-gray-500 ml-3">
                {exec.duration_ms != null ? `${exec.duration_ms} ms` : '—'}
              </span>
            </button>
          ))}
        </div>
      </Card>

      {selected && (
        <div className="flex flex-col gap-3 w-96 flex-shrink-0">
          <Card>
            <h4 className="text-xs font-medium text-gray-500 mb-2">Requête</h4>
            <JsonViewer data={selected.request_payload} maxHeight="180px" />
          </Card>
          <Card>
            <h4 className="text-xs font-medium text-gray-500 mb-2">Réponse</h4>
            <JsonViewer data={selected.response_payload ?? selected.error_message} maxHeight="180px" />
          </Card>
        </div>
      )}
    </div>
  )
}

// ── Overview tab ────────────────────────────────────────────────────────────
function OverviewTab({ connector }: { connector: ReturnType<typeof connectorsApi.getConnector> extends Promise<infer T> ? T : never }) {
  const wsdlValue = connector.type === 'soap'
    ? connector.wsdl_source === 'upload'
      ? { text: 'Fichier local', badge: true }
      : { text: connector.wsdl_url ?? '—', badge: false }
    : null

  const rows = [
    { label: 'Type', value: connector.type.toUpperCase(), badge: false },
    { label: 'Statut', value: connector.status, badge: false },
    { label: 'Auth', value: connector.auth_type, badge: false },
    { label: 'Base URL', value: connector.base_url ?? '—', badge: false },
    ...(wsdlValue ? [{ label: 'WSDL', value: wsdlValue.text, badge: wsdlValue.badge }] : []),
    { label: 'Créé le', value: new Date(connector.created_at).toLocaleString('fr-FR'), badge: false },
  ]
  return (
    <Card>
      <dl className="divide-y divide-gray-100">
        {rows.map(({ label, value, badge }) => (
          <div key={label} className="flex items-start py-3 gap-4">
            <dt className="w-28 text-sm text-gray-500 flex-shrink-0">{label}</dt>
            <dd className="text-sm text-gray-900 font-mono break-all">
              {badge ? (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-amber-50 text-amber-700 border border-amber-200 text-xs font-medium">
                  <span>📁</span> {value}
                </span>
              ) : value}
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}

// ── Main page ───────────────────────────────────────────────────────────────
export function ConnectorDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [activeTab, setActiveTab] = useState('overview')

  const { data: connector, isLoading } = useQuery({
    queryKey: ['connector', id],
    queryFn: () => connectorsApi.getConnector(id!),
    enabled: !!id,
  })

  const deleteConnector = useMutation({
    mutationFn: () => connectorsApi.deleteConnector(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['connectors'] })
      navigate('/dashboard/connectors')
    },
  })

  if (isLoading) return <div className="flex justify-center py-16"><Spinner size="lg" /></div>
  if (!connector) return <p className="text-sm text-gray-500">Connecteur introuvable.</p>

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/dashboard/connectors')} className="text-gray-400 hover:text-gray-600">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-gray-900">{connector.name}</h1>
              <Badge variant={connector.type === 'soap' ? 'blue' : 'gray'}>{connector.type.toUpperCase()}</Badge>
              <Badge variant={statusVariant(connector.status)}>{connector.status}</Badge>
            </div>
            <p className="text-xs text-gray-400 font-mono mt-0.5">
              {connector.base_url ?? (
                connector.wsdl_source === 'upload' ? '📁 Fichier local' : connector.wsdl_url
              )}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" className="flex items-center gap-1">
            <Pencil className="h-3 w-3" /> Éditer
          </Button>
          <Button
            variant="danger"
            size="sm"
            loading={deleteConnector.isPending}
            onClick={() => {
              if (confirm(`Supprimer "${connector.name}" ?`)) deleteConnector.mutate()
            }}
            className="flex items-center gap-1"
          >
            <Trash2 className="h-3 w-3" /> Supprimer
          </Button>
        </div>
      </div>

      <Tabs tabs={TABS} active={activeTab} onChange={setActiveTab} />

      <div className="mt-1">
        {activeTab === 'overview' && <OverviewTab connector={connector} />}
        {activeTab === 'test' && <TestTab connectorId={connector.id} connectorType={connector.type} />}
        {activeTab === 'transform' && <TransformTab connectorId={connector.id} />}
        {activeTab === 'history' && <HistoryTab connectorId={connector.id} />}
      </div>
    </div>
  )
}
