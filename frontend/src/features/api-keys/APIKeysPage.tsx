import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Copy, Check, Key, Trash2, ShieldOff } from 'lucide-react'
import type { ApiKeyCreated } from '@/lib/api/apiKeys'
import { apiKeysApi } from '@/lib/api/apiKeys'
import { connectorsApi } from '@/lib/api/connectors'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { TableSkeleton } from '@/components/ui/Skeleton'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { useToast } from '@/stores/toastStore'

function relTime(iso: string) {
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
}

// ── Create modal ─────────────────────────────────────────────────────────────
function CreateModal({ onClose, onCreated }: { onClose: () => void; onCreated: (k: ApiKeyCreated) => void }) {
  const toast = useToast()
  const { data: connectors } = useQuery({ queryKey: ['connectors'], queryFn: connectorsApi.getConnectors })
  const [name, setName] = useState('')
  const [rateLimit, setRateLimit] = useState('1000')
  const [expiresAt, setExpiresAt] = useState('')
  const [selectedConnectors, setSelectedConnectors] = useState<string[]>([])

  const create = useMutation({
    mutationFn: () => apiKeysApi.createApiKey({
      name,
      rate_limit: parseInt(rateLimit, 10) || 1000,
      expires_at: expiresAt ? new Date(expiresAt).toISOString() : undefined,
      permissions: selectedConnectors.length
        ? { connector_ids: selectedConnectors }
        : undefined,
    }),
    onSuccess: (data) => { toast.success('Clé API créée'); onCreated(data) },
    onError: () => toast.error('Erreur lors de la création'),
  })

  function toggleConnector(id: string) {
    setSelectedConnectors((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md flex flex-col gap-5 p-6">
        <h2 className="font-semibold text-gray-900 text-lg">Nouvelle clé API</h2>

        <div className="flex flex-col gap-4">
          <Input
            label="Nom"
            placeholder="ex: Service facturation"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Input
            label="Rate limit (req/heure)"
            type="number"
            min={1}
            value={rateLimit}
            onChange={(e) => setRateLimit(e.target.value)}
          />
          <div>
            <label className="text-sm font-medium text-gray-700">Expiration (optionnel)</label>
            <input
              type="date"
              className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              min={new Date().toISOString().split('T')[0]}
            />
          </div>

          {connectors && connectors.length > 0 && (
            <div>
              <label className="text-sm font-medium text-gray-700 mb-2 block">
                Connecteurs autorisés{' '}
                <span className="font-normal text-gray-400">(vide = tous)</span>
              </label>
              <div className="flex flex-col gap-1.5 max-h-40 overflow-y-auto border border-gray-200 rounded-lg p-2">
                {connectors.map((c) => (
                  <label key={c.id} className="flex items-center gap-2 cursor-pointer text-sm">
                    <input
                      type="checkbox"
                      checked={selectedConnectors.includes(c.id)}
                      onChange={() => toggleConnector(c.id)}
                      className="rounded text-brand-600"
                    />
                    <span>{c.name}</span>
                    <span className="text-xs text-gray-400 ml-auto">{c.type.toUpperCase()}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 pt-1">
          <Button variant="ghost" onClick={onClose} disabled={create.isPending}>Annuler</Button>
          <Button onClick={() => create.mutate()} loading={create.isPending} disabled={!name.trim()}>
            Créer la clé
          </Button>
        </div>
      </div>
    </div>
  )
}

// ── Raw key modal ─────────────────────────────────────────────────────────────
function RawKeyModal({ rawKey, onClose }: { rawKey: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false)

  function copy() {
    navigator.clipboard.writeText(rawKey).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col gap-5 p-6">
        <div className="bg-orange-50 border-2 border-orange-300 rounded-xl p-4 flex flex-col gap-3">
          <div className="flex items-center gap-2 text-orange-700 font-semibold">
            <ShieldOff className="h-5 w-5" />
            Copiez cette clé maintenant — elle ne sera plus affichée
          </div>
          <div className="bg-white rounded-lg border border-orange-200 px-4 py-3 font-mono text-sm break-all text-gray-900 select-all">
            {rawKey}
          </div>
          <Button onClick={copy} variant="secondary" className="self-start flex items-center gap-2">
            {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
            {copied ? 'Copié !' : 'Copier dans le presse-papier'}
          </Button>
        </div>
        <p className="text-xs text-gray-500 text-center">
          Cette clé sera hashée et stockée de manière sécurisée. Après fermeture de cette fenêtre,
          il sera impossible de la récupérer.
        </p>
        <Button onClick={onClose} className="w-full">J'ai copié ma clé — Fermer</Button>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export function APIKeysPage() {
  const qc = useQueryClient()
  const toast = useToast()
  const [createOpen, setCreateOpen] = useState(false)
  const [rawKey, setRawKey] = useState<string | null>(null)
  const [revokeId, setRevokeId] = useState<string | null>(null)

  useEffect(() => { document.title = 'bxChange — API Keys' }, [])

  const { data: apiKeys, isLoading } = useQuery({
    queryKey: ['api-keys'],
    queryFn: apiKeysApi.getApiKeys,
  })

  const revoke = useMutation({
    mutationFn: (id: string) => apiKeysApi.revokeApiKey(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['api-keys'] })
      toast.success('Clé révoquée')
      setRevokeId(null)
    },
    onError: () => toast.error('Erreur lors de la révocation'),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">API Keys</h1>
        <Button onClick={() => setCreateOpen(true)} className="flex items-center gap-2">
          <Plus className="h-4 w-4" /> Nouvelle clé API
        </Button>
      </div>

      <Card padding="none">
        {isLoading && <TableSkeleton />}

        {!isLoading && apiKeys?.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
            <div className="p-4 bg-gray-100 rounded-full">
              <Key className="h-7 w-7 text-gray-400" />
            </div>
            <p className="font-medium text-gray-700">Aucune clé API</p>
            <p className="text-sm text-gray-500">Créez une clé pour accéder à l'API depuis vos applications.</p>
          </div>
        )}

        {!isLoading && apiKeys && apiKeys.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left">
                  <th className="px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Nom</th>
                  <th className="px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Rate limit</th>
                  <th className="px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Expiration</th>
                  <th className="px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Statut</th>
                  <th className="px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Créée le</th>
                  <th className="px-6 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {apiKeys.map((k) => (
                  <tr key={k.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 font-medium text-gray-900">{k.name}</td>
                    <td className="px-6 py-4 text-gray-600">
                      {k.rate_limit?.toLocaleString('fr-FR') ?? '∞'} / h
                    </td>
                    <td className="px-6 py-4 text-gray-600">
                      {k.expires_at ? relTime(k.expires_at) : <span className="text-gray-400">Jamais</span>}
                    </td>
                    <td className="px-6 py-4">
                      <Badge variant={k.is_active ? 'green' : 'gray'}>
                        {k.is_active ? 'Active' : 'Révoquée'}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 text-gray-500">{relTime(k.created_at)}</td>
                    <td className="px-6 py-4">
                      {k.is_active && (
                        <button
                          onClick={() => setRevokeId(k.id)}
                          className="text-gray-400 hover:text-red-500 transition-colors"
                          title="Révoquer"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {createOpen && (
        <CreateModal
          onClose={() => setCreateOpen(false)}
          onCreated={(k) => {
            setCreateOpen(false)
            setRawKey(k.raw_key)
            qc.invalidateQueries({ queryKey: ['api-keys'] })
          }}
        />
      )}

      {rawKey && (
        <RawKeyModal rawKey={rawKey} onClose={() => setRawKey(null)} />
      )}

      {revokeId && (
        <ConfirmModal
          title="Révoquer cette clé API ?"
          message="La clé sera désactivée immédiatement. Les applications qui l'utilisent perdront leur accès."
          confirmLabel="Révoquer"
          danger
          loading={revoke.isPending}
          onConfirm={() => revoke.mutate(revokeId)}
          onCancel={() => setRevokeId(null)}
        />
      )}
    </div>
  )
}
