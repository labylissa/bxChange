import { Activity, Plug, CheckCircle, Clock } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'

const metrics = [
  {
    label: 'Exécutions (30j)',
    value: '1 248',
    delta: '+12%',
    icon: Activity,
    color: 'text-blue-500',
    bg: 'bg-blue-50',
  },
  {
    label: 'Connecteurs actifs',
    value: '7',
    delta: null,
    icon: Plug,
    color: 'text-green-500',
    bg: 'bg-green-50',
  },
  {
    label: 'Taux de succès',
    value: '98.4%',
    delta: '+0.3%',
    icon: CheckCircle,
    color: 'text-emerald-500',
    bg: 'bg-emerald-50',
  },
  {
    label: 'Latence p95',
    value: '342 ms',
    delta: '-18 ms',
    icon: Clock,
    color: 'text-purple-500',
    bg: 'bg-purple-50',
  },
]

const recentExecutions = [
  { id: '1', connector: 'SOAP Finances', status: 'success', duration: 210, time: 'il y a 2 min' },
  { id: '2', connector: 'REST CRM', status: 'success', duration: 89, time: 'il y a 5 min' },
  { id: '3', connector: 'SOAP Legacy HR', status: 'error', duration: 5001, time: 'il y a 12 min' },
  { id: '4', connector: 'REST Facturation', status: 'success', duration: 134, time: 'il y a 18 min' },
  { id: '5', connector: 'SOAP Stock', status: 'success', duration: 312, time: 'il y a 25 min' },
]

function statusVariant(status: string): 'green' | 'red' {
  return status === 'success' ? 'green' : 'red'
}

export function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold text-gray-900">Dashboard</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {metrics.map(({ label, value, delta, icon: Icon, color, bg }) => (
          <Card key={label} className="flex items-start gap-4">
            <div className={`p-2 rounded-lg ${bg}`}>
              <Icon className={`h-5 w-5 ${color}`} />
            </div>
            <div>
              <p className="text-sm text-gray-500">{label}</p>
              <p className="text-2xl font-bold text-gray-900 mt-0.5">{value}</p>
              {delta && (
                <p className={`text-xs mt-1 ${delta.startsWith('+') ? 'text-green-600' : 'text-blue-600'}`}>
                  {delta} ce mois
                </p>
              )}
            </div>
          </Card>
        ))}
      </div>

      <Card padding="none">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-700">Exécutions récentes</h2>
        </div>
        <div className="divide-y divide-gray-50">
          {recentExecutions.map((exec) => (
            <div key={exec.id} className="flex items-center justify-between px-6 py-3">
              <div>
                <p className="text-sm font-medium text-gray-800">{exec.connector}</p>
                <p className="text-xs text-gray-400 mt-0.5">{exec.time}</p>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-xs text-gray-500">{exec.duration} ms</span>
                <Badge variant={statusVariant(exec.status)}>
                  {exec.status}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
