import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Plus, ChevronRight, Search, Building2, Users, Plug, RefreshCw } from 'lucide-react'
import type { TenantCreate, TenantStats } from '@/lib/api/admin'
import { adminApi } from '@/lib/api/admin'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { useToast } from '@/stores/toastStore'
import { ConfirmModal } from '@/components/ui/ConfirmModal'

function planVariant(plan: string | null): 'blue' | 'green' | 'gray' {
  if (plan === 'enterprise') return 'blue'
  if (plan === 'professional') return 'green'
  return 'gray'
}

function statusVariant(s: string | null): 'green' | 'yellow' | 'red' | 'gray' {
  if (s === 'active' || s === 'trialing') return 'green'
  if (s === 'past_due') return 'yellow'
  if (s === 'cancelled') return 'red'
  return 'gray'
}

interface CreateModalProps { onClose: () => void }

function CreateModal({ onClose }: CreateModalProps) {
  const qc = useQueryClient()
  const toast = useToast()
  const [form, setForm] = useState<TenantCreate>({
    company_name: '',
    admin_email: '',
    admin_name: '',
    admin_password: '',
    connector_limit: 10,
    users_limit: 5,
  })

  const create = useMutation({
    mutationFn: () => adminApi.createTenant(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-tenants'] })
      toast.success('Client créé avec succès')
      onClose()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const field = (key: keyof TenantCreate, type = 'text', placeholder = '') => (
    <input
      type={type}
      placeholder={placeholder}
      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
      value={String(form[key])}
      onChange={(e) => setForm({ ...form, [key]: type === 'number' ? Number(e.target.value) : e.target.value })}
    />
  )

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-md flex flex-col gap-4">
        <h2 className="text-lg font-semibold text-gray-900">Nouveau client</h2>
        <div className="flex flex-col gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Nom de l'entreprise *</label>
            {field('company_name', 'text', 'Acme Corp')}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Email admin *</label>
              {field('admin_email', 'email', 'admin@acme.com')}
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Nom admin *</label>
              {field('admin_name', 'text', 'John Doe')}
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Mot de passe admin *</label>
            {field('admin_password', 'password')}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Quota connecteurs</label>
              {field('connector_limit', 'number')}
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Quota utilisateurs</label>
              {field('users_limit', 'number')}
            </div>
          </div>
        </div>
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button
            onClick={() => create.mutate()}
            loading={create.isPending}
            disabled={!form.company_name || !form.admin_email || !form.admin_password}
          >
            Créer
          </Button>
        </div>
      </Card>
    </div>
  )
}

export function TenantsPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [creating, setCreating] = useState(false)
  const [search, setSearch] = useState('')
  const [planFilter, setPlanFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [reactivateTarget, setReactivateTarget] = useState<TenantStats | null>(null)

  const { data: tenants, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['admin-tenants'],
    queryFn: adminApi.getTenants,
    refetchInterval: 30_000,
  })

  const reactivate = useMutation({
    mutationFn: (id: string) => adminApi.reactivateTenant(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-tenants'] })
      toast.success('Tenant réactivé')
      setReactivateTarget(null)
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const filtered = (tenants ?? []).filter((t) => {
    const q = search.toLowerCase()
    if (q && !t.name.toLowerCase().includes(q) && !t.slug.toLowerCase().includes(q)) return false
    if (planFilter !== 'all' && t.plan !== planFilter) return false
    if (statusFilter !== 'all' && t.subscription_status !== statusFilter) return false
    return true
  })

  const totalUsers = (tenants ?? []).reduce((s, t) => s + t.user_count, 0)
  const totalConnectors = (tenants ?? []).reduce((s, t) => s + t.connector_count, 0)

  if (isLoading) return <div className="flex justify-center py-16"><Spinner size="lg" /></div>

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Clients</h1>
          <p className="text-sm text-gray-500 mt-0.5">{tenants?.length ?? 0} tenant{(tenants?.length ?? 0) > 1 ? 's' : ''} sur la plateforme</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            title="Actualiser"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          </button>
          <Button onClick={() => setCreating(true)} className="flex items-center gap-2">
            <Plus className="h-4 w-4" /> Nouveau client
          </Button>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Tenants', value: tenants?.length ?? 0, icon: Building2, color: 'text-brand-600', bg: 'bg-brand-50' },
          { label: 'Utilisateurs', value: totalUsers, icon: Users, color: 'text-blue-600', bg: 'bg-blue-50' },
          { label: 'Connecteurs', value: totalConnectors, icon: Plug, color: 'text-green-600', bg: 'bg-green-50' },
        ].map(({ label, value, icon: Icon, color, bg }) => (
          <Card key={label} padding="sm" className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${bg}`}><Icon className={`h-4 w-4 ${color}`} /></div>
            <div>
              <p className="text-xs text-gray-500">{label}</p>
              <p className="text-lg font-bold text-gray-900">{value.toLocaleString('fr-FR')}</p>
            </div>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher un client…"
            className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <select
          value={planFilter}
          onChange={(e) => setPlanFilter(e.target.value)}
          className="pl-3 pr-8 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="all">Tous les plans</option>
          <option value="starter">Starter</option>
          <option value="professional">Professional</option>
          <option value="enterprise">Enterprise</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="pl-3 pr-8 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="all">Tous les statuts</option>
          <option value="trialing">Trial</option>
          <option value="active">Actif</option>
          <option value="past_due">Impayé</option>
          <option value="cancelled">Annulé</option>
        </select>
        {(search || planFilter !== 'all' || statusFilter !== 'all') && (
          <button onClick={() => { setSearch(''); setPlanFilter('all'); setStatusFilter('all') }} className="text-xs text-brand-600 hover:underline">
            Réinitialiser
          </button>
        )}
      </div>

      {/* Table */}
      <Card padding="none">
        <table className="w-full text-sm">
          <thead className="border-b border-gray-100 bg-gray-50">
            <tr>
              {['Entreprise', 'Plan', 'Utilisateurs', 'Connecteurs', 'Statut', 'Créé le', ''].map((h) => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {filtered.map((t) => (
              <tr key={t.id} className="hover:bg-gray-50 transition-colors group">
                <td className="px-4 py-3">
                  <button onClick={() => navigate(`/admin/tenants/${t.id}`)} className="font-medium text-gray-900 hover:text-brand-600 text-left">
                    {t.name}
                  </button>
                  <p className="text-xs text-gray-400 font-mono">{t.slug}</p>
                </td>
                <td className="px-4 py-3">
                  <Badge variant={planVariant(t.plan)}>{t.plan ?? '—'}</Badge>
                </td>
                <td className="px-4 py-3 text-gray-600">
                  <span className={t.users_limit !== null && t.user_count >= t.users_limit ? 'text-red-600 font-semibold' : ''}>
                    {t.user_count}
                  </span>
                  <span className="text-gray-400"> / {t.users_limit ?? '∞'}</span>
                </td>
                <td className="px-4 py-3 text-gray-600">
                  <span className={t.connector_limit !== null && t.connector_count >= t.connector_limit ? 'text-red-600 font-semibold' : ''}>
                    {t.connector_count}
                  </span>
                  <span className="text-gray-400"> / {t.connector_limit ?? '∞'}</span>
                </td>
                <td className="px-4 py-3">
                  <Badge variant={statusVariant(t.subscription_status)}>
                    {t.subscription_status ?? '—'}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {new Date(t.created_at).toLocaleDateString('fr-FR')}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1 justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                    {t.subscription_status === 'cancelled' && (
                      <button
                        onClick={(e) => { e.stopPropagation(); setReactivateTarget(t) }}
                        className="px-2 py-1 text-xs text-green-600 hover:bg-green-50 rounded font-medium transition-colors"
                        title="Réactiver"
                      >
                        Réactiver
                      </button>
                    )}
                    <button onClick={() => navigate(`/admin/tenants/${t.id}`)} className="p-1 text-gray-400 hover:text-brand-600 rounded transition-colors">
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="text-center text-sm text-gray-500 py-10">
            {tenants?.length === 0 ? "Aucun client pour l'instant." : 'Aucun client ne correspond aux filtres.'}
          </p>
        )}
      </Card>

      {creating && <CreateModal onClose={() => setCreating(false)} />}

      {reactivateTarget && (
        <ConfirmModal
          title="Réactiver le tenant"
          message={`Réactiver tous les utilisateurs de "${reactivateTarget.name}" ?`}
          confirmLabel="Réactiver"
          loading={reactivate.isPending}
          onConfirm={() => reactivate.mutate(reactivateTarget.id)}
          onCancel={() => setReactivateTarget(null)}
        />
      )}
    </div>
  )
}
