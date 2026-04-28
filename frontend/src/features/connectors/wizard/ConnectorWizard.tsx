import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X, Wifi, Globe, ChevronRight, ChevronLeft, Plus, Trash2 } from 'lucide-react'
import type { ConnectorType, AuthType } from '@/lib/api/connectors'
import { connectorsApi } from '@/lib/api/connectors'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { JsonViewer } from '@/components/ui/JsonViewer'

interface Props {
  onClose: () => void
}

type Step = 1 | 2 | 3 | 4

interface HeaderPair {
  key: string
  value: string
}

interface WizardState {
  // Step 1
  type: ConnectorType | null
  name: string
  // Step 2 – SOAP
  wsdlUrl: string
  wsdlOperations: string[]
  selectedOperation: string
  // Step 2 – REST
  baseUrl: string
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  restPath: string
  customHeaders: HeaderPair[]
  // Step 3
  authType: AuthType
  username: string
  password: string
  bearerToken: string
  apiKeyName: string
  apiKeyValue: string
  apiKeyIn: 'header' | 'query'
  // Internal
  draftConnectorId: string | null
  testResponse: unknown
  testError: string | null
}

const INITIAL: WizardState = {
  type: null, name: '',
  wsdlUrl: '', wsdlOperations: [], selectedOperation: '',
  baseUrl: '', method: 'GET', restPath: '', customHeaders: [{ key: '', value: '' }],
  authType: 'none', username: '', password: '',
  bearerToken: '', apiKeyName: 'X-API-Key', apiKeyValue: '', apiKeyIn: 'header',
  draftConnectorId: null, testResponse: null, testError: null,
}

function stepLabel(s: Step) {
  return ['Type & Nom', 'Connexion', 'Authentification', 'Test & Confirmation'][s - 1]
}

function buildAuthConfig(s: WizardState): Record<string, unknown> | undefined {
  if (s.authType === 'basic') return { username: s.username, password: s.password }
  if (s.authType === 'bearer') return { token: s.bearerToken }
  if (s.authType === 'apikey') return { key_name: s.apiKeyName, key_value: s.apiKeyValue, in: s.apiKeyIn }
  return undefined
}

function buildHeaders(pairs: HeaderPair[]): Record<string, string> {
  return Object.fromEntries(pairs.filter((h) => h.key.trim()).map((h) => [h.key.trim(), h.value]))
}

export function ConnectorWizard({ onClose }: Props) {
  const [step, setStep] = useState<Step>(1)
  const [s, setS] = useState<WizardState>(INITIAL)
  const qc = useQueryClient()

  function patch(partial: Partial<WizardState>) {
    setS((prev) => ({ ...prev, ...partial }))
  }

  const deleteDraft = useMutation({
    mutationFn: (id: string) => connectorsApi.deleteConnector(id),
  })

  function handleClose() {
    if (s.draftConnectorId) deleteDraft.mutate(s.draftConnectorId)
    onClose()
  }

  // SOAP: create draft then test-wsdl
  const loadWsdl = useMutation({
    mutationFn: async () => {
      let connId = s.draftConnectorId
      if (!connId) {
        const conn = await connectorsApi.createConnector({
          name: s.name, type: 'soap', wsdl_url: s.wsdlUrl, auth_type: 'none',
        })
        connId = conn.id
        patch({ draftConnectorId: conn.id })
      } else {
        await connectorsApi.updateConnector(connId, { wsdl_url: s.wsdlUrl })
      }
      return connectorsApi.testWsdl(connId)
    },
    onSuccess: (data) => {
      patch({ wsdlOperations: Object.keys(data.operations), selectedOperation: Object.keys(data.operations)[0] ?? '' })
    },
  })

  // Step 4: REST create + test
  const testRest = useMutation({
    mutationFn: async () => {
      let connId = s.draftConnectorId
      if (!connId) {
        const conn = await connectorsApi.createConnector({
          name: s.name, type: 'rest', base_url: s.baseUrl,
          auth_type: s.authType, auth_config: buildAuthConfig(s),
          headers: buildHeaders(s.customHeaders),
        })
        connId = conn.id
        patch({ draftConnectorId: conn.id })
      } else {
        await connectorsApi.updateConnector(connId, {
          base_url: s.baseUrl, auth_type: s.authType,
          auth_config: buildAuthConfig(s), headers: buildHeaders(s.customHeaders),
        })
      }
      return connectorsApi.testRest(connId, { method: s.method, path: s.restPath })
    },
    onSuccess: (data) => patch({ testResponse: data, testError: null }),
    onError: (err: Error) => patch({ testError: err.message, testResponse: null }),
  })

  // Step 4: SOAP test (update auth then re-test-wsdl)
  const testSoap = useMutation({
    mutationFn: async () => {
      const connId = s.draftConnectorId!
      await connectorsApi.updateConnector(connId, {
        auth_type: s.authType, auth_config: buildAuthConfig(s),
      })
      return connectorsApi.testWsdl(connId)
    },
    onSuccess: (data) => patch({ testResponse: data, testError: null }),
    onError: (err: Error) => patch({ testError: err.message, testResponse: null }),
  })

  function handleTest() {
    patch({ testResponse: null, testError: null })
    if (s.type === 'soap') testSoap.mutate()
    else testRest.mutate()
  }

  function handleConfirm() {
    // Connector already created — just activate it and close
    if (s.draftConnectorId) {
      connectorsApi.updateConnector(s.draftConnectorId, { status: 'active' })
        .catch(() => {/* status update is best-effort */ })
    }
    qc.invalidateQueries({ queryKey: ['connectors'] })
    onClose()
  }

  const isTesting = testRest.isPending || testSoap.isPending
  const testOk = s.testResponse !== null && s.testError === null

  // ── Step 1 ───────────────────────────────────────────────────────────────
  function renderStep1() {
    return (
      <div className="flex flex-col gap-6">
        <div className="grid grid-cols-2 gap-4">
          {(['soap', 'rest'] as ConnectorType[]).map((t) => (
            <button
              key={t}
              onClick={() => patch({ type: t })}
              className={`flex flex-col items-center gap-3 p-6 rounded-xl border-2 transition-colors ${
                s.type === t
                  ? 'border-brand-600 bg-brand-50 text-brand-700'
                  : 'border-gray-200 hover:border-gray-300 text-gray-600'
              }`}
            >
              {t === 'soap' ? <Wifi className="h-8 w-8" /> : <Globe className="h-8 w-8" />}
              <span className="font-semibold text-base uppercase">{t}</span>
              <span className="text-xs text-center text-gray-500">
                {t === 'soap' ? 'Connecteur WSDL / SOAP legacy' : 'API REST moderne (HTTP)'}
              </span>
            </button>
          ))}
        </div>
        <Input
          label="Nom du connecteur"
          placeholder="ex: SOAP Finances, REST CRM"
          value={s.name}
          onChange={(e) => patch({ name: e.target.value })}
        />
      </div>
    )
  }

  // ── Step 2 ───────────────────────────────────────────────────────────────
  function renderStep2() {
    if (s.type === 'soap') {
      return (
        <div className="flex flex-col gap-4">
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <Input
                label="URL du WSDL"
                placeholder="http://legacy.corp.local:8080/service?wsdl"
                value={s.wsdlUrl}
                onChange={(e) => patch({ wsdlUrl: e.target.value })}
              />
            </div>
            <Button
              variant="secondary"
              onClick={() => loadWsdl.mutate()}
              loading={loadWsdl.isPending}
              disabled={!s.wsdlUrl}
            >
              Charger
            </Button>
          </div>
          {loadWsdl.isError && (
            <p className="text-sm text-red-600">
              Impossible de charger le WSDL : {(loadWsdl.error as Error).message}
            </p>
          )}
          {s.wsdlOperations.length > 0 && (
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-gray-700">
                Opération ({s.wsdlOperations.length} disponibles)
              </label>
              <select
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                value={s.selectedOperation}
                onChange={(e) => patch({ selectedOperation: e.target.value })}
              >
                {s.wsdlOperations.map((op) => (
                  <option key={op} value={op}>{op}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      )
    }

    // REST
    return (
      <div className="flex flex-col gap-4">
        <Input
          label="Base URL"
          placeholder="https://api.example.com"
          value={s.baseUrl}
          onChange={(e) => patch({ baseUrl: e.target.value })}
        />
        <div className="flex gap-3">
          <div className="w-32">
            <label className="text-sm font-medium text-gray-700">Méthode</label>
            <select
              className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={s.method}
              onChange={(e) => patch({ method: e.target.value as WizardState['method'] })}
            >
              {['GET', 'POST', 'PUT', 'DELETE', 'PATCH'].map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <Input
              label="Path"
              placeholder="/api/users"
              value={s.restPath}
              onChange={(e) => patch({ restPath: e.target.value })}
            />
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium text-gray-700">Headers</label>
            <button
              type="button"
              onClick={() => patch({ customHeaders: [...s.customHeaders, { key: '', value: '' }] })}
              className="text-xs text-brand-600 hover:underline flex items-center gap-1"
            >
              <Plus className="h-3 w-3" /> Ajouter
            </button>
          </div>
          <div className="flex flex-col gap-2">
            {s.customHeaders.map((h, i) => (
              <div key={i} className="flex gap-2 items-center">
                <input
                  className="flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="Clé"
                  value={h.key}
                  onChange={(e) => {
                    const updated = [...s.customHeaders]
                    updated[i] = { ...updated[i], key: e.target.value }
                    patch({ customHeaders: updated })
                  }}
                />
                <input
                  className="flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="Valeur"
                  value={h.value}
                  onChange={(e) => {
                    const updated = [...s.customHeaders]
                    updated[i] = { ...updated[i], value: e.target.value }
                    patch({ customHeaders: updated })
                  }}
                />
                <button
                  type="button"
                  onClick={() => patch({ customHeaders: s.customHeaders.filter((_, j) => j !== i) })}
                  className="text-gray-400 hover:text-red-500"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  // ── Step 3 ───────────────────────────────────────────────────────────────
  function renderStep3() {
    return (
      <div className="flex flex-col gap-4">
        <div>
          <label className="text-sm font-medium text-gray-700">Type d'authentification</label>
          <select
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            value={s.authType}
            onChange={(e) => patch({ authType: e.target.value as AuthType })}
          >
            <option value="none">Aucune</option>
            <option value="basic">Basic (login/mot de passe)</option>
            <option value="bearer">Bearer Token (JWT)</option>
            <option value="apikey">API Key</option>
          </select>
        </div>

        {s.authType === 'basic' && (
          <>
            <Input label="Identifiant" value={s.username} onChange={(e) => patch({ username: e.target.value })} />
            <Input label="Mot de passe" type="password" value={s.password} onChange={(e) => patch({ password: e.target.value })} />
          </>
        )}
        {s.authType === 'bearer' && (
          <Input label="Token" placeholder="eyJhbGciO..." value={s.bearerToken} onChange={(e) => patch({ bearerToken: e.target.value })} />
        )}
        {s.authType === 'apikey' && (
          <>
            <Input label="Nom de la clé" placeholder="X-API-Key" value={s.apiKeyName} onChange={(e) => patch({ apiKeyName: e.target.value })} />
            <Input label="Valeur" type="password" value={s.apiKeyValue} onChange={(e) => patch({ apiKeyValue: e.target.value })} />
            <div>
              <label className="text-sm font-medium text-gray-700">Position</label>
              <select
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                value={s.apiKeyIn}
                onChange={(e) => patch({ apiKeyIn: e.target.value as 'header' | 'query' })}
              >
                <option value="header">Header HTTP</option>
                <option value="query">Query string</option>
              </select>
            </div>
          </>
        )}
      </div>
    )
  }

  // ── Step 4 ───────────────────────────────────────────────────────────────
  function renderStep4() {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-sm text-gray-600">
          Testez la connexion avant de finaliser le connecteur.
          {s.type === 'soap' && s.wsdlOperations.length === 0 && (
            <span className="text-orange-600"> Attention : le WSDL n'a pas encore été chargé (étape 2).</span>
          )}
        </p>

        <Button onClick={handleTest} loading={isTesting} className="self-start">
          Tester la connexion
        </Button>

        {s.testError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
            {s.testError}
          </div>
        )}

        {testOk && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 text-sm text-green-700 font-medium">
              <span className="h-2 w-2 rounded-full bg-green-500" /> Connexion réussie
            </div>
            <JsonViewer data={s.testResponse} maxHeight="200px" />
          </div>
        )}
      </div>
    )
  }

  // ── Validation ────────────────────────────────────────────────────────────
  function canAdvance(): boolean {
    if (step === 1) return !!s.type && s.name.trim().length > 0
    if (step === 2) {
      if (s.type === 'soap') return s.wsdlUrl.trim().length > 0 && s.wsdlOperations.length > 0
      return s.baseUrl.trim().length > 0
    }
    if (step === 3) return true
    return false
  }

  function next() { if (step < 4) setStep((prev) => (prev + 1) as Step) }
  function prev() { if (step > 1) setStep((prev) => (prev - 1) as Step) }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col" style={{ maxHeight: '90vh' }}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div>
            <h2 className="font-semibold text-gray-900">Nouveau connecteur</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Étape {step}/4 — {stepLabel(step)}
            </p>
          </div>
          <button onClick={handleClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Progress */}
        <div className="flex px-6 pt-4 gap-1.5">
          {([1, 2, 3, 4] as Step[]).map((n) => (
            <div
              key={n}
              className={`h-1 flex-1 rounded-full transition-colors ${n <= step ? 'bg-brand-600' : 'bg-gray-200'}`}
            />
          ))}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto px-6 py-5">
          {step === 1 && renderStep1()}
          {step === 2 && renderStep2()}
          {step === 3 && renderStep3()}
          {step === 4 && renderStep4()}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 gap-3">
          <Button variant="ghost" onClick={step === 1 ? handleClose : prev}>
            {step === 1 ? 'Annuler' : <><ChevronLeft className="h-4 w-4" /> Précédent</>}
          </Button>

          {step < 4 ? (
            <Button onClick={next} disabled={!canAdvance()}>
              Suivant <ChevronRight className="h-4 w-4" />
            </Button>
          ) : (
            <Button onClick={handleConfirm} disabled={!testOk}>
              Créer le connecteur
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
