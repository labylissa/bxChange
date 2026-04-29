import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Plus, ChevronRight } from 'lucide-react'
import type { TenantCreate } from '@/lib/api/admin'
import { adminApi } from '@/lib/api/admin'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { useToast } from '@/stores/toastStore'

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

  const field = (key: keyof TenantCreate, type = 'text') => (
    <input
      type={type}
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
            <label className="block text-xs text-gray-500 mb-1">Nom de l'entreprise *</label>
            {field('company_name')}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Email admin *</label>
              {field('admin_email', 'email')}
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Nom admin *</label>
              {field('admin_name')}
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Mot de passe admin *</label>
            {field('admin_password', 'password')}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Quota connecteurs</label>
              {field('connector_limit', 'number')}
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Quota utilisateurs</label>
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
  const [creating, setCreating] = useState(false)

  const { data: tenants, isLoading } = useQuery({
    queryKey: ['admin-tenants'],
    queryFn: adminApi.getTenants,
    refetchInterval: 30_000,
  })

  if (isLoading) {
    return <div className="flex justify-center py-16"><Spinner size="lg" /></div>
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Clients ({tenants?.length ?? 0})</h1>
        <Button onClick={() => setCreating(true)} className="flex items-center gap-2">
          <Plus className="h-4 w-4" /> Nouveau client
        </Button>
      </div>

      <Card padding="none">
        <table className="w-full text-sm">
          <thead className="border-b border-gray-100 bg-gray-50">
            <tr>
              {['Entreprise', 'Plan', 'Utilisateurs', 'Connecteurs', 'Statut', ''].map((h) => (
                <th key={h} className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {tenants?.map((t) => (
              <tr
                key={t.id}
                className="hover:bg-gray-50 cursor-pointer transition-colors"
                onClick={() => navigate(`/admin/tenants/${t.id}`)}
              >
                <td className="px-4 py-3 font-medium text-gray-900">{t.name}</td>
                <td className="px-4 py-3">
                  <Badge variant={planVariant(t.plan)}>{t.plan ?? '—'}</Badge>
                </td>
                <td className="px-4 py-3 text-gray-600">
                  {t.user_count} / {t.users_limit ?? '∞'}
                </td>
                <td className="px-4 py-3 text-gray-600">
                  {t.connector_count} / {t.connector_limit ?? '∞'}
                </td>
                <td className="px-4 py-3">
                  <Badge variant={statusVariant(t.subscription_status)}>
                    {t.subscription_status ?? '—'}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-gray-400">
                  <ChevronRight className="h-4 w-4" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {tenants?.length === 0 && (
          <p className="text-center text-sm text-gray-500 py-10">Aucun client pour l'instant.</p>
        )}
      </Card>

      {creating && <CreateModal onClose={() => setCreating(false)} />}
    </div>
  )
}
