import { useState } from 'react'
import { Shield } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { ssoApi } from '@/lib/api/sso'

interface Props {
  onRedirect?: (url: string) => void
}

export function SSOLoginButton({ onRedirect }: Props) {
  const [open, setOpen] = useState(false)
  const [domain, setDomain] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSSO() {
    if (!domain.trim()) {
      setError('Entrez votre domaine email (ex: acme.com)')
      return
    }
    setError('')
    setLoading(true)
    try {
      await ssoApi.getDomainHint(domain.trim().toLowerCase())
      // Build SAML redirect URL
      const redirectUrl = `/api/v1/sso/login?domain=${encodeURIComponent(domain.trim())}&return_to=${encodeURIComponent(window.location.origin + '/dashboard')}`
      if (onRedirect) {
        onRedirect(redirectUrl)
      } else {
        window.location.href = redirectUrl
      }
    } catch {
      setError('Aucun SSO configuré pour ce domaine')
    } finally {
      setLoading(false)
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full flex items-center justify-center gap-2 border border-gray-300 rounded-lg px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
      >
        <Shield size={15} />
        Connexion SSO entreprise
      </button>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Shield size={15} className="text-brand-600 flex-shrink-0" />
        <span className="text-sm font-medium text-gray-700">Connexion SSO</span>
      </div>

      <Input
        label="Domaine email"
        placeholder="acme.com"
        value={domain}
        onChange={(e) => setDomain(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && handleSSO()}
        error={error}
      />

      <div className="flex gap-2">
        <Button
          type="button"
          onClick={handleSSO}
          loading={loading}
          className="flex-1"
        >
          Continuer
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => { setOpen(false); setError(''); setDomain('') }}
        >
          Annuler
        </Button>
      </div>
    </div>
  )
}
