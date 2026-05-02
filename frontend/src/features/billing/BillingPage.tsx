import { useQuery } from '@tanstack/react-query'
import { CreditCard, ExternalLink, FileText, Mail, RefreshCw } from 'lucide-react'
import { billingApi, type InvoiceItem, type LicenseStatus } from '@/lib/api/billing'

function StatusBadge({ status }: { status: LicenseStatus }) {
  const cfg: Record<LicenseStatus, { label: string; cls: string }> = {
    trial: { label: 'Essai gratuit', cls: 'bg-orange-100 text-orange-700' },
    active: { label: 'Actif', cls: 'bg-green-100 text-green-700' },
    expired: { label: 'Expiré', cls: 'bg-red-100 text-red-700' },
    suspended: { label: 'Suspendu', cls: 'bg-red-200 text-red-900' },
  }
  const { label, cls } = cfg[status] ?? cfg.trial
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${cls}`}>
      {label}
    </span>
  )
}

function QuotaBar({
  label,
  used,
  limit,
  pct,
}: {
  label: string
  used: number
  limit: number
  pct: number
}) {
  const color =
    pct >= 95
      ? 'bg-red-500'
      : pct >= 80
      ? 'bg-orange-400'
      : 'bg-brand-500'

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-sm">
        <span className="font-medium text-gray-700">{label}</span>
        <span className="text-gray-500">
          {used.toLocaleString()} / {limit.toLocaleString()}
        </span>
      </div>
      <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <p className="text-xs text-gray-500">{pct.toFixed(1)}% utilisé</p>
    </div>
  )
}

function InvoiceRow({ inv }: { inv: InvoiceItem }) {
  const statusCls: Record<string, string> = {
    paid: 'text-green-600',
    open: 'text-orange-600',
    void: 'text-gray-400',
    draft: 'text-gray-400',
    uncollectible: 'text-red-600',
  }
  return (
    <tr className="border-b last:border-0">
      <td className="py-3 pr-4 text-sm text-gray-700">
        {new Date(inv.date).toLocaleDateString('fr-FR')}
      </td>
      <td className="py-3 pr-4 text-sm text-gray-700 max-w-xs truncate">{inv.description || '—'}</td>
      <td className="py-3 pr-4 text-sm font-medium text-gray-900">
        {(inv.amount_cents / 100).toLocaleString('fr-FR', { style: 'currency', currency: inv.currency?.toUpperCase() || 'EUR' })}
      </td>
      <td className="py-3 pr-4">
        <span className={`text-xs font-semibold capitalize ${statusCls[inv.status] ?? 'text-gray-600'}`}>
          {inv.status}
        </span>
      </td>
      <td className="py-3 text-sm">
        {inv.pdf_url ? (
          <a
            href={inv.pdf_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-brand-600 hover:underline"
          >
            <FileText className="h-4 w-4" />
            PDF
          </a>
        ) : inv.invoice_url ? (
          <a
            href={inv.invoice_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-brand-600 hover:underline"
          >
            <ExternalLink className="h-4 w-4" />
            Voir
          </a>
        ) : (
          <span className="text-gray-400">—</span>
        )}
      </td>
    </tr>
  )
}

export function BillingPage() {
  const { data: usage, isLoading: loadingUsage } = useQuery({
    queryKey: ['billing-usage'],
    queryFn: billingApi.getUsage,
  })

  const { data: invoices = [], isLoading: loadingInvoices } = useQuery({
    queryKey: ['billing-invoices'],
    queryFn: billingApi.getInvoices,
  })

  const trialDaysLeft = usage?.trial_ends_at
    ? Math.max(0, Math.ceil((new Date(usage.trial_ends_at).getTime() - Date.now()) / 86_400_000))
    : null

  const contractDaysLeft = usage?.days_remaining ?? null

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <CreditCard className="h-6 w-6 text-brand-600" />
        <h1 className="text-2xl font-bold text-gray-900">Facturation & Licence</h1>
      </div>

      {/* Status card */}
      {loadingUsage ? (
        <div className="bg-white rounded-xl border p-6 animate-pulse h-40" />
      ) : usage ? (
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Ma licence</h2>
            <StatusBadge status={usage.license_status} />
          </div>

          {/* Trial countdown */}
          {usage.license_status === 'trial' && trialDaysLeft !== null && (
            <div className="flex items-center gap-2 bg-orange-50 border border-orange-100 rounded-lg px-4 py-3 text-sm text-orange-700">
              <RefreshCw className="h-4 w-4 flex-shrink-0" />
              Essai gratuit — <strong>{trialDaysLeft} jour{trialDaysLeft !== 1 ? 's' : ''}</strong> restant
              {trialDaysLeft !== 1 ? 's' : ''}
            </div>
          )}

          {/* Contract end */}
          {usage.contract_end && (
            <p className="text-sm text-gray-600">
              Contrat jusqu'au{' '}
              <span className="font-medium text-gray-900">
                {new Date(usage.contract_end).toLocaleDateString('fr-FR')}
              </span>
              {contractDaysLeft !== null && (
                <span className="ml-2 text-gray-500">({contractDaysLeft} jours restants)</span>
              )}
            </p>
          )}

          {/* Quotas */}
          <div className="space-y-4 pt-2 border-t border-gray-100">
            <QuotaBar
              label="Exécutions ce mois"
              used={usage.executions_used}
              limit={usage.executions_limit}
              pct={usage.executions_pct}
            />
            <QuotaBar
              label="Connecteurs actifs"
              used={usage.connectors_used}
              limit={usage.connectors_limit}
              pct={usage.connectors_limit > 0 ? (usage.connectors_used / usage.connectors_limit) * 100 : 0}
            />
          </div>

          {/* CTA */}
          <a
            href="mailto:sales@bxchange.io"
            className="inline-flex items-center gap-2 text-sm text-brand-600 hover:underline font-medium"
          >
            <Mail className="h-4 w-4" />
            Contacter notre équipe commerciale
          </a>
        </div>
      ) : null}

      {/* Invoices */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Factures</h2>

        {loadingInvoices ? (
          <div className="animate-pulse space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-8 bg-gray-100 rounded" />
            ))}
          </div>
        ) : invoices.length === 0 ? (
          <p className="text-sm text-gray-500">Aucune facture disponible.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  <th className="pb-2 pr-4">Date</th>
                  <th className="pb-2 pr-4">Description</th>
                  <th className="pb-2 pr-4">Montant</th>
                  <th className="pb-2 pr-4">Statut</th>
                  <th className="pb-2">Lien</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <InvoiceRow key={inv.invoice_id} inv={inv} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
