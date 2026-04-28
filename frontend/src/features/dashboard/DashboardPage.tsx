import { useQuery } from '@tanstack/react-query'
import { Activity, Plug, CheckCircle, Clock } from 'lucide-react'
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
  return (
    <Card padding="none">
      <div className="px-6 py-4 border-b border-gray-100">
        <h2 className="text-sm font-semibold text-gray-700">Exécutions récentes</h2>
      </div>
      {rows.length === 0 && (
        <p className="text-sm text-gray-500 px-6 py-4">Aucune exécution pour le moment.</p>
      )}
      <div className="divide-y divide-gray-50">
        {rows.slice(0, 10).map((exec) => (
          <div key={exec.id} className="flex items-center justify-between px-6 py-3">
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

export function DashboardPage() {
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

  const cards = metrics
    ? [
        {
          label: 'Appels (24h)',
          value: metrics.total_calls.toLocaleString('fr-FR'),
          sub: `${metrics.success_count} succès · ${metrics.error_count} erreurs`,
          icon: Activity,
          color: 'text-blue-500',
          bg: 'bg-blue-50',
        },
        {
          label: 'Connecteurs actifs',
          value: metrics.calls_by_connector.length.toString(),
          sub: 'avec exécutions 24h',
          icon: Plug,
          color: 'text-green-500',
          bg: 'bg-green-50',
        },
        {
          label: 'Taux de succès',
          value: `${metrics.success_rate}%`,
          sub: 'sur 24 heures',
          icon: CheckCircle,
          color: 'text-emerald-500',
          bg: 'bg-emerald-50',
        },
        {
          label: 'Latence p95',
          value: `${Math.round(metrics.p95_duration_ms)} ms`,
          sub: `moy ${Math.round(metrics.avg_duration_ms)} ms`,
          icon: Clock,
          color: 'text-purple-500',
          bg: 'bg-purple-50',
        },
      ]
    : []

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold text-gray-900">Dashboard</h1>

      {loadingMetrics ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {cards.map(({ label, value, sub, icon: Icon, color, bg }) => (
            <Card key={label} className="flex items-start gap-4">
              <div className={`p-2 rounded-lg ${bg}`}>
                <Icon className={`h-5 w-5 ${color}`} />
              </div>
              <div>
                <p className="text-sm text-gray-500">{label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-0.5">{value}</p>
                <p className="text-xs text-gray-400 mt-1">{sub}</p>
              </div>
            </Card>
          ))}
        </div>
      )}

      {loadingRecent ? (
        <div className="flex justify-center py-4"><Spinner /></div>
      ) : (
        <RecentTable rows={recent ?? []} />
      )}
    </div>
  )
}
