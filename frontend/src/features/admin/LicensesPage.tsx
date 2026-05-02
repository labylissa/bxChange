import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CheckCircle,
  PauseCircle,
  RefreshCw,
  Send,
  Plus,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import {
  adminLicensesApi,
  type LicenseCreate,
  type TenantUsageAdmin,
} from '@/lib/api/billing'
import { adminApi } from '@/lib/api/admin'

type LicenseStatus = 'trial' | 'active' | 'expired' | 'suspended'

function StatusPill({ status }: { status: LicenseStatus }) {
  const cfg: Record<LicenseStatus, string> = {
    trial: 'bg-orange-100 text-orange-700',
    active: 'bg-green-100 text-green-700',
    expired: 'bg-red-100 text-red-700',
    suspended: 'bg-red-200 text-red-900',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${cfg[status] ?? cfg.trial}`}>
      {status}
    </span>
  )
}

function LicenseFormModal({
  tenants,
  onClose,
  onCreated,
}: {
  tenants: { id: string; name: string }[]
  onClose: () => void
  onCreated: () => void
}) {
  const [form, setForm] = useState<LicenseCreate>({
    tenant_id: tenants[0]?.id ?? '',
    executions_limit: 10000,
    connectors_limit: 20,
    contract_start: new Date().toISOString().split('T')[0] + 'T00:00:00',
    contract_end: new Date(Date.now() + 365 * 86_400_000).toISOString().split('T')[0] + 'T00:00:00',
    annual_price_cents: 0,
    notes: '',
  })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await adminLicensesApi.createLicense(form)
      onCreated()
      onClose()
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Erreur lors de la création')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-4">Créer une licence</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Tenant</label>
            <select
              className="w-full border rounded-lg px-3 py-2 text-sm"
              value={form.tenant_id}
              onChange={(e) => setForm((f) => ({ ...f, tenant_id: e.target.value }))}
            >
              {tenants.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Exécutions/mois</label>
              <input
                type="number"
                className="w-full border rounded-lg px-3 py-2 text-sm"
                value={form.executions_limit}
                onChange={(e) => setForm((f) => ({ ...f, executions_limit: +e.target.value }))}
                min={1}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Connecteurs max</label>
              <input
                type="number"
                className="w-full border rounded-lg px-3 py-2 text-sm"
                value={form.connectors_limit}
                onChange={(e) => setForm((f) => ({ ...f, connectors_limit: +e.target.value }))}
                min={1}
                required
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Début contrat</label>
              <input
                type="date"
                className="w-full border rounded-lg px-3 py-2 text-sm"
                value={form.contract_start.split('T')[0]}
                onChange={(e) =>
                  setForm((f) => ({ ...f, contract_start: e.target.value + 'T00:00:00' }))
                }
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Fin contrat</label>
              <input
                type="date"
                className="w-full border rounded-lg px-3 py-2 text-sm"
                value={form.contract_end.split('T')[0]}
                onChange={(e) =>
                  setForm((f) => ({ ...f, contract_end: e.target.value + 'T00:00:00' }))
                }
                required
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Prix annuel (€ centimes, ex : 120000 = 1 200€)
            </label>
            <input
              type="number"
              className="w-full border rounded-lg px-3 py-2 text-sm"
              value={form.annual_price_cents}
              onChange={(e) => setForm((f) => ({ ...f, annual_price_cents: +e.target.value }))}
              min={0}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Notes internes</label>
            <textarea
              className="w-full border rounded-lg px-3 py-2 text-sm"
              rows={2}
              value={form.notes ?? ''}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">
              Annuler
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-sm font-medium bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
            >
              {submitting ? 'Création…' : 'Créer la licence'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function InvoiceModal({
  tenant,
  onClose,
}: {
  tenant: TenantUsageAdmin
  onClose: () => void
}) {
  const [form, setForm] = useState({
    description: `Licence annuelle bxChange — ${tenant.tenant_name}`,
    amount_euros: (tenant.annual_price_cents / 100).toString(),
    due_date: new Date(Date.now() + 30 * 86_400_000).toISOString().split('T')[0],
  })
  const [result, setResult] = useState<{ invoice_id: string; invoice_url: string | null } | null>(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const res = await adminLicensesApi.createInvoice({
        tenant_id: tenant.tenant_id,
        description: form.description,
        amount_cents: Math.round(parseFloat(form.amount_euros) * 100),
        due_date: form.due_date,
      })
      setResult(res)
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Erreur Stripe')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-4">
          Envoyer facture — {tenant.tenant_name}
        </h2>

        {result ? (
          <div className="text-center space-y-4">
            <p className="text-green-700 font-semibold">Facture envoyée avec succès</p>
            {result.invoice_url && (
              <a
                href={result.invoice_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-brand-600 underline text-sm"
              >
                Voir la facture Stripe
              </a>
            )}
            <button
              onClick={onClose}
              className="block mx-auto px-4 py-2 text-sm bg-gray-100 rounded-lg hover:bg-gray-200"
            >
              Fermer
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <input
                type="text"
                className="w-full border rounded-lg px-3 py-2 text-sm"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Montant (€)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                  value={form.amount_euros}
                  onChange={(e) => setForm((f) => ({ ...f, amount_euros: e.target.value }))}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Échéance</label>
                <input
                  type="date"
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                  value={form.due_date}
                  onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
                  required
                />
              </div>
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600">
                Annuler
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
              >
                <Send className="h-4 w-4" />
                {submitting ? 'Envoi…' : 'Envoyer via Stripe'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

function TenantRow({ tenant }: { tenant: TenantUsageAdmin }) {
  const [showInvoice, setShowInvoice] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const exePct = tenant.executions_limit > 0
    ? (tenant.executions_used / tenant.executions_limit) * 100
    : 0

  return (
    <>
      <tr className="border-b hover:bg-gray-50 transition-colors">
        <td className="py-3 px-4 text-sm font-medium text-gray-900">{tenant.tenant_name}</td>
        <td className="py-3 px-4">
          <StatusPill status={tenant.license_status as LicenseStatus} />
        </td>
        <td className="py-3 px-4 text-sm text-gray-700">
          <div className="flex items-center gap-2">
            <span>{tenant.executions_used.toLocaleString()} / {tenant.executions_limit.toLocaleString()}</span>
            <div className="h-1.5 w-16 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${exePct >= 90 ? 'bg-red-500' : exePct >= 75 ? 'bg-orange-400' : 'bg-green-500'}`}
                style={{ width: `${Math.min(exePct, 100)}%` }}
              />
            </div>
          </div>
        </td>
        <td className="py-3 px-4 text-sm text-gray-700">
          {tenant.connectors_count} / {tenant.connectors_limit}
        </td>
        <td className="py-3 px-4 text-sm text-gray-500">
          {tenant.contract_end
            ? new Date(tenant.contract_end).toLocaleDateString('fr-FR')
            : '—'}
        </td>
        <td className="py-3 px-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowInvoice(true)}
              className="p-1.5 text-gray-400 hover:text-brand-600 rounded"
              title="Envoyer facture"
            >
              <Send className="h-4 w-4" />
            </button>
            <button
              onClick={() => setExpanded((e) => !e)}
              className="p-1.5 text-gray-400 hover:text-gray-700 rounded"
              title="Voir les licences"
            >
              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
          </div>
        </td>
      </tr>
      {showInvoice && (
        <InvoiceModal tenant={tenant} onClose={() => setShowInvoice(false)} />
      )}
    </>
  )
}

export function LicensesPage() {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)

  const { data: licenses = [] } = useQuery({
    queryKey: ['admin-all-licenses'],
    queryFn: adminLicensesApi.listLicenses,
  })

  const { data: tenants = [] } = useQuery({
    queryKey: ['admin-tenants'],
    queryFn: adminApi.getTenants,
  })

  const tenantUsageQueries = useQuery({
    queryKey: ['admin-tenants-usage'],
    queryFn: async () => {
      const all = await Promise.allSettled(
        tenants.map((t) => adminLicensesApi.getTenantUsage(t.id))
      )
      return all.flatMap((r) => (r.status === 'fulfilled' ? [r.value] : []))
    },
    enabled: tenants.length > 0,
  })

  const usages: TenantUsageAdmin[] = tenantUsageQueries.data ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Licences clients</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-brand-600 text-white rounded-lg hover:bg-brand-700"
        >
          <Plus className="h-4 w-4" />
          Créer une licence
        </button>
      </div>

      {/* Tenants table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                {['Tenant', 'Statut', 'Exécutions', 'Connecteurs', 'Fin contrat', 'Actions'].map(
                  (h) => (
                    <th
                      key={h}
                      className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide"
                    >
                      {h}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {tenantUsageQueries.isLoading ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-gray-400 text-sm">
                    Chargement…
                  </td>
                </tr>
              ) : usages.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-gray-400 text-sm">
                    Aucun tenant
                  </td>
                </tr>
              ) : (
                usages.map((u) => <TenantRow key={u.tenant_id} tenant={u} />)
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Licenses list */}
      {licenses.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Toutes les licences ({licenses.length})
          </h2>
          <div className="space-y-2">
            {licenses.map((lic) => (
              <div
                key={lic.id}
                className="flex items-center justify-between p-3 border rounded-lg text-sm"
              >
                <div className="flex items-center gap-3">
                  <StatusPill status={lic.status as LicenseStatus} />
                  <span className="font-mono text-xs text-gray-500">{lic.license_key}</span>
                  <span className="text-gray-700">
                    {lic.executions_limit.toLocaleString()} exec ·{' '}
                    {lic.connectors_limit} connecteurs ·{' '}
                    {(lic.annual_price_cents / 100).toLocaleString('fr-FR', {
                      style: 'currency',
                      currency: 'EUR',
                    })}
                    /an
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {lic.status !== 'active' && (
                    <button
                      onClick={() => adminLicensesApi.activateLicense(lic.id).then(() => qc.invalidateQueries({ queryKey: ['admin-all-licenses'] }))}
                      className="p-1.5 text-green-600 hover:bg-green-50 rounded"
                      title="Activer"
                    >
                      <CheckCircle className="h-4 w-4" />
                    </button>
                  )}
                  {lic.status === 'active' && (
                    <button
                      onClick={() => {
                        const reason = window.prompt('Raison de suspension ?')
                        if (reason) adminLicensesApi.suspendLicense(lic.id, reason).then(() => qc.invalidateQueries({ queryKey: ['admin-all-licenses'] }))
                      }}
                      className="p-1.5 text-orange-600 hover:bg-orange-50 rounded"
                      title="Suspendre"
                    >
                      <PauseCircle className="h-4 w-4" />
                    </button>
                  )}
                  <button
                    onClick={() => adminLicensesApi.renewLicense(lic.id).then(() => qc.invalidateQueries({ queryKey: ['admin-all-licenses'] }))}
                    className="p-1.5 text-blue-600 hover:bg-blue-50 rounded"
                    title="Renouveler +1 an"
                  >
                    <RefreshCw className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {showCreate && (
        <LicenseFormModal
          tenants={tenants.map((t) => ({ id: t.id, name: t.name }))}
          onClose={() => setShowCreate(false)}
          onCreated={() => qc.invalidateQueries({ queryKey: ['admin-all-licenses'] })}
        />
      )}
    </div>
  )
}
