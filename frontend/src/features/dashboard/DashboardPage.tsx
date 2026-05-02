import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Activity, Plug, CheckCircle, Clock, RefreshCw, TrendingUp, ArrowRight } from 'lucide-react'
import type { RecentExecution } from '@/lib/api/executions'
import { logsApi } from '@/lib/api/executions'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Spinner'

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60_000)
  if (m < 1) return "à l'instant"
  if (m < 60) return `il y a ${m} min`
  const h = Math.floor(m / 60)
  if (h < 24) return `il y a ${h}h`
  return `il y a ${Math.floor(h / 24)}j`
}

function statusVariant(status: string): 'green' | 'red' | 'yellow' {
  if (status === 'success') return 'green'
  if (status === 'error' || status === 'timeout') return 'red'
  return 'yellow'
}

function RecentTable({ rows }: { rows: RecentExecution[] }) {
  const navigate = useNavigate()
  return (
    <Card padding="none">
      <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700">Exécutions récentes</h2>
        <button onClick={() => navigate('/dashboard/logs')} className="text-xs text-brand-600 hover:underline flex items-center gap-1">
          Voir tout <ArrowRight className="h-3 w-3" />
        </button>
      </div>
      {rows.length === 0 && (
        <p className="text-sm text-gray-500 px-6 py-8 text-center">Aucune exécution pour le moment.</p>
      )}
      <div className="divide-y divide-gray-50">
        {rows.slice(0, 10).map((exec) => (
          <div
            key={exec.id}
            onClick={() => navigate('/dashboard/logs')}
            className="flex items-center justify-between px-6 py-3 hover:bg-gray-50 cursor-pointer transition-colors"
          >
            <div>
              <p className="text-sm font-medium text-gray-800">{exec.connector_name}</p>
              <p className="text-xs text-gray-400 mt-0.5">{relativeTime(exec.created_at)}</p>
            </div>
            <div className="flex items-center gap-4">
              {exec.duration_ms != null && (
                <span className="text-xs text-gray-500">{exec.duration_ms} ms</span>
              )}
              <Badge variant={statusVariant(exec.status)}>{exec.status}</Badge>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

function TopConnectors({ data }: { data: Array<{ connector_id: string; name: string; count: number; error_rate: number }> }) {
  if (!data.length) return null
  const max = data[0].count
  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-brand-500" />
          Top connecteurs (24h)
        </h2>
      </div>
      <div className="flex flex-col gap-3">
        {data.slice(0, 5).map((item) => {
          const pct = max > 0 ? Math.round((item.count / max) * 100) : 0
          return (
            <div key={item.connector_id}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm text-gray-700 truncate max-w-[70%]">{item.name}</span>
                <span className="text-xs font-semibold text-gray-500">{item.count.toLocaleString('fr-FR')} appels</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-1.5">
                <div className="h-1.5 rounded-full bg-brand-500 transition-all" style={{ width: `${pct}%` }} />
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}

export function DashboardPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date())

  const { data: metrics, isLoading: loadingMetrics } = useQuery({
    queryKey: ['metrics', '24h'],
    queryFn: () => logsApi.getMetrics('24h'),
    refetchInterval: 60_000,
  })

  const { data: recent, isLoading: loadingRecent } = useQuery({
    queryKey: ['recent-executions'],
    queryFn: logsApi.getRecent,
    refetchInterval: 30_000,
  })

  async function handleRefresh() {
    setIsRefreshing(true)
    await Promise.all([
      qc.invalidateQueries({ queryKey: ['metrics'] }),
      qc.invalidateQueries({ queryKey: ['recent-executions'] }),
    ])
    setLastRefreshed(new Date())
    setIsRefreshing(false)
  }

  const cards = metrics
    ? [
        {
          label: 'Appels (24h)',
          value: metrics.total_calls.toLocaleString('fr-FR'),
          sub: `${metrics.success_count} succès · ${metrics.error_count} erreurs`,
          icon: Activity,
          color: 'text-blue-500',
          bg: 'bg-blue-50',
          onClick: () => navigate('/dashboard/logs'),
        },
        {
          label: 'Connecteurs actifs',
          value: metrics.calls_by_connector.length.toString(),
          sub: 'avec exécutions 24h',
          icon: Plug,
          color: 'text-green-500',
          bg: 'bg-green-50',
          onClick: () => navigate('/dashboard/connectors'),
        },
        {
          label: 'Taux de succès',
          value: `${metrics.success_rate}%`,
          sub: 'sur 24 heures',
          icon: CheckCircle,
          color: 'text-emerald-500',
          bg: 'bg-emerald-50',
          onClick: () => navigate('/dashboard/logs'),
        },
        {
          label: 'Latence p95',
          value: `${Math.round(metrics.p95_duration_ms)} ms`,
          sub: `moy ${Math.round(metrics.avg_duration_ms)} ms`,
          icon: Clock,
          color: 'text-purple-500',
          bg: 'bg-purple-50',
          onClick: () => navigate('/dashboard/logs'),
        },
      ]
    : []

  const topConnectors = metrics?.calls_by_connector ?? [] as Array<{ connector_id: string; name: string; count: number; error_rate: number }>

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Dashboard</h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400 hidden sm:block">
            Mis à jour {relativeTime(lastRefreshed.toISOString())}
          </span>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            Actualiser
          </button>
        </div>
      </div>

      {loadingMetrics ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {cards.map(({ label, value, sub, icon: Icon, color, bg, onClick }) => (
            <button
              key={label}
              onClick={onClick}
              className="text-left w-full"
            >
              <Card className="flex items-start gap-4 hover:shadow-md hover:border-brand-200 transition-all cursor-pointer group">
                <div className={`p-2 rounded-lg ${bg} group-hover:scale-110 transition-transform`}>
                  <Icon className={`h-5 w-5 ${color}`} />
                </div>
                <div>
                  <p className="text-sm text-gray-500">{label}</p>
                  <p className="text-2xl font-bold text-gray-900 mt-0.5">{value}</p>
                  <p className="text-xs text-gray-400 mt-1">{sub}</p>
                </div>
              </Card>
            </button>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2">
          {loadingRecent ? (
            <div className="flex justify-center py-4"><Spinner /></div>
          ) : (
            <RecentTable rows={recent ?? []} />
          )}
        </div>
        <div>
          {!loadingMetrics && topConnectors.length > 0 && (
            <TopConnectors data={topConnectors} />
          )}
        </div>
      </div>
    </div>
  )
}
