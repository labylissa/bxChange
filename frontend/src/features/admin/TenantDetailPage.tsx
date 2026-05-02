import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Pencil, Power, PlayCircle, Shield, UserCheck, UserX,
  RefreshCw, Globe, Wifi, ChevronDown,
} from 'lucide-react'
import { adminApi } from '@/lib/api/admin'
import type { UserInTenant } from '@/lib/api/admin'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { useToast } from '@/stores/toastStore'
import { useAuthStore } from '@/stores/authStore'

const ROLES = ['admin', 'developer', 'viewer']
const PLANS = ['starter', 'professional', 'enterprise']

// ── Quota modal ───────────────────────────────────────────────────────────────

interface QuotaModalProps {
  tenantId: string
  current: { connector_limit: number | null; users_limit: number | null }
  onClose: () => void
}

function QuotaModal({ tenantId, current, onClose }: QuotaModalProps) {
  const qc = useQueryClient()
  const toast = useToast()
  const [cl, setCl] = useState(current.connector_limit ?? 10)
  const [ul, setUl] = useState(current.users_limit ?? 5)

  const save = useMutation({
    mutationFn: () => adminApi.updateQuota(tenantId, cl, ul),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-tenant', tenantId] })
      qc.invalidateQueries({ queryKey: ['admin-tenants'] })
      toast.success('Quotas mis à jour')
      onClose()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-sm flex flex-col gap-4">
        <h2 className="text-lg font-semibold text-gray-900">Modifier les quotas</h2>
        <div className="flex flex-col gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Quota connecteurs</label>
            <input type="number" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" value={cl} onChange={(e) => setCl(Number(e.target.value))} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Quota utilisateurs</label>
            <input type="number" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" value={ul} onChange={(e) => setUl(Number(e.target.value))} />
          </div>
        </div>
        <div className="flex gap-2 justify-end">
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button onClick={() => save.mutate()} loading={save.isPending}>Enregistrer</Button>
        </div>
      </Card>
    </div>
  )
}

// ── Plan modal ────────────────────────────────────────────────────────────────

interface PlanModalProps {
  tenantId: string
  currentPlan: string | null
  onClose: () => void
}

function PlanModal({ tenantId, currentPlan, onClose }: PlanModalProps) {
  const qc = useQueryClient()
  const toast = useToast()
  const [plan, setPlan] = useState(currentPlan ?? 'starter')

  const save = useMutation({
    mutationFn: () => adminApi.changePlan(tenantId, plan),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-tenant', tenantId] })
      qc.invalidateQueries({ queryKey: ['admin-tenants'] })
      toast.success(`Plan changé en ${plan}`)
      onClose()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-sm flex flex-col gap-4">
        <h2 className="text-lg font-semibold text-gray-900">Changer le plan</h2>
        <div className="flex flex-col gap-2">
          {PLANS.map((p) => (
            <label key={p} className={`flex items-center gap-3 p-3 border rounded-lg cursor-pointer transition-colors ${plan === p ? 'border-brand-500 bg-brand-50' : 'border-gray-200 hover:bg-gray-50'}`}>
              <input type="radio" name="plan" value={p} checked={plan === p} onChange={() => setPlan(p)} className="accent-brand-600" />
              <span className="capitalize font-medium text-sm text-gray-800">{p}</span>
            </label>
          ))}
        </div>
        <div className="flex gap-2 justify-end">
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button onClick={() => save.mutate()} loading={save.isPending} disabled={plan === currentPlan}>
            Appliquer
          </Button>
        </div>
      </Card>
    </div>
  )
}

// ── Users table with per-user actions ────────────────────────────────────────

interface UsersTableProps {
  tenantId: string
  users: UserInTenant[]
}

function UsersTable({ tenantId, users }: UsersTableProps) {
  const qc = useQueryClient()
  const toast = useToast()
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)

  const changeRole = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      adminApi.updateRole(userId, role),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-tenant', tenantId] })
      toast.success('Rôle mis à jour')
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const toggleActive = useMutation({
    mutationFn: ({ userId, is_active }: { userId: string; is_active: boolean }) =>
      adminApi.toggleActivate(userId, is_active),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-tenant', tenantId] })
      toast.success('Statut mis à jour')
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const impersonate = useMutation({
    mutationFn: (userId: string) => adminApi.impersonate(userId),
    onSuccess: (data) => {
      login(data.access_token, '', { id: data.user_id, email: data.email, full_name: data.email, role: 'viewer', tenant_id: null })
      toast.success(`Session ouverte en tant que ${data.email}`)
      navigate('/dashboard')
    },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <Card padding="none">
      <div className="px-4 py-3 border-b border-gray-100">
        <h2 className="text-sm font-semibold text-gray-700">Utilisateurs ({users.length})</h2>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-100">
          <tr>
            {['Nom', 'Email', 'Rôle', 'Statut', 'Actions'].map((h) => (
              <th key={h} className="text-left px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {users.map((u) => (
            <tr key={u.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3 font-medium text-gray-900">{u.full_name ?? '—'}</td>
              <td className="px-4 py-3 text-gray-500 text-xs font-mono">{u.email}</td>
              <td className="px-4 py-3">
                <div className="relative inline-block">
                  <select
                    value={u.role}
                    onChange={(e) => changeRole.mutate({ userId: u.id, role: e.target.value })}
                    className="appearance-none pl-2 pr-6 py-1 border border-gray-200 rounded text-xs bg-white focus:outline-none focus:ring-1 focus:ring-brand-500 cursor-pointer"
                  >
                    {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                  <ChevronDown className="absolute right-1.5 top-1/2 -translate-y-1/2 h-3 w-3 text-gray-400 pointer-events-none" />
                </div>
              </td>
              <td className="px-4 py-3">
                <Badge variant={u.is_active ? 'green' : 'red'}>{u.is_active ? 'actif' : 'inactif'}</Badge>
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => impersonate.mutate(u.id)}
                    disabled={impersonate.isPending}
                    className="flex items-center gap-1 px-2 py-1 text-xs text-brand-600 hover:bg-brand-50 rounded transition-colors font-medium"
                    title="Se connecter en tant que cet utilisateur"
                  >
                    <PlayCircle className="h-3.5 w-3.5" />
                    Impersonner
                  </button>
                  <button
                    onClick={() => toggleActive.mutate({ userId: u.id, is_active: !u.is_active })}
                    className={`flex items-center gap-1 px-2 py-1 text-xs rounded transition-colors font-medium ${
                      u.is_active
                        ? 'text-red-600 hover:bg-red-50'
                        : 'text-green-600 hover:bg-green-50'
                    }`}
                    title={u.is_active ? 'Désactiver' : 'Activer'}
                  >
                    {u.is_active ? <UserX className="h-3.5 w-3.5" /> : <UserCheck className="h-3.5 w-3.5" />}
                    {u.is_active ? 'Désactiver' : 'Activer'}
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {users.length === 0 && (
        <p className="text-center text-sm text-gray-500 py-6">Aucun utilisateur.</p>
      )}
    </Card>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function TenantDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [quotaModal, setQuotaModal] = useState(false)
  const [planModal, setPlanModal] = useState(false)
  const [deactivateConfirm, setDeactivateConfirm] = useState(false)
  const [reactivateConfirm, setReactivateConfirm] = useState(false)

  const { data: tenant, isLoading } = useQuery({
    queryKey: ['admin-tenant', id],
    queryFn: () => adminApi.getTenant(id!),
    enabled: !!id,
  })

  const deactivate = useMutation({
    mutationFn: () => adminApi.deactivateTenant(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-tenants'] })
      toast.success('Tenant désactivé')
      navigate('/admin/tenants')
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const reactivate = useMutation({
    mutationFn: () => adminApi.reactivateTenant(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-tenant', id] })
      qc.invalidateQueries({ queryKey: ['admin-tenants'] })
      toast.success('Tenant réactivé')
      setReactivateConfirm(false)
    },
    onError: (e: Error) => toast.error(e.message),
  })

  if (isLoading) return <div className="flex justify-center py-16"><Spinner size="lg" /></div>
  if (!tenant) return <p className="text-sm text-gray-500">Tenant introuvable.</p>

  const isActive = tenant.subscription_status === 'active' || tenant.subscription_status === 'trialing'

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/admin/tenants')} className="text-gray-400 hover:text-gray-600 p-1 rounded hover:bg-gray-100 transition-colors">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <h1 className="text-xl font-semibold text-gray-900">{tenant.name}</h1>
            <p className="text-xs text-gray-400 font-mono">{tenant.slug}</p>
          </div>
          {tenant.subscription_status && (
            <Badge variant={isActive ? 'green' : 'red'}>{tenant.subscription_status}</Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => setPlanModal(true)} className="flex items-center gap-1">
            <Shield className="h-3.5 w-3.5" /> Changer plan
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setQuotaModal(true)} className="flex items-center gap-1">
            <Pencil className="h-3.5 w-3.5" /> Quotas
          </Button>
          {isActive ? (
            <Button variant="danger" size="sm" onClick={() => setDeactivateConfirm(true)} className="flex items-center gap-1">
              <Power className="h-3.5 w-3.5" /> Désactiver
            </Button>
          ) : (
            <Button size="sm" onClick={() => setReactivateConfirm(true)} className="flex items-center gap-1 bg-green-600 hover:bg-green-700">
              <RefreshCw className="h-3.5 w-3.5" /> Réactiver
            </Button>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Plan', value: tenant.plan ?? '—' },
          { label: 'Connecteurs', value: `${tenant.connector_count} / ${tenant.connector_limit ?? '∞'}` },
          { label: 'Utilisateurs', value: `${tenant.user_count} / ${tenant.users_limit ?? '∞'}` },
          { label: 'Créé le', value: new Date(tenant.created_at).toLocaleDateString('fr-FR') },
        ].map(({ label, value }) => (
          <Card key={label} padding="sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className="text-sm font-semibold text-gray-900 mt-1 capitalize">{value}</p>
          </Card>
        ))}
      </div>

      {/* Users */}
      <UsersTable tenantId={id!} users={tenant.users} />

      {/* Connectors */}
      <Card padding="none">
        <div className="px-4 py-3 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-700">Connecteurs ({tenant.connectors.length})</h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {['Nom', 'Type', 'Statut', 'Créé le'].map((h) => (
                <th key={h} className="text-left px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {tenant.connectors.map((c) => (
              <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 font-medium text-gray-900">{c.name}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    {c.type === 'soap'
                      ? <Wifi className="h-3.5 w-3.5 text-purple-500" />
                      : <Globe className="h-3.5 w-3.5 text-blue-500" />}
                    <span className="text-xs font-medium text-gray-600 uppercase">{c.type}</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <Badge variant={c.status === 'active' ? 'green' : c.status === 'error' ? 'red' : 'gray'}>{c.status}</Badge>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">{new Date(c.created_at).toLocaleDateString('fr-FR')}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {tenant.connectors.length === 0 && (
          <p className="text-center text-sm text-gray-500 py-6">Aucun connecteur.</p>
        )}
      </Card>

      {quotaModal && (
        <QuotaModal
          tenantId={id!}
          current={{ connector_limit: tenant.connector_limit, users_limit: tenant.users_limit }}
          onClose={() => setQuotaModal(false)}
        />
      )}

      {planModal && (
        <PlanModal tenantId={id!} currentPlan={tenant.plan} onClose={() => setPlanModal(false)} />
      )}

      {deactivateConfirm && (
        <ConfirmModal
          title="Désactiver le tenant"
          message={`Tous les utilisateurs de "${tenant.name}" seront désactivés. Continuer ?`}
          confirmLabel="Désactiver"
          danger
          loading={deactivate.isPending}
          onConfirm={() => deactivate.mutate()}
          onCancel={() => setDeactivateConfirm(false)}
        />
      )}

      {reactivateConfirm && (
        <ConfirmModal
          title="Réactiver le tenant"
          message={`Réactiver tous les utilisateurs de "${tenant.name}" ?`}
          confirmLabel="Réactiver"
          loading={reactivate.isPending}
          onConfirm={() => reactivate.mutate()}
          onCancel={() => setReactivateConfirm(false)}
        />
      )}
    </div>
  )
}
