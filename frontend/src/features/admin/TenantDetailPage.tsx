import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Pencil, Power } from 'lucide-react'
import { adminApi } from '@/lib/api/admin'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { useToast } from '@/stores/toastStore'

function roleBadge(role: string) {
  const v = role === 'admin' ? 'blue' : role === 'developer' ? 'green' : 'gray'
  return <Badge variant={v}>{role}</Badge>
}

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
            <label className="block text-xs text-gray-500 mb-1">Quota connecteurs</label>
            <input type="number" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" value={cl} onChange={(e) => setCl(Number(e.target.value))} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Quota utilisateurs</label>
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

export function TenantDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [quotaModal, setQuotaModal] = useState(false)
  const [deactivateConfirm, setDeactivateConfirm] = useState(false)

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

  if (isLoading) return <div className="flex justify-center py-16"><Spinner size="lg" /></div>
  if (!tenant) return <p className="text-sm text-gray-500">Tenant introuvable.</p>

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/admin/tenants')} className="text-gray-400 hover:text-gray-600">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-xl font-semibold text-gray-900">{tenant.name}</h1>
          {tenant.subscription_status && (
            <Badge variant={tenant.subscription_status === 'active' || tenant.subscription_status === 'trialing' ? 'green' : 'yellow'}>
              {tenant.subscription_status}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => setQuotaModal(true)} className="flex items-center gap-1">
            <Pencil className="h-3 w-3" /> Modifier quotas
          </Button>
          <Button variant="danger" size="sm" onClick={() => setDeactivateConfirm(true)} className="flex items-center gap-1">
            <Power className="h-3 w-3" /> Désactiver
          </Button>
        </div>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Plan', value: tenant.plan ?? '—' },
          { label: 'Connecteurs', value: `${tenant.connector_count} / ${tenant.connector_limit ?? '∞'}` },
          { label: 'Utilisateurs', value: `${tenant.user_count} / ${tenant.users_limit ?? '∞'}` },
          { label: 'Créé le', value: new Date(tenant.created_at).toLocaleDateString('fr-FR') },
        ].map(({ label, value }) => (
          <Card key={label} padding="sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className="text-sm font-semibold text-gray-900 mt-1">{value}</p>
          </Card>
        ))}
      </div>

      {/* Users */}
      <Card padding="none">
        <div className="px-4 py-3 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-700">Utilisateurs ({tenant.users.length})</h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {['Nom', 'Email', 'Rôle', 'Statut'].map((h) => (
                <th key={h} className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {tenant.users.map((u) => (
              <tr key={u.id}>
                <td className="px-4 py-2 font-medium text-gray-900">{u.full_name ?? '—'}</td>
                <td className="px-4 py-2 text-gray-600">{u.email}</td>
                <td className="px-4 py-2">{roleBadge(u.role)}</td>
                <td className="px-4 py-2">
                  <Badge variant={u.is_active ? 'green' : 'red'}>{u.is_active ? 'actif' : 'inactif'}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {/* Connectors */}
      <Card padding="none">
        <div className="px-4 py-3 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-700">Connecteurs ({tenant.connectors.length})</h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {['Nom', 'Type', 'Statut', 'Créé le'].map((h) => (
                <th key={h} className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {tenant.connectors.map((c) => (
              <tr key={c.id}>
                <td className="px-4 py-2 font-medium text-gray-900">{c.name}</td>
                <td className="px-4 py-2"><Badge variant="gray">{c.type.toUpperCase()}</Badge></td>
                <td className="px-4 py-2"><Badge variant={c.status === 'active' ? 'green' : 'gray'}>{c.status}</Badge></td>
                <td className="px-4 py-2 text-gray-600">{new Date(c.created_at).toLocaleDateString('fr-FR')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {quotaModal && (
        <QuotaModal
          tenantId={id!}
          current={{ connector_limit: tenant.connector_limit, users_limit: tenant.users_limit }}
          onClose={() => setQuotaModal(false)}
        />
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
    </div>
  )
}
