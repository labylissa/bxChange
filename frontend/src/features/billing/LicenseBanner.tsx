import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Clock, XCircle } from 'lucide-react'
import { billingApi } from '@/lib/api/billing'
import { useAuthStore } from '@/stores/authStore'

export function LicenseBanner() {
  const user = useAuthStore((s) => s.user)

  const { data: usage } = useQuery({
    queryKey: ['billing-usage'],
    queryFn: billingApi.getUsage,
    enabled: !!user && user.role !== 'super_admin',
    staleTime: 60_000,
  })

  if (!usage) return null

  const trialDaysLeft =
    usage.license_status === 'trial' && usage.trial_ends_at
      ? Math.max(0, Math.ceil((new Date(usage.trial_ends_at).getTime() - Date.now()) / 86_400_000))
      : null

  if (usage.license_status === 'expired') {
    return (
      <div className="bg-red-600 text-white px-4 py-2.5 flex items-center justify-center gap-2 text-sm font-medium">
        <XCircle className="h-4 w-4 flex-shrink-0" />
        Votre licence a expiré. Contactez{' '}
        <a href="mailto:sales@bxchange.io" className="underline font-bold">
          sales@bxchange.io
        </a>{' '}
        pour renouveler.
      </div>
    )
  }

  if (usage.license_status === 'suspended') {
    return (
      <div className="bg-red-800 text-white px-4 py-2.5 flex items-center justify-center gap-2 text-sm font-medium">
        <XCircle className="h-4 w-4 flex-shrink-0" />
        Votre licence est suspendue. Contactez{' '}
        <a href="mailto:support@bxchange.io" className="underline font-bold">
          support@bxchange.io
        </a>
        .
      </div>
    )
  }

  if (usage.license_status === 'trial' && trialDaysLeft !== null && trialDaysLeft <= 7) {
    return (
      <div className="bg-blue-600 text-white px-4 py-2.5 flex items-center justify-center gap-2 text-sm">
        <Clock className="h-4 w-4 flex-shrink-0" />
        Votre essai expire dans{' '}
        <strong>
          {trialDaysLeft} jour{trialDaysLeft !== 1 ? 's' : ''}
        </strong>
        . Contactez{' '}
        <a href="mailto:sales@bxchange.io" className="underline font-semibold ml-1">
          sales@bxchange.io
        </a>
        .
      </div>
    )
  }

  if (usage.executions_pct >= 85) {
    return (
      <div className="bg-orange-500 text-white px-4 py-2.5 flex items-center justify-center gap-2 text-sm">
        <AlertTriangle className="h-4 w-4 flex-shrink-0" />
        {usage.executions_pct.toFixed(0)}% de votre quota mensuel utilisé (
        {usage.executions_used.toLocaleString()} / {usage.executions_limit.toLocaleString()}).
      </div>
    )
  }

  return null
}
