import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Shield, Plus, Trash2, Copy, Check, Key } from 'lucide-react'
import { ssoApi, type SSOConfig, type SSOConfigCreate, type ScimToken, type ScimTokenCreated } from '@/lib/api/sso'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { useToast } from '@/stores/toastStore'
import { RoleMappingEditor } from './RoleMappingEditor'

// ── SSO Config form ───────────────────────────────────────────────────────────

function SSOConfigForm({ existing, onSaved }: { existing?: SSOConfig; onSaved: () => void }) {
  const toast = useToast()
  const qc = useQueryClient()

  const [idpType, setIdpType] = useState<'saml' | 'oidc'>(existing?.idp_type ?? 'saml')
  const [entityId, setEntityId] = useState(existing?.entity_id ?? '')
  const [ssoUrl, setSsoUrl] = useState(existing?.sso_url ?? '')
  const [certificate, setCertificate] = useState('')
  const [domains, setDomains] = useState<string>(
    (existing?.attr_mapping as any)?._domains?.join(', ') ?? ''
  )
  const [roleMapping, setRoleMapping] = useState<Record<string, string>>(
    (existing?.attr_mapping as any)?.role_mapping ?? {}
  )
  const [emailAttr, setEmailAttr] = useState<string>(
    (existing?.attr_mapping as any)?.email_attr ?? ''
  )
  const [nameAttr, setNameAttr] = useState<string>(
    (existing?.attr_mapping as any)?.name_attr ?? ''
  )
  const [groupsAttr, setGroupsAttr] = useState<string>(
    (existing?.attr_mapping as any)?.groups_attr ?? ''
  )

  const save = useMutation({
    mutationFn: () => {
      const attrMapping = {
        ...(emailAttr ? { email_attr: emailAttr } : {}),
        ...(nameAttr ? { name_attr: nameAttr } : {}),
        ...(groupsAttr ? { groups_attr: groupsAttr } : {}),
        role_mapping: roleMapping,
      }
      const domainList = domains.split(',').map((d) => d.trim()).filter(Boolean)

      if (existing) {
        return ssoApi.updateConfig({
          entity_id: entityId,
          sso_url: ssoUrl,
          ...(certificate ? { certificate } : {}),
          attr_mapping: attrMapping,
          domains: domainList,
        })
      }
      return ssoApi.createConfig({
        idp_type: idpType,
        entity_id: entityId,
        sso_url: ssoUrl,
        ...(certificate ? { certificate } : {}),
        attr_mapping: attrMapping,
        domains: domainList,
      } as SSOConfigCreate)
    },
    onSuccess: () => {
      toast.success(existing ? 'Configuration SSO mise à jour' : 'Configuration SSO créée')
      qc.invalidateQueries({ queryKey: ['sso-config'] })
      onSaved()
    },
    onError: () => toast.error('Erreur lors de la sauvegarde'),
  })

  return (
    <div className="flex flex-col gap-5">
      {!existing && (
        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-gray-700">Type d'IdP</label>
          <div className="flex gap-2">
            {(['saml', 'oidc'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setIdpType(t)}
                className={`px-4 py-2 rounded-lg border text-sm font-medium transition-colors ${
                  idpType === t
                    ? 'bg-brand-600 text-white border-brand-600'
                    : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                }`}
              >
                {t.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      )}

      <Input
        label={idpType === 'saml' ? 'Entity ID (IdP)' : 'Client ID (OIDC)'}
        placeholder={idpType === 'saml' ? 'https://idp.example.com/saml' : 'my-client-id'}
        value={entityId}
        onChange={(e) => setEntityId(e.target.value)}
      />

      <Input
        label={idpType === 'saml' ? 'SSO URL (IdP)' : 'Issuer URL'}
        placeholder={idpType === 'saml' ? 'https://idp.example.com/sso' : 'https://accounts.google.com'}
        value={ssoUrl}
        onChange={(e) => setSsoUrl(e.target.value)}
      />

      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium text-gray-700">
          {idpType === 'saml' ? 'Certificat X.509 (PEM)' : 'Client Secret'}
        </label>
        <textarea
          placeholder={idpType === 'saml' ? 'MIIFxxxxx...' : 'secret-value'}
          value={certificate}
          onChange={(e) => setCertificate(e.target.value)}
          rows={3}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono bg-white focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
        />
        <p className="text-xs text-gray-400">
          {existing ? 'Laisser vide pour conserver le certificat actuel.' : 'Chiffré au stockage — ne sera jamais retourné.'}
        </p>
      </div>

      <Input
        label="Domaines email (séparés par des virgules)"
        placeholder="acme.com, corp.acme.com"
        value={domains}
        onChange={(e) => setDomains(e.target.value)}
      />

      <details className="border border-gray-200 rounded-lg p-3">
        <summary className="text-sm font-medium text-gray-700 cursor-pointer select-none">
          Mapping d'attributs (optionnel)
        </summary>
        <div className="mt-3 flex flex-col gap-3">
          <Input
            label="Attribut email"
            placeholder="email (défaut)"
            value={emailAttr}
            onChange={(e) => setEmailAttr(e.target.value)}
          />
          <Input
            label="Attribut nom"
            placeholder="name (défaut)"
            value={nameAttr}
            onChange={(e) => setNameAttr(e.target.value)}
          />
          <Input
            label="Attribut groupes"
            placeholder="groups (défaut)"
            value={groupsAttr}
            onChange={(e) => setGroupsAttr(e.target.value)}
          />
          <RoleMappingEditor value={roleMapping} onChange={setRoleMapping} />
        </div>
      </details>

      <Button
        onClick={() => save.mutate()}
        loading={save.isPending}
        disabled={!entityId || !ssoUrl}
        className="self-start"
      >
        {existing ? 'Mettre à jour' : 'Créer la configuration SSO'}
      </Button>
    </div>
  )
}


// ── SCIM Tokens section ───────────────────────────────────────────────────────

function ScimTokensSection() {
  const toast = useToast()
  const qc = useQueryClient()
  const [newName, setNewName] = useState('')
  const [createdToken, setCreatedToken] = useState<ScimTokenCreated | null>(null)
  const [copied, setCopied] = useState(false)
  const [toRevoke, setToRevoke] = useState<string | null>(null)

  const { data: tokens = [], isLoading } = useQuery({
    queryKey: ['scim-tokens'],
    queryFn: ssoApi.listScimTokens,
  })

  const create = useMutation({
    mutationFn: () => ssoApi.createScimToken({ name: newName }),
    onSuccess: (data) => {
      toast.success('Token SCIM créé')
      qc.invalidateQueries({ queryKey: ['scim-tokens'] })
      setCreatedToken(data)
      setNewName('')
    },
    onError: () => toast.error('Erreur lors de la création du token'),
  })

  const revoke = useMutation({
    mutationFn: (id: string) => ssoApi.revokeScimToken(id),
    onSuccess: () => {
      toast.success('Token révoqué')
      qc.invalidateQueries({ queryKey: ['scim-tokens'] })
      setToRevoke(null)
    },
    onError: () => toast.error('Erreur lors de la révocation'),
  })

  async function copyToken(val: string) {
    await navigator.clipboard.writeText(val)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex flex-col gap-4">
      <h3 className="font-medium text-gray-900 flex items-center gap-2">
        <Key size={16} />
        Tokens SCIM (provisioning Azure AD / Okta)
      </h3>

      {createdToken && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex flex-col gap-2">
          <p className="text-sm font-medium text-amber-800">
            Token créé — copiez-le maintenant, il ne sera plus affiché.
          </p>
          <div className="flex items-center gap-2 font-mono text-xs bg-white border border-amber-200 rounded p-2 break-all">
            <span className="flex-1">{createdToken.raw_token}</span>
            <button onClick={() => copyToken(createdToken.raw_token)} className="text-amber-600 hover:text-amber-800 flex-shrink-0">
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </button>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setCreatedToken(null)} className="self-start">
            OK, je l'ai copié
          </Button>
        </div>
      )}

      <div className="flex gap-2 items-end">
        <Input
          label="Nom du token"
          placeholder="ex: Azure AD provisioning"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          className="flex-1"
        />
        <Button
          onClick={() => create.mutate()}
          loading={create.isPending}
          disabled={!newName.trim()}
          className="mb-0"
        >
          <Plus size={14} />
          Créer
        </Button>
      </div>

      {isLoading ? (
        <Spinner />
      ) : tokens.length === 0 ? (
        <p className="text-sm text-gray-400 italic">Aucun token SCIM configuré.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {tokens.map((t) => (
            <div key={t.id} className="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
              <div>
                <p className="text-sm font-medium text-gray-900">{t.name}</p>
                <p className="text-xs text-gray-400">
                  Créé le {new Date(t.created_at).toLocaleDateString('fr-FR')}
                  {t.expires_at && ` — expire le ${new Date(t.expires_at).toLocaleDateString('fr-FR')}`}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={t.is_active ? 'success' : 'error'}>
                  {t.is_active ? 'Actif' : 'Révoqué'}
                </Badge>
                {t.is_active && (
                  <button
                    onClick={() => setToRevoke(t.id)}
                    className="text-gray-400 hover:text-red-500 transition-colors"
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {toRevoke && (
        <ConfirmModal
          title="Révoquer ce token SCIM ?"
          message="Les provisions en cours via ce token seront interrompues."
          confirmLabel="Révoquer"
          variant="danger"
          onConfirm={() => revoke.mutate(toRevoke)}
          onCancel={() => setToRevoke(null)}
        />
      )}
    </div>
  )
}


// ── Main page ─────────────────────────────────────────────────────────────────

export function SSOConfigPage() {
  const toast = useToast()
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const { data: config, isLoading, error } = useQuery({
    queryKey: ['sso-config'],
    queryFn: ssoApi.getConfig,
    retry: (count, err: any) => err?.response?.status !== 404 && count < 2,
  })

  const deleteConfig = useMutation({
    mutationFn: ssoApi.deleteConfig,
    onSuccess: () => {
      toast.success('Configuration SSO supprimée')
      qc.invalidateQueries({ queryKey: ['sso-config'] })
      setConfirmDelete(false)
      setEditing(false)
    },
    onError: () => toast.error('Erreur lors de la suppression'),
  })

  const hasConfig = !!config && !(error as any)

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
            <Shield size={20} className="text-brand-600" />
            SSO Enterprise
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            SAML 2.0 / OIDC — Authentification unique pour votre organisation
          </p>
        </div>
        {hasConfig && !editing && (
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
              Modifier
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)} className="text-red-600 hover:text-red-700">
              <Trash2 size={14} />
            </Button>
          </div>
        )}
      </div>

      {isLoading ? (
        <Spinner />
      ) : hasConfig && !editing ? (
        <Card className="p-5 flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <Badge variant={config.is_active ? 'success' : 'error'}>
              {config.is_active ? 'Actif' : 'Désactivé'}
            </Badge>
            <Badge variant="default">{config.idp_type.toUpperCase()}</Badge>
          </div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <div>
              <p className="text-gray-500 text-xs">Entity ID / Client ID</p>
              <p className="font-mono text-gray-900 truncate">{config.entity_id}</p>
            </div>
            <div>
              <p className="text-gray-500 text-xs">SSO URL / Issuer</p>
              <p className="font-mono text-gray-900 truncate">{config.sso_url}</p>
            </div>
          </div>
        </Card>
      ) : editing ? (
        <Card className="p-5">
          <SSOConfigForm existing={config} onSaved={() => setEditing(false)} />
          <Button variant="ghost" size="sm" className="mt-3" onClick={() => setEditing(false)}>
            Annuler
          </Button>
        </Card>
      ) : (
        <Card className="p-5">
          <p className="text-sm text-gray-500 mb-4">
            Aucune configuration SSO. Configurez SAML 2.0 ou OIDC pour permettre la connexion via votre IdP d'entreprise.
          </p>
          <SSOConfigForm onSaved={() => {}} />
        </Card>
      )}

      <hr className="border-gray-200" />

      <ScimTokensSection />

      {confirmDelete && (
        <ConfirmModal
          title="Supprimer la configuration SSO ?"
          message="Les utilisateurs SSO ne pourront plus se connecter. Les comptes créés par JIT provisioning sont conservés."
          confirmLabel="Supprimer"
          variant="danger"
          onConfirm={() => deleteConfig.mutate()}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </div>
  )
}
