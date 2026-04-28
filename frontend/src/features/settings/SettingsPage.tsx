import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { User, Lock, AlertTriangle } from 'lucide-react'
import { authApi } from '@/lib/api/auth'
import { useAuthStore } from '@/stores/authStore'
import { useToast } from '@/stores/toastStore'
import { Card } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { ConfirmModal } from '@/components/ui/ConfirmModal'

export function SettingsPage() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const setUser = useAuthStore((s) => s.setUser)
  const navigate = useNavigate()
  const toast = useToast()

  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)

  useEffect(() => { document.title = 'bxChange — Paramètres' }, [])

  const updateProfile = useMutation({
    mutationFn: () => authApi.updateProfile({ full_name: fullName, email }),
    onSuccess: (data) => {
      setUser({ ...user!, ...data })
      toast.success('Profil mis à jour')
    },
    onError: () => toast.error('Cette fonctionnalité sera disponible prochainement'),
  })

  const changePassword = useMutation({
    mutationFn: () => {
      if (newPw !== confirmPw) throw new Error('Les mots de passe ne correspondent pas')
      if (newPw.length < 8) throw new Error('Le nouveau mot de passe doit faire au moins 8 caractères')
      return authApi.changePassword({ current_password: currentPw, new_password: newPw })
    },
    onSuccess: () => {
      setCurrentPw(''); setNewPw(''); setConfirmPw('')
      toast.success('Mot de passe modifié')
    },
    onError: (err: Error) => toast.error(err.message || 'Erreur lors du changement de mot de passe'),
  })

  const deleteAccount = useMutation({
    mutationFn: () => authApi.deleteAccount(),
    onSuccess: () => {
      logout()
      navigate('/login')
      toast.info('Compte supprimé')
    },
    onError: () => toast.error('Cette fonctionnalité sera disponible prochainement'),
  })

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <h1 className="text-xl font-semibold text-gray-900">Paramètres</h1>

      {/* ── Profil ── */}
      <Card>
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 bg-brand-50 rounded-lg">
            <User className="h-5 w-5 text-brand-600" />
          </div>
          <h2 className="font-semibold text-gray-800">Profil</h2>
        </div>
        <div className="flex flex-col gap-4">
          <Input
            label="Nom complet"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <div className="flex justify-end pt-1">
            <Button
              onClick={() => updateProfile.mutate()}
              loading={updateProfile.isPending}
              disabled={!fullName.trim() || !email.trim()}
            >
              Enregistrer
            </Button>
          </div>
        </div>
      </Card>

      {/* ── Mot de passe ── */}
      <Card>
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 bg-yellow-50 rounded-lg">
            <Lock className="h-5 w-5 text-yellow-600" />
          </div>
          <h2 className="font-semibold text-gray-800">Mot de passe</h2>
        </div>
        <div className="flex flex-col gap-4">
          <Input
            label="Mot de passe actuel"
            type="password"
            autoComplete="current-password"
            value={currentPw}
            onChange={(e) => setCurrentPw(e.target.value)}
          />
          <Input
            label="Nouveau mot de passe"
            type="password"
            autoComplete="new-password"
            value={newPw}
            onChange={(e) => setNewPw(e.target.value)}
          />
          <Input
            label="Confirmer le nouveau mot de passe"
            type="password"
            autoComplete="new-password"
            value={confirmPw}
            onChange={(e) => setConfirmPw(e.target.value)}
            error={confirmPw && newPw !== confirmPw ? 'Les mots de passe ne correspondent pas' : undefined}
          />
          <div className="flex justify-end pt-1">
            <Button
              onClick={() => changePassword.mutate()}
              loading={changePassword.isPending}
              disabled={!currentPw || !newPw || !confirmPw}
            >
              Changer le mot de passe
            </Button>
          </div>
        </div>
      </Card>

      {/* ── Zone danger ── */}
      <Card className="border-red-200">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-red-50 rounded-lg">
            <AlertTriangle className="h-5 w-5 text-red-600" />
          </div>
          <h2 className="font-semibold text-red-700">Zone de danger</h2>
        </div>
        <p className="text-sm text-gray-600 mb-4">
          La suppression du compte est irréversible. Toutes vos données, connecteurs et clés API seront
          définitivement supprimés.
        </p>
        <Button variant="danger" onClick={() => setDeleteOpen(true)}>
          Supprimer mon compte
        </Button>
      </Card>

      {deleteOpen && (
        <ConfirmModal
          title="Supprimer votre compte ?"
          message="Cette action est irréversible. Tous vos connecteurs, logs et clés API seront supprimés définitivement."
          confirmLabel="Supprimer définitivement"
          danger
          loading={deleteAccount.isPending}
          onConfirm={() => deleteAccount.mutate()}
          onCancel={() => setDeleteOpen(false)}
        />
      )}
    </div>
  )
}
