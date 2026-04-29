import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Building2, Users, Plug, AlertTriangle } from 'lucide-react'
import { adminApi } from '@/lib/api/admin'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { Button } from '@/components/ui/Button'

function StatCard({ label, value, icon: Icon, color }: {
  label: string; value: number; icon: React.ElementType; color: string
}) {
  return (
    <Card className="flex items-center gap-4">
      <div className={`p-3 rounded-xl ${color}`}>
        <Icon className="h-6 w-6 text-white" />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>
    </Card>
  )
}

export function AdminPage() {
  const navigate = useNavigate()

  const { data: tenants, isLoading } = useQuery({
    queryKey: ['admin-tenants'],
    queryFn: adminApi.getTenants,
    refetchInterval: 60_000,
  })

  if (isLoading) {
    return <div className="flex justify-center py-16"><Spinner size="lg" /></div>
  }

  const totalTenants = tenants?.length ?? 0
  const totalUsers = tenants?.reduce((s, t) => s + t.user_count, 0) ?? 0
  const totalConnectors = tenants?.reduce((s, t) => s + t.connector_count, 0) ?? 0
  const alerts = tenants?.filter((t) => t.subscription_status === 'past_due') ?? []

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Super Admin — Tableau de bord</h1>
        <Button onClick={() => navigate('/admin/tenants')} className="flex items-center gap-2">
          <Building2 className="h-4 w-4" /> Gérer les clients
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Tenants actifs" value={totalTenants} icon={Building2} color="bg-brand-600" />
        <StatCard label="Utilisateurs totaux" value={totalUsers} icon={Users} color="bg-purple-600" />
        <StatCard label="Connecteurs totaux" value={totalConnectors} icon={Plug} color="bg-blue-600" />
      </div>

      {alerts.length > 0 && (
        <Card>
          <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-yellow-500" />
            Alertes ({alerts.length})
          </h2>
          <ul className="divide-y divide-gray-100">
            {alerts.map((t) => (
              <li key={t.id} className="py-2 flex items-center justify-between">
                <span className="text-sm text-gray-700">{t.name}</span>
                <span className="text-xs text-yellow-700 bg-yellow-100 px-2 py-0.5 rounded-full">
                  past_due
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {alerts.length === 0 && (
        <Card className="flex items-center gap-3 text-green-700">
          <span className="text-lg">✓</span>
          <span className="text-sm font-medium">Tout est nominal — aucune alerte.</span>
        </Card>
      )}
    </div>
  )
}
