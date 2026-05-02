import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  UserPlus, Search, Shield, Code2, Eye, ShieldCheck,
  MoreVertical, Pencil, KeyRound, UserCheck, UserX, X,
  Clock, Mail, Calendar, ChevronDown, AlertTriangle, Copy, Check,
} from 'lucide-react'
import { teamApi, type TeamMember } from '@/lib/api/team'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { useToast } from '@/stores/toastStore'
import { useAuthStore } from '@/stores/authStore'

// ── Role config ───────────────────────────────────────────────────────────────

const ROLE_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ElementType; desc: string }> = {
  super_admin: { label: 'Super Admin', color: 'text-purple-700', bg: 'bg-purple-100', icon: ShieldCheck, desc: 'Accès total à toute la plateforme' },
  admin: { label: 'Admin', color: 'text-blue-700', bg: 'bg-blue-100', icon: Shield, desc: 'Gère les membres et les connecteurs' },
  developer: { label: 'Développeur', color: 'text-emerald-700', bg: 'bg-emerald-100', icon: Code2, desc: 'Crée et teste les connecteurs' },
  viewer: { label: 'Lecteur', color: 'text-gray-600', bg: 'bg-gray-100', icon: Eye, desc: 'Lecture seule' },
}

const ASSIGNABLE_ROLES = ['admin', 'developer', 'viewer'] as const

function RoleBadge({ role }: { role: string }) {
  const cfg = ROLE_CONFIG[role] ?? ROLE_CONFIG.viewer
  const Icon = cfg.icon
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.bg} ${cfg.color}`}>
      <Icon className="h-3 w-3" />
      {cfg.label}
    </span>
  )
}

// ── Last login display ────────────────────────────────────────────────────────

function LastLogin({ date }: { date: string | null }) {
  if (!date) return (
    <span className="inline-flex items-center gap-1 text-xs text-gray-400">
      <Clock className="h-3 w-3" /> Jamais connecté
    </span>
  )
  const d = new Date(date)
  const diffH = (Date.now() - d.getTime()) / 3_600_000
  const label = diffH < 1 ? "À l'instant"
    : diffH < 24 ? `Il y a ${Math.round(diffH)}h`
    : diffH < 168 ? `Il y a ${Math.round(diffH / 24)}j`
    : d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
  const isRecent = diffH < 24
  return (
    <span className={`inline-flex items-center gap-1 text-xs ${isRecent ? 'text-emerald-600' : 'text-gray-500'}`}>
      {isRecent && <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />}
      {label}
    </span>
  )
}

// ── Avatar initials ───────────────────────────────────────────────────────────

const AVATAR_COLORS = [
  'bg-violet-500', 'bg-blue-500', 'bg-emerald-500',
  'bg-amber-500', 'bg-rose-500', 'bg-cyan-500',
]

function Avatar({ name, email, size = 'sm' }: { name: string | null; email: string; size?: 'sm' | 'lg' }) {
  const initials = name
    ? name.split(' ').map((w) => w[0]).join('').toUpperCase().slice(0, 2)
    : email[0].toUpperCase()
  const colorIdx = email.charCodeAt(0) % AVATAR_COLORS.length
  const sz = size === 'lg' ? 'h-12 w-12 text-base' : 'h-8 w-8 text-xs'
  return (
    <div className={`${sz} ${AVATAR_COLORS[colorIdx]} rounded-full flex items-center justify-center text-white font-semibold flex-shrink-0`}>
      {initials}
    </div>
  )
}

// ── Copy button ───────────────────────────────────────────────────────────────

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
      className="p-1 text-gray-400 hover:text-gray-700 transition-colors">
      {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  )
}

// ── Invite modal ──────────────────────────────────────────────────────────────

function InviteModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [form, setForm] = useState({ email: '', full_name: '', password: '', role: 'developer' as 'admin' | 'developer' | 'viewer' })

  const invite = useMutation({
    mutationFn: () => teamApi.invite(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['team-members'] }); toast.success('Membre invité avec succès'); onClose() },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Inviter un membre</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
        </div>
        <div className="space-y-3">
          {[
            { label: 'Email *', type: 'email', key: 'email', placeholder: 'jean@entreprise.com' },
            { label: 'Nom complet *', type: 'text', key: 'full_name', placeholder: 'Jean Dupont' },
            { label: 'Mot de passe *', type: 'password', key: 'password', placeholder: '••••••••' },
          ].map(({ label, type, key, placeholder }) => (
            <div key={key}>
              <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
              <input type={type} placeholder={placeholder}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                value={(form as Record<string, string>)[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
            </div>
          ))}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-2">Rôle</label>
            <div className="space-y-2">
              {ASSIGNABLE_ROLES.map((r) => {
                const cfg = ROLE_CONFIG[r]
                const Icon = cfg.icon
                return (
                  <label key={r} className={`flex items-center gap-3 p-2.5 rounded-lg border-2 cursor-pointer transition-colors ${form.role === r ? 'border-brand-500 bg-brand-50' : 'border-gray-200 hover:border-gray-300'}`}>
                    <input type="radio" name="role" value={r} checked={form.role === r} onChange={() => setForm({ ...form, role: r })} className="sr-only" />
                    <div className={`p-1 rounded-md ${cfg.bg}`}><Icon className={`h-3.5 w-3.5 ${cfg.color}`} /></div>
                    <div>
                      <p className="text-sm font-medium text-gray-800">{cfg.label}</p>
                      <p className="text-xs text-gray-400">{cfg.desc}</p>
                    </div>
                  </label>
                )
              })}
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button onClick={() => invite.mutate()} loading={invite.isPending}
            disabled={!form.email || !form.full_name || !form.password}>
            Inviter
          </Button>
        </div>
      </div>
    </div>
  )
}

// ── Edit modal ────────────────────────────────────────────────────────────────

function EditModal({ member, onClose }: { member: TeamMember; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [fullName, setFullName] = useState(member.full_name ?? '')
  const [role, setRole] = useState(member.role)

  const update = useMutation({
    mutationFn: () => teamApi.update(member.id, { full_name: fullName, role }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['team-members'] }); toast.success('Membre modifié'); onClose() },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Modifier le membre</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
        </div>
        <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
          <Avatar name={member.full_name} email={member.email} />
          <div>
            <p className="text-sm font-medium text-gray-800">{member.full_name || '—'}</p>
            <p className="text-xs text-gray-500">{member.email}</p>
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Nom complet</label>
          <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-2">Rôle</label>
          <div className="space-y-2">
            {ASSIGNABLE_ROLES.map((r) => {
              const cfg = ROLE_CONFIG[r]
              const Icon = cfg.icon
              return (
                <label key={r} className={`flex items-center gap-3 p-2.5 rounded-lg border-2 cursor-pointer transition-colors ${role === r ? 'border-brand-500 bg-brand-50' : 'border-gray-200 hover:border-gray-300'}`}>
                  <input type="radio" name="edit-role" value={r} checked={role === r} onChange={() => setRole(r)} className="sr-only" />
                  <div className={`p-1 rounded-md ${cfg.bg}`}><Icon className={`h-3.5 w-3.5 ${cfg.color}`} /></div>
                  <div>
                    <p className="text-sm font-medium text-gray-800">{cfg.label}</p>
                    <p className="text-xs text-gray-400">{cfg.desc}</p>
                  </div>
                </label>
              )
            })}
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button onClick={() => update.mutate()} loading={update.isPending}>Enregistrer</Button>
        </div>
      </div>
    </div>
  )
}

// ── Reset password modal ──────────────────────────────────────────────────────

function ResetPasswordModal({ member, onClose }: { member: TeamMember; onClose: () => void }) {
  const toast = useToast()
  const [tempPwd, setTempPwd] = useState<string | null>(null)

  const reset = useMutation({
    mutationFn: () => teamApi.resetPassword(member.id),
    onSuccess: (d) => setTempPwd(d.temp_password),
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Réinitialiser le mot de passe</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
        </div>

        {!tempPwd ? (
          <>
            <div className="flex items-start gap-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <AlertTriangle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-amber-700">Un nouveau mot de passe temporaire sera généré pour <strong>{member.full_name || member.email}</strong>. L'ancien mot de passe sera invalidé immédiatement.</p>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={onClose}>Annuler</Button>
              <Button onClick={() => reset.mutate()} loading={reset.isPending}>Générer un mot de passe</Button>
            </div>
          </>
        ) : (
          <>
            <div className="flex items-start gap-3 p-3 bg-red-50 border border-red-200 rounded-lg">
              <AlertTriangle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700 font-medium">Copiez ce mot de passe maintenant — il ne sera plus affiché.</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Mot de passe temporaire</label>
              <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                <code className="flex-1 text-sm font-mono font-bold text-gray-900">{tempPwd}</code>
                <CopyBtn text={tempPwd} />
              </div>
            </div>
            <p className="text-xs text-gray-500">Communiquez ce mot de passe à <strong>{member.full_name || member.email}</strong> via un canal sécurisé. Ils devront le changer lors de leur prochaine connexion.</p>
            <Button className="w-full" onClick={onClose}>J'ai copié le mot de passe</Button>
          </>
        )}
      </div>
    </div>
  )
}

// ── Member drawer ─────────────────────────────────────────────────────────────

function MemberDrawer({
  member, onClose, onEdit, onReset,
  onDeactivate, onReactivate, isSelf,
}: {
  member: TeamMember; onClose: () => void
  onEdit: () => void; onReset: () => void
  onDeactivate: () => void; onReactivate: () => void
  isSelf: boolean
}) {
  const cfg = ROLE_CONFIG[member.role] ?? ROLE_CONFIG.viewer
  const Icon = cfg.icon

  return (
    <div className="fixed inset-0 z-40 flex justify-end" onClick={onClose}>
      <div className="fixed inset-0 bg-black/30" />
      <div
        className="relative w-full max-w-sm bg-white shadow-2xl h-full overflow-y-auto flex flex-col animate-slide-in-right"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-5 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Détail du membre</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-5 space-y-6">
          {/* Profile */}
          <div className="flex items-center gap-4">
            <Avatar name={member.full_name} email={member.email} size="lg" />
            <div>
              <p className="font-semibold text-gray-900">{member.full_name || '—'}</p>
              <div className="flex items-center gap-1 mt-0.5">
                <span className="text-sm text-gray-500">{member.email}</span>
                <CopyBtn text={member.email} />
              </div>
            </div>
          </div>

          {/* Status pills */}
          <div className="flex flex-wrap gap-2">
            <RoleBadge role={member.role} />
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${member.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${member.is_active ? 'bg-green-500' : 'bg-red-400'}`} />
              {member.is_active ? 'Actif' : 'Désactivé'}
            </span>
          </div>

          {/* Info rows */}
          <div className="space-y-3">
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <Clock className="h-4 w-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-500">Dernière connexion</p>
                <LastLogin date={member.last_login_at} />
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <Calendar className="h-4 w-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-500">Membre depuis</p>
                <p className="text-sm text-gray-700">{new Date(member.created_at).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' })}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <Mail className="h-4 w-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-500">Email</p>
                <div className="flex items-center gap-1">
                  <p className="text-sm text-gray-700">{member.email}</p>
                  <CopyBtn text={member.email} />
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <div className={`p-1 rounded-md ${cfg.bg}`}><Icon className={`h-3.5 w-3.5 ${cfg.color}`} /></div>
              <div>
                <p className="text-xs text-gray-500">Rôle</p>
                <p className="text-sm text-gray-700">{cfg.label} — {cfg.desc}</p>
              </div>
            </div>
          </div>

          {/* Actions */}
          {!isSelf && member.role !== 'super_admin' && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Actions admin</p>
              <button onClick={onEdit}
                className="w-full flex items-center gap-3 px-4 py-2.5 rounded-lg border border-gray-200 text-sm text-gray-700 hover:bg-gray-50 transition-colors">
                <Pencil className="h-4 w-4 text-gray-400" /> Modifier le profil
              </button>
              <button onClick={onReset}
                className="w-full flex items-center gap-3 px-4 py-2.5 rounded-lg border border-gray-200 text-sm text-gray-700 hover:bg-amber-50 hover:border-amber-200 transition-colors">
                <KeyRound className="h-4 w-4 text-amber-500" /> Réinitialiser le mot de passe
              </button>
              {member.is_active ? (
                <button onClick={onDeactivate}
                  className="w-full flex items-center gap-3 px-4 py-2.5 rounded-lg border border-red-100 text-sm text-red-600 hover:bg-red-50 transition-colors">
                  <UserX className="h-4 w-4" /> Désactiver le compte
                </button>
              ) : (
                <button onClick={onReactivate}
                  className="w-full flex items-center gap-3 px-4 py-2.5 rounded-lg border border-emerald-100 text-sm text-emerald-600 hover:bg-emerald-50 transition-colors">
                  <UserCheck className="h-4 w-4" /> Réactiver le compte
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Actions dropdown ──────────────────────────────────────────────────────────

function ActionsMenu({ member, onEdit, onReset, onDeactivate, onReactivate, onView, isSelf }: {
  member: TeamMember; onEdit: () => void; onReset: () => void
  onDeactivate: () => void; onReactivate: () => void; onView: () => void; isSelf: boolean
}) {
  const [open, setOpen] = useState(false)
  const items = [
    { label: 'Voir le détail', icon: Eye, action: onView },
    ...(!isSelf && member.role !== 'super_admin' ? [
      { label: 'Modifier', icon: Pencil, action: onEdit },
      { label: 'Réinitialiser le MDP', icon: KeyRound, action: onReset },
      member.is_active
        ? { label: 'Désactiver', icon: UserX, action: onDeactivate, danger: true }
        : { label: 'Réactiver', icon: UserCheck, action: onReactivate, success: true },
    ] : []),
  ]

  return (
    <div className="relative">
      <button onClick={() => setOpen((o) => !o)}
        className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
        <MoreVertical className="h-4 w-4" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-8 z-20 bg-white border border-gray-200 rounded-xl shadow-lg py-1.5 w-52">
            {items.map((item) => {
              const Icon = item.icon
              return (
                <button key={item.label} onClick={() => { item.action(); setOpen(false) }}
                  className={`w-full flex items-center gap-3 px-4 py-2 text-sm transition-colors ${
                    (item as { danger?: boolean }).danger ? 'text-red-600 hover:bg-red-50'
                    : (item as { success?: boolean }).success ? 'text-emerald-600 hover:bg-emerald-50'
                    : 'text-gray-700 hover:bg-gray-50'
                  }`}>
                  <Icon className="h-3.5 w-3.5" />
                  {item.label}
                </button>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function TeamPage() {
  const currentUser = useAuthStore((s) => s.user)
  const qc = useQueryClient()
  const toast = useToast()

  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [inviteOpen, setInviteOpen] = useState(false)
  const [drawerMember, setDrawerMember] = useState<TeamMember | null>(null)
  const [editMember, setEditMember] = useState<TeamMember | null>(null)
  const [resetMember, setResetMember] = useState<TeamMember | null>(null)
  const [deactivateId, setDeactivateId] = useState<string | null>(null)
  const [reactivateId, setReactivateId] = useState<string | null>(null)

  const { data: members, isLoading } = useQuery({
    queryKey: ['team-members'],
    queryFn: teamApi.getMembers,
    refetchInterval: 30_000,
  })

  const deactivate = useMutation({
    mutationFn: (id: string) => teamApi.deactivate(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['team-members'] }); toast.success('Membre désactivé'); setDeactivateId(null); setDrawerMember(null) },
    onError: (e: Error) => toast.error(e.message),
  })

  const reactivate = useMutation({
    mutationFn: (id: string) => teamApi.reactivate(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['team-members'] }); toast.success('Membre réactivé'); setReactivateId(null); setDrawerMember(null) },
    onError: (e: Error) => toast.error(e.message),
  })

  const filtered = (members ?? []).filter((m) => {
    const q = search.toLowerCase()
    if (q && !m.full_name?.toLowerCase().includes(q) && !m.email.toLowerCase().includes(q)) return false
    if (roleFilter !== 'all' && m.role !== roleFilter) return false
    if (statusFilter === 'active' && !m.is_active) return false
    if (statusFilter === 'inactive' && m.is_active) return false
    return true
  })

  const deactivateTarget = deactivateId ? (members ?? []).find((m) => m.id === deactivateId) : null
  const reactivateTarget = reactivateId ? (members ?? []).find((m) => m.id === reactivateId) : null

  if (isLoading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Équipe</h1>
          <p className="text-sm text-gray-500 mt-1">{members?.length ?? 0} membre{(members?.length ?? 0) > 1 ? 's' : ''} dans ce tenant</p>
        </div>
        <Button onClick={() => setInviteOpen(true)} className="flex items-center gap-2">
          <UserPlus className="h-4 w-4" /> Inviter un membre
        </Button>
      </div>

      {/* Search + Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher par nom ou email…"
            className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
          />
        </div>
        <div className="relative">
          <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}
            className="appearance-none pl-3 pr-8 py-2 border border-gray-300 rounded-lg text-sm bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-500 cursor-pointer">
            <option value="all">Tous les rôles</option>
            {Object.entries(ROLE_CONFIG).filter(([k]) => k !== 'super_admin').map(([k, v]) => (
              <option key={k} value={k}>{v.label}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400 pointer-events-none" />
        </div>
        <div className="relative">
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
            className="appearance-none pl-3 pr-8 py-2 border border-gray-300 rounded-lg text-sm bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-500 cursor-pointer">
            <option value="all">Tous les statuts</option>
            <option value="active">Actifs</option>
            <option value="inactive">Désactivés</option>
          </select>
          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400 pointer-events-none" />
        </div>
        {(search || roleFilter !== 'all' || statusFilter !== 'all') && (
          <button onClick={() => { setSearch(''); setRoleFilter('all'); setStatusFilter('all') }}
            className="text-xs text-brand-600 hover:underline">
            Réinitialiser
          </button>
        )}
      </div>

      {/* Table */}
      <Card padding="none">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {['Membre', 'Rôle', 'Statut', 'Dernière connexion', 'Depuis', ''].map((h) => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {filtered.map((m) => {
              const isSelf = m.id === currentUser?.id
              return (
                <tr key={m.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <button className="flex items-center gap-3 text-left group" onClick={() => setDrawerMember(m)}>
                      <Avatar name={m.full_name} email={m.email} />
                      <div>
                        <p className="font-medium text-gray-900 group-hover:text-brand-600 transition-colors">
                          {m.full_name ?? <span className="text-gray-400 italic">Sans nom</span>}
                          {isSelf && <span className="ml-2 text-xs text-gray-400 font-normal">(vous)</span>}
                        </p>
                        <p className="text-xs text-gray-500">{m.email}</p>
                      </div>
                    </button>
                  </td>
                  <td className="px-4 py-3"><RoleBadge role={m.role} /></td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${m.is_active ? 'text-emerald-600' : 'text-gray-400'}`}>
                      <span className={`h-1.5 w-1.5 rounded-full ${m.is_active ? 'bg-emerald-500' : 'bg-gray-300'}`} />
                      {m.is_active ? 'Actif' : 'Désactivé'}
                    </span>
                  </td>
                  <td className="px-4 py-3"><LastLogin date={m.last_login_at} /></td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {new Date(m.created_at).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <ActionsMenu
                      member={m}
                      isSelf={isSelf}
                      onView={() => setDrawerMember(m)}
                      onEdit={() => { setEditMember(m); setDrawerMember(null) }}
                      onReset={() => { setResetMember(m); setDrawerMember(null) }}
                      onDeactivate={() => { setDeactivateId(m.id); setDrawerMember(null) }}
                      onReactivate={() => { setReactivateId(m.id); setDrawerMember(null) }}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <div className="flex flex-col items-center py-16 gap-3 text-center">
            <div className="p-4 bg-gray-100 rounded-full">
              <Search className="h-6 w-6 text-gray-400" />
            </div>
            <p className="font-medium text-gray-700">Aucun membre trouvé</p>
            <p className="text-sm text-gray-500">Modifiez vos filtres ou invitez un nouveau membre.</p>
          </div>
        )}
      </Card>

      {/* Modals + Drawer */}
      {inviteOpen && <InviteModal onClose={() => setInviteOpen(false)} />}
      {editMember && <EditModal member={editMember} onClose={() => setEditMember(null)} />}
      {resetMember && <ResetPasswordModal member={resetMember} onClose={() => setResetMember(null)} />}

      {drawerMember && (
        <MemberDrawer
          member={drawerMember}
          isSelf={drawerMember.id === currentUser?.id}
          onClose={() => setDrawerMember(null)}
          onEdit={() => { setEditMember(drawerMember); setDrawerMember(null) }}
          onReset={() => { setResetMember(drawerMember); setDrawerMember(null) }}
          onDeactivate={() => { setDeactivateId(drawerMember.id); setDrawerMember(null) }}
          onReactivate={() => { setReactivateId(drawerMember.id); setDrawerMember(null) }}
        />
      )}

      {deactivateId && deactivateTarget && (
        <ConfirmModal
          title="Désactiver le membre"
          message={`Désactiver "${deactivateTarget.full_name ?? deactivateTarget.email}" ? Ils ne pourront plus se connecter.`}
          confirmLabel="Désactiver"
          danger
          loading={deactivate.isPending}
          onConfirm={() => deactivate.mutate(deactivateId)}
          onCancel={() => setDeactivateId(null)}
        />
      )}

      {reactivateId && reactivateTarget && (
        <ConfirmModal
          title="Réactiver le membre"
          message={`Réactiver "${reactivateTarget.full_name ?? reactivateTarget.email}" ? Ils pourront à nouveau se connecter.`}
          confirmLabel="Réactiver"
          loading={reactivate.isPending}
          onConfirm={() => reactivate.mutate(reactivateId)}
          onCancel={() => setReactivateId(null)}
        />
      )}
    </div>
  )
}
