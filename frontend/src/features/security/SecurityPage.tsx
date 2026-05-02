import { useState } from 'react'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import {
  Shield, Plus, Trash2, RefreshCw, Copy, Check,
  Clock, AlertTriangle, Info, X
} from 'lucide-react'
import {
  oauth2ClientsApi, mtlsCertificatesApi,
  type OAuth2ClientCreated,
  type OAuth2Scope,
} from '@/lib/api/security'

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtDate(d: string | null) {
  if (!d) return '—'
  return new Date(d).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}

function ttlLabel(s: number): string {
  if (s < 3600) return `${s / 60} min`
  if (s < 86400) return `${s / 3600} h`
  return `${s / 86400} j`
}

const SCOPES: { value: OAuth2Scope; label: string }[] = [
  { value: 'execute:connectors', label: 'Exécuter des connecteurs' },
  { value: 'execute:pipelines', label: 'Exécuter des pipelines' },
  { value: 'read:results', label: "Lire l'historique des exécutions" },
]

const TTL_OPTIONS = [
  { value: 900, label: '15 min' },
  { value: 3600, label: '1 heure' },
  { value: 14400, label: '4 heures' },
  { value: 86400, label: '24 heures' },
]

// ── Copy button ───────────────────────────────────────────────────────────────

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handle = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button onClick={handle} className="p-1 text-gray-400 hover:text-gray-700 transition-colors">
      {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
    </button>
  )
}

// ── Secret revealed modal ─────────────────────────────────────────────────────

function SecretModal({ data, onClose }: { data: OAuth2ClientCreated; onClose: () => void }) {
  const curlSnippet = `curl -X POST https://app.bxchange.io/api/v1/oauth2/token \\
  -H "Content-Type: application/x-www-form-urlencoded" \\
  -d "grant_type=client_credentials" \\
  -d "client_id=${data.client_id}" \\
  -d "client_secret=${data.client_secret}" \\
  -d "scope=${data.scopes.join(' ')}"`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Client OAuth2 créé</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-6 space-y-4">
          <div className="flex items-start gap-3 p-3 bg-red-50 border border-red-200 rounded-lg">
            <AlertTriangle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-700 font-medium">
              Ce secret ne sera plus jamais affiché. Copiez-le maintenant.
            </p>
          </div>

          <div>
            <p className="text-xs text-gray-500 mb-1">Client ID</p>
            <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
              <code className="text-sm flex-1 break-all">{data.client_id}</code>
              <CopyBtn text={data.client_id} />
            </div>
          </div>

          <div>
            <p className="text-xs text-gray-500 mb-1">Client Secret</p>
            <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
              <code className="text-sm flex-1 break-all font-bold text-red-700">{data.client_secret}</code>
              <CopyBtn text={data.client_secret} />
            </div>
          </div>

          <div>
            <p className="text-xs text-gray-500 mb-1">Exemple curl — obtenir un token</p>
            <div className="relative bg-gray-900 rounded-lg p-3">
              <pre className="text-xs text-green-400 whitespace-pre-wrap break-all">{curlSnippet}</pre>
              <div className="absolute top-2 right-2">
                <CopyBtn text={curlSnippet} />
              </div>
            </div>
          </div>
        </div>
        <div className="px-6 py-4 border-t border-gray-100 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
          >
            J'ai copié le secret
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Create OAuth2 Client modal ────────────────────────────────────────────────

function CreateClientModal({ onClose, onCreated }: { onClose: () => void; onCreated: (c: OAuth2ClientCreated) => void }) {
  const [name, setName] = useState('')
  const [scopes, setScopes] = useState<OAuth2Scope[]>(['execute:connectors'])
  const [ttl, setTtl] = useState(3600)
  const [ipInput, setIpInput] = useState('')
  const [ips, setIps] = useState<string[]>([])

  const mutation = useMutation({
    mutationFn: () => oauth2ClientsApi.create({ name, scopes, token_ttl_seconds: ttl, allowed_ips: ips }),
    onSuccess: onCreated,
  })

  const toggleScope = (s: OAuth2Scope) =>
    setScopes((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s])

  const addIp = () => {
    const v = ipInput.trim()
    if (v && !ips.includes(v)) { setIps([...ips, v]); setIpInput('') }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Nouveau client OAuth2</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nom</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="ex : Système CovéaProd"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Scopes</label>
            <div className="space-y-2">
              {SCOPES.map(({ value, label }) => (
                <label key={value} className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={scopes.includes(value)}
                    onChange={() => toggleScope(value)}
                    className="h-4 w-4 text-brand-600 rounded border-gray-300"
                  />
                  <span className="text-sm text-gray-700">{label}</span>
                  <code className="text-xs text-gray-400 font-mono">{value}</code>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Durée de vie du token</label>
            <div className="flex gap-2 flex-wrap">
              {TTL_OPTIONS.map(({ value, label }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setTtl(value)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                    ttl === value
                      ? 'bg-brand-600 text-white border-brand-600'
                      : 'border-gray-300 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              IPs autorisées <span className="text-gray-400 font-normal">(optionnel, CIDR supporté)</span>
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={ipInput}
                onChange={(e) => setIpInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addIp()}
                placeholder="192.168.1.0/24"
                className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <button type="button" onClick={addIp} className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">
                Ajouter
              </button>
            </div>
            {ips.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {ips.map((ip) => (
                  <span key={ip} className="flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-full">
                    {ip}
                    <button onClick={() => setIps(ips.filter((x) => x !== ip))}><X className="h-3 w-3" /></button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Annuler</button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!name || scopes.length === 0 || mutation.isPending}
            className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50"
          >
            {mutation.isPending ? 'Création…' : 'Créer le client'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Add mTLS cert modal ───────────────────────────────────────────────────────

function AddCertModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('')
  const [pem, setPem] = useState('')
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => mtlsCertificatesApi.create({ name, certificate_pem: pem }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mtls-certs'] })
      onClose()
    },
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Enregistrer un certificat mTLS</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nom</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="ex : BanqueXYZ Production"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Certificat PEM</label>
            <textarea
              value={pem}
              onChange={(e) => setPem(e.target.value)}
              rows={8}
              placeholder="-----BEGIN CERTIFICATE-----&#10;MIICxx...&#10;-----END CERTIFICATE-----"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          {mutation.isError && (
            <p className="text-sm text-red-600">
              {(mutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Erreur lors de l\'enregistrement'}
            </p>
          )}
        </div>
        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Annuler</button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!name || !pem || mutation.isPending}
            className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50"
          >
            {mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── OAuth2 Clients Tab ────────────────────────────────────────────────────────

function OAuth2Tab() {
  const qc = useQueryClient()
  const { data: clients = [], isLoading } = useQuery({ queryKey: ['oauth2-clients'], queryFn: oauth2ClientsApi.list })
  const [showCreate, setShowCreate] = useState(false)
  const [revealed, setRevealed] = useState<OAuth2ClientCreated | null>(null)

  const deleteMutation = useMutation({
    mutationFn: (id: string) => oauth2ClientsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['oauth2-clients'] }),
  })

  const rotateMutation = useMutation({
    mutationFn: (id: string) => oauth2ClientsApi.rotate(id),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['oauth2-clients'] })
      setRevealed(data)
    },
  })

  return (
    <div className="space-y-4">
      {revealed && <SecretModal data={revealed} onClose={() => setRevealed(null)} />}
      {showCreate && (
        <CreateClientModal
          onClose={() => setShowCreate(false)}
          onCreated={(c) => {
            qc.invalidateQueries({ queryKey: ['oauth2-clients'] })
            setShowCreate(false)
            setRevealed(c)
          }}
        />
      )}

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-900">Clients OAuth2 Machine-to-Machine</h2>
          <p className="text-sm text-gray-500 mt-0.5">Standard Client Credentials (RFC 6749 §4.4)</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
        >
          <Plus className="h-4 w-4" /> Nouveau client
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-8 text-gray-400">Chargement…</div>
      ) : clients.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
          <Shield className="h-10 w-10 text-gray-200 mx-auto mb-3" />
          <p className="text-gray-500 font-medium">Aucun client OAuth2</p>
          <p className="text-sm text-gray-400 mt-1">Créez un client pour les intégrations machine-to-machine</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Nom</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Client ID</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Scopes</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">TTL</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Dernière utilisation</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Statut</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {clients.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{c.name}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <code className="text-xs text-gray-600">{c.client_id}</code>
                      <CopyBtn text={c.client_id} />
                    </div>
                    <p className="text-xs text-gray-400 mt-0.5">secret: {c.client_secret_preview}…</p>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {c.scopes.map((s) => (
                        <span key={s} className="px-1.5 py-0.5 bg-blue-50 text-blue-700 text-xs rounded font-mono">{s}</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{ttlLabel(c.token_ttl_seconds)}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{fmtDate(c.last_used_at)}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${c.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {c.is_active ? 'Actif' : 'Inactif'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 justify-end">
                      <button
                        onClick={() => { if (confirm(`Régénérer le secret de "${c.name}" ? L'ancien secret sera invalide.`)) rotateMutation.mutate(c.id) }}
                        className="p-1.5 text-gray-400 hover:text-amber-600 hover:bg-amber-50 rounded"
                        title="Régénérer le secret"
                      >
                        <RefreshCw className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => { if (confirm(`Supprimer le client "${c.name}" ?`)) deleteMutation.mutate(c.id) }}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                        title="Révoquer"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg flex gap-3">
        <Info className="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-blue-700">
          <p className="font-medium mb-1">Comment utiliser les tokens OAuth2 ?</p>
          <p>1. Appelez <code className="bg-blue-100 px-1 rounded">POST /api/v1/oauth2/token</code> avec vos credentials pour obtenir un Bearer token.</p>
          <p className="mt-1">2. Utilisez ce token via <code className="bg-blue-100 px-1 rounded">Authorization: Bearer {'{token}'}</code> sur les endpoints <code className="bg-blue-100 px-1 rounded">/execute</code>.</p>
        </div>
      </div>
    </div>
  )
}

// ── mTLS Tab ──────────────────────────────────────────────────────────────────

function MTLSTab() {
  const qc = useQueryClient()
  const { data: certs = [], isLoading } = useQuery({ queryKey: ['mtls-certs'], queryFn: mtlsCertificatesApi.list })
  const [showAdd, setShowAdd] = useState(false)

  const deleteMutation = useMutation({
    mutationFn: (id: string) => mtlsCertificatesApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mtls-certs'] }),
  })

  const isExpired = (d: string) => new Date(d) < new Date()

  return (
    <div className="space-y-4">
      {showAdd && <AddCertModal onClose={() => setShowAdd(false)} />}

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-900">Certificats mTLS</h2>
          <p className="text-sm text-gray-500 mt-0.5">Authentification par certificat client TLS</p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
        >
          <Plus className="h-4 w-4" /> Enregistrer un certificat
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-8 text-gray-400">Chargement…</div>
      ) : certs.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
          <Shield className="h-10 w-10 text-gray-200 mx-auto mb-3" />
          <p className="text-gray-500 font-medium">Aucun certificat mTLS</p>
          <p className="text-sm text-gray-400 mt-1">Enregistrez un certificat client pour activer l'authentification mTLS</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Nom</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Subject DN</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Fingerprint</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Valide jusqu'au</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Dernière utilisation</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {certs.map((cert) => (
                <tr key={cert.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{cert.name}</td>
                  <td className="px-4 py-3 text-xs text-gray-600 max-w-xs truncate" title={cert.subject_dn}>
                    {cert.subject_dn}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <code className="text-xs text-gray-500">{cert.fingerprint_sha256.slice(0, 16)}…</code>
                      <CopyBtn text={cert.fingerprint_sha256} />
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {isExpired(cert.valid_until) ? (
                      <span className="inline-flex items-center gap-1 text-xs text-red-600">
                        <AlertTriangle className="h-3 w-3" /> Expiré
                      </span>
                    ) : (
                      <span className="text-xs text-gray-600 flex items-center gap-1">
                        <Clock className="h-3 w-3 text-gray-400" />
                        {fmtDate(cert.valid_until)}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{fmtDate(cert.last_used_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end">
                      <button
                        onClick={() => { if (confirm(`Révoquer le certificat "${cert.name}" ?`)) deleteMutation.mutate(cert.id) }}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                        title="Révoquer"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg flex gap-3">
        <Info className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-amber-700">
          <p className="font-medium">Configuration reverse proxy requise</p>
          <p className="mt-1">
            Le mTLS nécessite que votre reverse proxy (nginx/traefik) extraie le fingerprint du certificat
            client TLS et l'injecte dans le header <code className="bg-amber-100 px-1 rounded">X-Client-Cert-Fingerprint</code>.
            Contactez notre équipe technique pour l'activation :{' '}
            <a href="mailto:support@bxchange.io" className="underline">support@bxchange.io</a>
          </p>
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

type Tab = 'oauth2' | 'mtls'

export function SecurityPage() {
  const [tab, setTab] = useState<Tab>('oauth2')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Sécurité</h1>
        <p className="text-sm text-gray-500 mt-1">Authentification OAuth2 et certificats mTLS pour vos intégrations</p>
      </div>

      <div className="flex gap-1 border-b border-gray-200">
        {([['oauth2', 'OAuth2 Clients'], ['mtls', 'Certificats mTLS']] as [Tab, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === key
                ? 'border-brand-600 text-brand-700'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'oauth2' ? <OAuth2Tab /> : <MTLSTab />}
    </div>
  )
}
