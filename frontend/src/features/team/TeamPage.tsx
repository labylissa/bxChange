import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { UserPlus, UserX, ChevronDown } from 'lucide-react'
import type { TeamInvite } from '@/lib/api/team'
import { teamApi } from '@/lib/api/team'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { useToast } from '@/stores/toastStore'
import { useAuthStore } from '@/stores/authStore'

const ROLES = ['admin', 'developer', 'viewer'] as const
type Role = typeof ROLES[number]

function roleBadge(role: string) {
  const v: 'blue' | 'green' | 'gray' = role === 'admin' ? 'blue' : role === 'developer' ? 'green' : 'gray'
  return <Badge variant={v}>{role}</Badge>
}

interface InviteModalProps { onClose: () => void }

function InviteModal({ onClose }: InviteModalProps) {
  const qc = useQueryClient()
  const toast = useToast()
  const [form, setForm] = useState<TeamInvite>({ email: '', full_name: '', password: '', role: 'developer' })

  const invite = useMutation({
    mutationFn: () => teamApi.invite(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['team-members'] })
      toast.success('Membre invité avec succès')
      onClose()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-md flex flex-col gap-4">
        <h2 className="text-lg font-semibold text-gray-900">Inviter un membre</h2>

        <div className="flex flex-col gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Email *</label>
            <input type="email" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Nom complet *</label>
            <input type="text" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Mot de passe *</label>
            <input type="password" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Rôle</label>
            <select className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        </div>

        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button onClick={() => invite.mutate()} loading={invite.isPending}
            disabled={!form.email || !form.full_name || !form.password}>
            Inviter
          </Button>
        </div>
      </Card>
    </div>
  )
}

export function TeamPage() {
  const currentUser = useAuthStore((s) => s.user)
  const qc = useQueryClient()
  const toast = useToast()
  const [inviteOpen, setInviteOpen] = useState(false)
  const [deactivateId, setDeactivateId] = useState<string | null>(null)
  const [roleDropdown, setRoleDropdown] = useState<string | null>(null)

  const { data: members, isLoading } = useQuery({
    queryKey: ['team-members'],
    queryFn: teamApi.getMembers,
    refetchInterval: 30_000,
  })

  const updateRole = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) => teamApi.updateRole(id, role),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['team-members'] })
      toast.success('Rôle mis à jour')
      setRoleDropdown(null)
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const deactivate = useMutation({
    mutationFn: (id: string) => teamApi.deactivate(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['team-members'] })
      toast.success('Membre désactivé')
      setDeactivateId(null)
    },
    onError: (e: Error) => toast.error(e.message),
  })

  if (isLoading) return <div className="flex justify-center py-16"><Spinner size="lg" /></div>

  const targetMember = deactivateId ? members?.find((m) => m.id === deactivateId) : null

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">
          Équipe ({members?.length ?? 0} membres)
        </h1>
        <Button onClick={() => setInviteOpen(true)} className="flex items-center gap-2">
          <UserPlus className="h-4 w-4" /> Inviter un membre
        </Button>
      </div>

      <Card padding="none">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {['Nom', 'Email', 'Rôle', 'Statut', 'Membre depuis', 'Actions'].map((h) => (
                <th key={h} className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {members?.map((m) => (
              <tr key={m.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{m.full_name ?? '—'}</td>
                <td className="px-4 py-3 text-gray-600">{m.email}</td>
                <td className="px-4 py-3">
                  <div className="relative inline-block">
                    {m.id === currentUser?.id || m.role === 'super_admin' ? (
                      roleBadge(m.role)
                    ) : (
                      <button
                        onClick={() => setRoleDropdown(roleDropdown === m.id ? null : m.id)}
                        className="flex items-center gap-1 text-xs font-medium px-2.5 py-0.5 rounded-full bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
                      >
                        {m.role} <ChevronDown className="h-3 w-3" />
                      </button>
                    )}
                    {roleDropdown === m.id && (
                      <div className="absolute left-0 top-full mt-1 z-10 bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-[120px]">
                        {ROLES.map((r) => (
                          <button
                            key={r}
                            onClick={() => updateRole.mutate({ id: m.id, role: r })}
                            className="w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 text-gray-700"
                          >
                            {r}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <Badge variant={m.is_active ? 'green' : 'red'}>{m.is_active ? 'actif' : 'inactif'}</Badge>
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  {new Date(m.created_at).toLocaleDateString('fr-FR')}
                </td>
                <td className="px-4 py-3">
                  {m.id !== currentUser?.id && m.role !== 'super_admin' && m.is_active && (
                    <button
                      onClick={() => setDeactivateId(m.id)}
                      className="text-gray-400 hover:text-red-500 transition-colors"
                      title="Désactiver"
                    >
                      <UserX className="h-4 w-4" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {members?.length === 0 && (
          <p className="text-center text-sm text-gray-500 py-10">Aucun membre.</p>
        )}
      </Card>

      {inviteOpen && <InviteModal onClose={() => setInviteOpen(false)} />}

      {deactivateId && targetMember && (
        <ConfirmModal
          title="Désactiver le membre"
          message={`Désactiver "${targetMember.full_name ?? targetMember.email}" ? Ils ne pourront plus se connecter.`}
          confirmLabel="Désactiver"
          danger
          loading={deactivate.isPending}
          onConfirm={() => deactivate.mutate(deactivateId)}
          onCancel={() => setDeactivateId(null)}
        />
      )}
    </div>
  )
}
