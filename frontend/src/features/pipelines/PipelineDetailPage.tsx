import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, Play, CheckCircle, XCircle, Clock, Minus, RefreshCw, Key } from 'lucide-react'
import { pipelinesApi, type PipelineExecutionRead } from '@/lib/api/pipelines'
import { PipelineGraph } from './PipelineGraph'

// ── Helpers ───────────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60_000)
  if (m < 1) return "à l'instant"
  if (m < 60) return `il y a ${m} min`
  const h = Math.floor(m / 60)
  if (h < 24) return `il y a ${h}h`
  return `il y a ${Math.floor(h / 24)}j`
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'success') return <CheckCircle className="h-4 w-4 text-green-500" />
  if (status === 'error') return <XCircle className="h-4 w-4 text-red-500" />
  if (status === 'skipped') return <Minus className="h-4 w-4 text-gray-400" />
  return <Clock className="h-4 w-4 text-gray-400" />
}

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === 'success' ? 'bg-green-100 text-green-700'
    : status === 'error' ? 'bg-red-100 text-red-700'
    : status === 'skipped' ? 'bg-gray-100 text-gray-500'
    : 'bg-yellow-100 text-yellow-700'
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{status}</span>
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

type Tab = 'overview' | 'test' | 'history'

// ── Test tab ──────────────────────────────────────────────────────────────────

function TestTab({ pipelineId }: { pipelineId: string }) {
  const [paramsText, setParamsText] = useState('{}')
  const [apiKey, setApiKey] = useState('')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<null | { status: string; result: unknown; steps: Record<string, unknown>; duration_ms: number; error_message?: string | null }>(null)
  const [error, setError] = useState('')
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set())

  const handleRun = async () => {
    let params: Record<string, unknown> = {}
    try { params = JSON.parse(paramsText) } catch { setError('Params JSON invalide'); return }
    if (!apiKey) { setError('Entrez une clé API (bxc_…)'); return }

    setRunning(true)
    setError('')
    setResult(null)
    try {
      const r = await pipelinesApi.execute(pipelineId, params, apiKey)
      setResult(r)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Erreur lors de l\'exécution')
    } finally {
      setRunning(false)
    }
  }

  const toggleStep = (k: string) =>
    setExpandedSteps((prev) => {
      const next = new Set(prev)
      next.has(k) ? next.delete(k) : next.add(k)
      return next
    })

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Params (JSON)</label>
          <textarea
            rows={6}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
            value={paramsText}
            onChange={(e) => setParamsText(e.target.value)}
          />
        </div>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Clé API (bxc_…)</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="bxc_…"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
            <p className="text-xs text-gray-400 mt-1 flex items-center gap-1">
              <Key className="h-3 w-3" />
              <Link to="/dashboard/api-keys" className="underline">Gérer les clés API</Link>
            </p>
          </div>
          {error && <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}
          <button
            onClick={handleRun}
            disabled={running}
            className="flex items-center gap-2 px-5 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700 disabled:opacity-60"
          >
            <Play className="h-4 w-4" />
            {running ? 'Exécution…' : 'Exécuter'}
          </button>
        </div>
      </div>

      {result && (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <StatusIcon status={result.status} />
            <span className="font-semibold text-gray-800">Résultat</span>
            <StatusBadge status={result.status} />
            <span className="text-sm text-gray-400">{result.duration_ms} ms</span>
          </div>

          {/* Steps accordion */}
          <div className="space-y-2">
            {Object.entries(result.steps as Record<string, { status: string; result: unknown; error_message?: string | null; duration_ms: number; connector_id: string }>)
              .sort(([a], [b]) => Number(a) - Number(b))
              .map(([order, stepRes]) => {
                const key = `step-${order}`
                return (
                  <div key={key} className="border border-gray-200 rounded-lg overflow-hidden">
                    <button
                      onClick={() => toggleStep(key)}
                      className="w-full flex items-center gap-3 px-4 py-2.5 bg-gray-50 hover:bg-gray-100 text-left"
                    >
                      <StatusIcon status={stepRes.status} />
                      <span className="text-sm font-medium text-gray-800">Step {order}</span>
                      <StatusBadge status={stepRes.status} />
                      <span className="text-xs text-gray-400 ml-auto">{stepRes.duration_ms} ms</span>
                    </button>
                    {expandedSteps.has(key) && (
                      <div className="px-4 py-3 border-t border-gray-100">
                        {stepRes.error_message && (
                          <p className="text-sm text-red-600 mb-2">{stepRes.error_message}</p>
                        )}
                        <pre className="text-xs text-gray-700 bg-gray-50 p-2 rounded overflow-auto max-h-40">
                          {JSON.stringify(stepRes.result, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )
              })}
          </div>

          {/* Final result */}
          <div>
            <p className="text-sm font-medium text-gray-700 mb-1">Résultat final</p>
            <pre className="text-xs text-gray-700 bg-gray-50 border border-gray-200 p-3 rounded-lg overflow-auto max-h-60">
              {JSON.stringify(result.result, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}

// ── History tab ───────────────────────────────────────────────────────────────

function HistoryTab({ pipelineId }: { pipelineId: string }) {
  const { data: executions = [], isLoading, refetch } = useQuery({
    queryKey: ['pipeline-executions', pipelineId],
    queryFn: () => pipelinesApi.listExecutions(pipelineId),
  })
  const [expandedId, setExpandedId] = useState<string | null>(null)

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <button onClick={() => refetch()} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
          <RefreshCw className="h-3.5 w-3.5" /> Rafraîchir
        </button>
      </div>
      {isLoading ? (
        <div className="text-center py-8 text-gray-400">Chargement…</div>
      ) : executions.length === 0 ? (
        <div className="text-center py-12 text-gray-400">Aucune exécution</div>
      ) : (
        <div className="space-y-2">
          {executions.map((e: PipelineExecutionRead) => (
            <div key={e.id} className="border border-gray-200 rounded-lg overflow-hidden">
              <button
                onClick={() => setExpandedId((prev) => (prev === e.id ? null : e.id))}
                className="w-full flex items-center gap-3 px-4 py-3 bg-white hover:bg-gray-50 text-left"
              >
                <StatusIcon status={e.status} />
                <StatusBadge status={e.status} />
                <span className="text-xs text-gray-500">{relativeTime(e.created_at)}</span>
                <span className="text-xs text-gray-400">{e.duration_ms} ms</span>
                <span className="text-xs text-gray-400 ml-auto">{e.triggered_by}</span>
              </button>
              {expandedId === e.id && (
                <div className="px-4 py-3 border-t border-gray-100 space-y-3">
                  {e.error_message && (
                    <p className="text-sm text-red-600">Erreur étape {e.error_step}: {e.error_message}</p>
                  )}
                  <div>
                    <p className="text-xs font-semibold text-gray-500 mb-1">Détail par step</p>
                    <div className="space-y-1">
                      {Object.entries(e.steps_detail)
                        .sort(([a], [b]) => Number(a) - Number(b))
                        .map(([order, sd]) => (
                          <div key={order} className="flex items-center gap-2 text-xs">
                            <StatusIcon status={sd.status} />
                            <span className="text-gray-600">Step {order}</span>
                            <StatusBadge status={sd.status} />
                            <span className="text-gray-400">{sd.duration_ms} ms</span>
                            {sd.error_message && <span className="text-red-500 truncate">{sd.error_message}</span>}
                          </div>
                        ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-gray-500 mb-1">Résultat</p>
                    <pre className="text-xs text-gray-700 bg-gray-50 p-2 rounded overflow-auto max-h-32">
                      {JSON.stringify(e.result, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function PipelineDetailPage() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>('overview')

  const { data: pipeline, isLoading } = useQuery({
    queryKey: ['pipeline', id],
    queryFn: () => pipelinesApi.get(id!),
    enabled: !!id,
  })

  const handleToggleActive = async () => {
    if (!pipeline) return
    await pipelinesApi.update(pipeline.id, { is_active: !pipeline.is_active })
    qc.invalidateQueries({ queryKey: ['pipeline', id] })
    qc.invalidateQueries({ queryKey: ['pipelines'] })
  }

  if (isLoading) return <div className="text-center py-16 text-gray-400">Chargement…</div>
  if (!pipeline) return <div className="text-center py-16 text-red-500">Pipeline introuvable</div>

  const TABS: { id: Tab; label: string }[] = [
    { id: 'overview', label: 'Vue générale' },
    { id: 'test', label: 'Tester' },
    { id: 'history', label: 'Historique' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Link to="/dashboard/pipelines" className="mt-1 text-gray-400 hover:text-gray-600">
          <ChevronLeft className="h-5 w-5" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">{pipeline.name}</h1>
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${pipeline.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
              {pipeline.is_active ? 'Actif' : 'Inactif'}
            </span>
          </div>
          {pipeline.description && <p className="text-sm text-gray-500 mt-1">{pipeline.description}</p>}
          <p className="text-xs text-gray-400 mt-1">
            {pipeline.steps.length} step{pipeline.steps.length > 1 ? 's' : ''} · fusion: {pipeline.merge_strategy} · {pipeline.executions_count} exécution{pipeline.executions_count !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={handleToggleActive}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 text-gray-600"
        >
          {pipeline.is_active ? 'Désactiver' : 'Activer'}
        </button>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-0">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${tab === t.id ? 'border-brand-600 text-brand-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      <div>
        {tab === 'overview' && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl border border-gray-200 p-6 overflow-x-auto">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">Schéma du pipeline</h2>
              <PipelineGraph
                steps={pipeline.steps}
                mergeStrategy={pipeline.merge_strategy}
                hasOutputTransform={!!pipeline.output_transform}
              />
              {/* Legend */}
              <div className="mt-4 flex items-center gap-4 justify-center text-xs text-gray-500">
                <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-blue-500 inline-block" /> SOAP</span>
                <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-emerald-500 inline-block" /> REST</span>
              </div>
            </div>

            {/* Steps detail */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-200">
                <h2 className="text-sm font-semibold text-gray-700">Étapes</h2>
              </div>
              <div className="divide-y divide-gray-100">
                {[...pipeline.steps].sort((a, b) => a.step_order - b.step_order).map((s) => (
                  <div key={s.id} className="px-4 py-3 flex items-center gap-3">
                    <span className="w-6 h-6 rounded-full bg-brand-100 text-brand-700 text-xs font-bold flex items-center justify-center flex-shrink-0">{s.step_order}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900">{s.name}</p>
                      <p className="text-xs text-gray-400">{s.connector_name} · {s.connector_type}</p>
                    </div>
                    <span className={`px-1.5 py-0.5 rounded text-xs ${s.execution_mode === 'parallel' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'}`}>
                      {s.execution_mode}
                    </span>
                    <span className={`px-1.5 py-0.5 rounded text-xs ${s.on_error === 'stop' ? 'bg-red-50 text-red-700' : s.on_error === 'skip' ? 'bg-yellow-50 text-yellow-700' : 'bg-gray-100 text-gray-600'}`}>
                      on_error: {s.on_error}
                    </span>
                    <span className="text-xs text-gray-400">{s.timeout_seconds}s</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === 'test' && <TestTab pipelineId={id!} />}
        {tab === 'history' && <HistoryTab pipelineId={id!} />}
      </div>
    </div>
  )
}
