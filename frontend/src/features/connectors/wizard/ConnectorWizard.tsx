import { useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X, Wifi, Globe, ChevronRight, ChevronLeft, Link, FolderOpen, Upload } from 'lucide-react'
import type { ConnectorType, AuthType, SOAPAdvancedConfig, RESTAdvancedConfig } from '@/lib/api/connectors'
import { connectorsApi } from '@/lib/api/connectors'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { JsonViewer } from '@/components/ui/JsonViewer'
import { KeyValueEditor, type KVPair } from '@/components/ui/KeyValueEditor'

interface Props {
  onClose: () => void
}

type Step = 1 | 2 | 3 | 4 | 5

interface WizardState {
  // Step 1
  type: ConnectorType | null
  name: string
  // Step 2 – SOAP source
  wsdlSource: 'url' | 'upload'
  wsdlUrl: string
  wsdlFile: File | null
  wsdlFileId: string | null
  wsdlFileName: string | null
  uploadError: string | null
  wsdlOperations: string[]
  selectedOperation: string
  // Step 2 – REST
  baseUrl: string
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  restPath: string
  customHeaders: KVPair[]
  // Step 3
  authType: AuthType
  username: string
  password: string
  bearerToken: string
  apiKeyName: string
  apiKeyValue: string
  apiKeyIn: 'header' | 'query'
  // Step 4 – SOAP advanced
  soapAdvServiceName: string
  soapAdvPortName: string
  soapAdvOperationTimeout: string
  soapAdvCustomHeaders: KVPair[]
  soapAdvWsSecEnabled: boolean
  soapAdvWsSecUsername: string
  soapAdvWsSecPassword: string
  soapAdvResponsePath: string
  soapAdvForceListPaths: string
  // Step 4 – REST advanced
  restAdvStaticHeaders: KVPair[]
  restAdvQueryParams: KVPair[]
  restAdvRetryCount: string
  restAdvRetryBackoff: string
  restAdvRetryOnCodes: string
  restAdvResponsePath: string
  restAdvBodyTemplate: string
  restAdvOauth2Enabled: boolean
  restAdvOauth2TokenUrl: string
  restAdvOauth2ClientId: string
  restAdvOauth2ClientSecret: string
  restAdvOauth2Scope: string
  restAdvOauth2CacheTtl: string
  // Internal
  draftConnectorId: string | null
  testResponse: unknown
  testError: string | null
}

const INITIAL: WizardState = {
  type: null, name: '',
  wsdlSource: 'url',
  wsdlUrl: '', wsdlFile: null, wsdlFileId: null, wsdlFileName: null, uploadError: null,
  wsdlOperations: [], selectedOperation: '',
  baseUrl: '', method: 'GET', restPath: '', customHeaders: [{ key: '', value: '' }],
  authType: 'none', username: '', password: '',
  bearerToken: '', apiKeyName: 'X-API-Key', apiKeyValue: '', apiKeyIn: 'header',
  soapAdvServiceName: '', soapAdvPortName: '', soapAdvOperationTimeout: '30',
  soapAdvCustomHeaders: [], soapAdvWsSecEnabled: false,
  soapAdvWsSecUsername: '', soapAdvWsSecPassword: '',
  soapAdvResponsePath: '', soapAdvForceListPaths: '',
  restAdvStaticHeaders: [], restAdvQueryParams: [],
  restAdvRetryCount: '3', restAdvRetryBackoff: '1.0', restAdvRetryOnCodes: '',
  restAdvResponsePath: '', restAdvBodyTemplate: '',
  restAdvOauth2Enabled: false, restAdvOauth2TokenUrl: '',
  restAdvOauth2ClientId: '', restAdvOauth2ClientSecret: '',
  restAdvOauth2Scope: '', restAdvOauth2CacheTtl: '3600',
  draftConnectorId: null, testResponse: null, testError: null,
}

function stepLabel(s: Step) {
  return ['Type & Nom', 'Connexion', 'Authentification', 'Config. avancée', 'Test & Confirmation'][s - 1]
}

function buildKVMap(pairs: KVPair[]): Record<string, string> {
  return Object.fromEntries(pairs.filter((h) => h.key.trim()).map((h) => [h.key.trim(), h.value]))
}

function buildAuthConfig(s: WizardState): Record<string, unknown> | undefined {
  if (s.authType === 'basic') return { username: s.username, password: s.password }
  if (s.authType === 'bearer') return { token: s.bearerToken }
  if (s.authType === 'apikey') return { key_name: s.apiKeyName, key_value: s.apiKeyValue, in: s.apiKeyIn }
  return undefined
}

function buildAdvancedConfig(s: WizardState): SOAPAdvancedConfig | RESTAdvancedConfig | null {
  if (s.type === 'soap') {
    const adv: SOAPAdvancedConfig = {}
    if (s.soapAdvServiceName.trim()) adv.service_name = s.soapAdvServiceName.trim()
    if (s.soapAdvPortName.trim()) adv.port_name = s.soapAdvPortName.trim()
    const timeout = parseInt(s.soapAdvOperationTimeout)
    if (!isNaN(timeout) && timeout !== 30) adv.operation_timeout = timeout
    const ch = buildKVMap(s.soapAdvCustomHeaders)
    if (Object.keys(ch).length) adv.custom_headers = ch
    if (s.soapAdvWsSecEnabled && s.soapAdvWsSecUsername.trim()) {
      adv.ws_security = {
        type: 'username_token',
        username: s.soapAdvWsSecUsername.trim(),
        ...(s.soapAdvWsSecPassword ? { password: s.soapAdvWsSecPassword } : {}),
      }
    }
    if (s.soapAdvResponsePath.trim()) adv.response_path = s.soapAdvResponsePath.trim()
    const flp = s.soapAdvForceListPaths.split(',').map((t) => t.trim()).filter(Boolean)
    if (flp.length) adv.force_list_paths = flp
    return Object.keys(adv).length ? adv : null
  }

  if (s.type === 'rest') {
    const adv: RESTAdvancedConfig = {}
    const sh = buildKVMap(s.restAdvStaticHeaders)
    if (Object.keys(sh).length) adv.headers = sh
    const qp = buildKVMap(s.restAdvQueryParams)
    if (Object.keys(qp).length) adv.query_params = qp
    const rc = parseInt(s.restAdvRetryCount)
    if (!isNaN(rc) && rc !== 3) adv.retry_count = rc
    const rb = parseFloat(s.restAdvRetryBackoff)
    if (!isNaN(rb) && rb !== 1.0) adv.retry_backoff = rb
    if (s.restAdvRetryOnCodes.trim()) {
      const codes = s.restAdvRetryOnCodes.split(',').map((c) => parseInt(c.trim())).filter((n) => !isNaN(n))
      if (codes.length) adv.retry_on_codes = codes
    }
    if (s.restAdvResponsePath.trim()) adv.response_path = s.restAdvResponsePath.trim()
    if (s.restAdvBodyTemplate.trim()) adv.body_template = s.restAdvBodyTemplate.trim()
    if (s.restAdvOauth2Enabled && s.restAdvOauth2TokenUrl.trim() && s.restAdvOauth2ClientId.trim()) {
      adv.oauth2_client_credentials = {
        token_url: s.restAdvOauth2TokenUrl.trim(),
        client_id: s.restAdvOauth2ClientId.trim(),
        ...(s.restAdvOauth2ClientSecret ? { client_secret: s.restAdvOauth2ClientSecret } : {}),
        ...(s.restAdvOauth2Scope.trim() ? { scope: s.restAdvOauth2Scope.trim() } : {}),
        ...(s.restAdvOauth2CacheTtl !== '3600' ? { token_cache_ttl: parseInt(s.restAdvOauth2CacheTtl) || 3600 } : {}),
      }
    }
    return Object.keys(adv).length ? adv : null
  }

  return null
}

export function ConnectorWizard({ onClose }: Props) {
  const [step, setStep] = useState<Step>(1)
  const [s, setS] = useState<WizardState>(INITIAL)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
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

  // SOAP URL mode: create draft then test-wsdl
  const loadWsdl = useMutation({
    mutationFn: async () => {
      let connId = s.draftConnectorId
      if (!connId) {
        const conn = await connectorsApi.createConnector({
          name: s.name, type: 'soap', wsdl_url: s.wsdlUrl, wsdl_source: 'url', auth_type: 'none',
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

  // SOAP upload mode: upload file, then create draft connector
  const uploadAndLoad = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('file', file)
      const uploaded = await connectorsApi.uploadWsdl(form)

      let connId = s.draftConnectorId
      if (!connId) {
        const conn = await connectorsApi.createConnector({
          name: s.name,
          type: 'soap',
          wsdl_source: 'upload',
          wsdl_file_id: uploaded.wsdl_file_id,
          auth_type: 'none',
        })
        connId = conn.id
      }
      return { uploaded, connId }
    },
    onSuccess: ({ uploaded, connId }) => {
      patch({
        wsdlFileId: uploaded.wsdl_file_id,
        wsdlFileName: uploaded.filename,
        wsdlOperations: uploaded.operations,
        selectedOperation: uploaded.operations[0] ?? '',
        draftConnectorId: connId,
        uploadError: null,
      })
    },
    onError: (err: Error) => {
      patch({ uploadError: err.message })
    },
  })

  // Step 5: REST create + test
  const testRest = useMutation({
    mutationFn: async () => {
      const adv = buildAdvancedConfig(s)
      let connId = s.draftConnectorId
      if (!connId) {
        const conn = await connectorsApi.createConnector({
          name: s.name, type: 'rest', base_url: s.baseUrl,
          auth_type: s.authType, auth_config: buildAuthConfig(s),
          headers: buildKVMap(s.customHeaders),
          advanced_config: adv,
        })
        connId = conn.id
        patch({ draftConnectorId: conn.id })
      } else {
        await connectorsApi.updateConnector(connId, {
          base_url: s.baseUrl, auth_type: s.authType,
          auth_config: buildAuthConfig(s), headers: buildKVMap(s.customHeaders),
          advanced_config: adv,
        })
      }
      return connectorsApi.testRest(connId, { method: s.method, path: s.restPath })
    },
    onSuccess: (data) => patch({ testResponse: data, testError: null }),
    onError: (err: Error) => patch({ testError: err.message, testResponse: null }),
  })

  // Step 5: SOAP test (update auth + advanced then re-test-wsdl)
  const testSoap = useMutation({
    mutationFn: async () => {
      const connId = s.draftConnectorId!
      await connectorsApi.updateConnector(connId, {
        auth_type: s.authType, auth_config: buildAuthConfig(s),
        advanced_config: buildAdvancedConfig(s),
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
    if (s.draftConnectorId) {
      const adv = buildAdvancedConfig(s)
      connectorsApi.updateConnector(s.draftConnectorId, {
        status: 'active',
        ...(adv != null ? { advanced_config: adv } : {}),
        ...(s.type === 'soap' && s.selectedOperation ? { operation: s.selectedOperation } : {}),
      }).catch(() => {})
    }
    qc.invalidateQueries({ queryKey: ['connectors'] })
    onClose()
  }

  function handleFileSelect(file: File | undefined) {
    if (!file) return
    patch({ wsdlFile: file, wsdlFileId: null, wsdlFileName: null, wsdlOperations: [], uploadError: null })
    uploadAndLoad.reset()
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
          {/* Source toggle */}
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => patch({ wsdlSource: 'url', wsdlFile: null, wsdlFileId: null, wsdlFileName: null, wsdlOperations: [], uploadError: null })}
              className={`flex items-center gap-2 px-4 py-3 rounded-xl border-2 text-sm font-medium transition-colors ${
                s.wsdlSource === 'url'
                  ? 'border-brand-600 bg-brand-50 text-brand-700'
                  : 'border-gray-200 hover:border-gray-300 text-gray-600'
              }`}
            >
              <Link className="h-4 w-4 flex-shrink-0" />
              URL WSDL
            </button>
            <button
              onClick={() => patch({ wsdlSource: 'upload', wsdlUrl: '', wsdlOperations: [] })}
              className={`flex items-center gap-2 px-4 py-3 rounded-xl border-2 text-sm font-medium transition-colors ${
                s.wsdlSource === 'upload'
                  ? 'border-brand-600 bg-brand-50 text-brand-700'
                  : 'border-gray-200 hover:border-gray-300 text-gray-600'
              }`}
            >
              <FolderOpen className="h-4 w-4 flex-shrink-0" />
              Fichier .wsdl local
            </button>
          </div>

          {/* URL mode */}
          {s.wsdlSource === 'url' && (
            <>
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
            </>
          )}

          {/* Upload mode */}
          {s.wsdlSource === 'upload' && (
            <>
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Fichier WSDL</p>
                <div
                  onDrop={(e) => {
                    e.preventDefault()
                    setIsDragging(false)
                    handleFileSelect(e.dataTransfer.files[0])
                  }}
                  onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
                  onDragLeave={() => setIsDragging(false)}
                  onClick={() => fileInputRef.current?.click()}
                  className={`flex flex-col items-center justify-center gap-2 border-2 border-dashed rounded-xl p-6 cursor-pointer transition-colors ${
                    isDragging
                      ? 'border-brand-400 bg-brand-50'
                      : s.wsdlFile
                      ? 'border-green-400 bg-green-50'
                      : 'border-gray-300 hover:border-gray-400 bg-gray-50'
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".wsdl,.xml"
                    className="hidden"
                    onChange={(e) => handleFileSelect(e.target.files?.[0])}
                  />
                  <Upload className={`h-8 w-8 ${s.wsdlFile ? 'text-green-500' : 'text-gray-400'}`} />
                  {s.wsdlFile ? (
                    <div className="text-center">
                      <p className="text-sm font-medium text-green-700">{s.wsdlFile.name}</p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {(s.wsdlFile.size / 1024).toFixed(1)} KB — cliquer pour changer
                      </p>
                    </div>
                  ) : (
                    <div className="text-center">
                      <p className="text-sm text-gray-600">Glissez votre fichier .wsdl ici</p>
                      <p className="text-xs text-gray-400 mt-0.5">ou cliquez pour sélectionner</p>
                      <p className="text-xs text-gray-400 mt-1">Formats : .wsdl, .xml — max 5 MB</p>
                    </div>
                  )}
                </div>
              </div>

              <Button
                variant="secondary"
                onClick={() => s.wsdlFile && uploadAndLoad.mutate(s.wsdlFile)}
                loading={uploadAndLoad.isPending}
                disabled={!s.wsdlFile}
                className="self-start"
              >
                Analyser le fichier
              </Button>

              {s.uploadError && (
                <p className="text-sm text-red-600">
                  Ce fichier n'est pas un WSDL valide : {s.uploadError}
                </p>
              )}
            </>
          )}

          {/* Operations (shared URL + upload) */}
          {s.wsdlOperations.length > 0 && (
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-gray-700">
                Opération par défaut{' '}
                <span className="font-normal text-gray-400">({s.wsdlOperations.length} disponibles)</span>
              </label>
              <select
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                value={s.selectedOperation}
                onChange={(e) => patch({ selectedOperation: e.target.value })}
              >
                <option value="">— Aucune (à spécifier à chaque appel) —</option>
                {s.wsdlOperations.map((op) => (
                  <option key={op} value={op}>{op}</option>
                ))}
              </select>
              <p className="text-xs text-gray-400">
                Optionnel — peut être passé à chaque appel via le champ <code className="bg-gray-100 px-1 rounded">operation</code> des params.
              </p>
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
        <KeyValueEditor
          label="Headers"
          pairs={s.customHeaders}
          onChange={(pairs) => patch({ customHeaders: pairs })}
        />
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

  // ── Step 4 — Advanced config ──────────────────────────────────────────────
  function renderStep4() {
    if (s.type === 'soap') {
      return (
        <div className="flex flex-col gap-5">
          <p className="text-xs text-gray-500">Tous les champs sont optionnels.</p>

          {/* Service / Port */}
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Service name"
              placeholder="CalculatorService"
              value={s.soapAdvServiceName}
              onChange={(e) => patch({ soapAdvServiceName: e.target.value })}
            />
            <Input
              label="Port name"
              placeholder="CalculatorSoap"
              value={s.soapAdvPortName}
              onChange={(e) => patch({ soapAdvPortName: e.target.value })}
            />
          </div>

          {/* Operation timeout */}
          <Input
            label="Timeout opération (s)"
            type="number"
            placeholder="30"
            value={s.soapAdvOperationTimeout}
            onChange={(e) => patch({ soapAdvOperationTimeout: e.target.value })}
          />

          {/* Custom HTTP headers */}
          <KeyValueEditor
            label="Headers HTTP additionnels"
            pairs={s.soapAdvCustomHeaders}
            onChange={(pairs) => patch({ soapAdvCustomHeaders: pairs })}
          />

          {/* Response path */}
          <Input
            label="Response path (ex: Body.Result)"
            placeholder="Body.Result"
            value={s.soapAdvResponsePath}
            onChange={(e) => patch({ soapAdvResponsePath: e.target.value })}
          />

          {/* Force list paths */}
          <Input
            label="Force list paths (séparés par virgule)"
            placeholder="Item,Row,Record"
            value={s.soapAdvForceListPaths}
            onChange={(e) => patch({ soapAdvForceListPaths: e.target.value })}
          />

          {/* WS-Security */}
          <div className="border border-gray-200 rounded-xl p-4 flex flex-col gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                className="rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                checked={s.soapAdvWsSecEnabled}
                onChange={(e) => patch({ soapAdvWsSecEnabled: e.target.checked })}
              />
              <span className="text-sm font-medium text-gray-700">WS-Security (UsernameToken)</span>
            </label>
            {s.soapAdvWsSecEnabled && (
              <div className="flex flex-col gap-3 pt-1">
                <Input
                  label="Utilisateur WS-Sec"
                  value={s.soapAdvWsSecUsername}
                  onChange={(e) => patch({ soapAdvWsSecUsername: e.target.value })}
                />
                <Input
                  label="Mot de passe WS-Sec"
                  type="password"
                  value={s.soapAdvWsSecPassword}
                  onChange={(e) => patch({ soapAdvWsSecPassword: e.target.value })}
                />
              </div>
            )}
          </div>
        </div>
      )
    }

    // REST advanced
    return (
      <div className="flex flex-col gap-5">
        <p className="text-xs text-gray-500">Tous les champs sont optionnels.</p>

        {/* Static headers */}
        <KeyValueEditor
          label="Headers statiques"
          pairs={s.restAdvStaticHeaders}
          onChange={(pairs) => patch({ restAdvStaticHeaders: pairs })}
        />

        {/* Static query params */}
        <KeyValueEditor
          label="Query params statiques"
          pairs={s.restAdvQueryParams}
          onChange={(pairs) => patch({ restAdvQueryParams: pairs })}
          keyPlaceholder="Paramètre"
        />

        {/* Retry policy */}
        <div className="border border-gray-200 rounded-xl p-4 flex flex-col gap-3">
          <p className="text-sm font-medium text-gray-700">Politique de retry</p>
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Tentatives max"
              type="number"
              placeholder="3"
              value={s.restAdvRetryCount}
              onChange={(e) => patch({ restAdvRetryCount: e.target.value })}
            />
            <Input
              label="Backoff base (s)"
              type="number"
              placeholder="1.0"
              value={s.restAdvRetryBackoff}
              onChange={(e) => patch({ restAdvRetryBackoff: e.target.value })}
            />
          </div>
          <Input
            label="Codes retriables (ex: 502,503,504)"
            placeholder="502,503,504"
            value={s.restAdvRetryOnCodes}
            onChange={(e) => patch({ restAdvRetryOnCodes: e.target.value })}
          />
        </div>

        {/* Response path */}
        <Input
          label="Response path JSONPath (ex: $.data.items)"
          placeholder="$.data.items"
          value={s.restAdvResponsePath}
          onChange={(e) => patch({ restAdvResponsePath: e.target.value })}
        />

        {/* Body template */}
        <div>
          <label className="text-sm font-medium text-gray-700">Body template</label>
          <textarea
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500 resize-y"
            rows={3}
            placeholder={'{"name": "{name}", "qty": {qty}}'}
            value={s.restAdvBodyTemplate}
            onChange={(e) => patch({ restAdvBodyTemplate: e.target.value })}
          />
          <p className="text-xs text-gray-400 mt-1">
            Utilisez <code className="bg-gray-100 px-1 rounded">{'{variable}'}</code> — valeurs injectées depuis les params d'exécution.
          </p>
        </div>

        {/* OAuth2 CC */}
        <div className="border border-gray-200 rounded-xl p-4 flex flex-col gap-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              className="rounded border-gray-300 text-brand-600 focus:ring-brand-500"
              checked={s.restAdvOauth2Enabled}
              onChange={(e) => patch({ restAdvOauth2Enabled: e.target.checked })}
            />
            <span className="text-sm font-medium text-gray-700">OAuth2 Client Credentials</span>
          </label>
          {s.restAdvOauth2Enabled && (
            <div className="flex flex-col gap-3 pt-1">
              <Input
                label="Token URL"
                placeholder="https://auth.example.com/oauth/token"
                value={s.restAdvOauth2TokenUrl}
                onChange={(e) => patch({ restAdvOauth2TokenUrl: e.target.value })}
              />
              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="Client ID"
                  value={s.restAdvOauth2ClientId}
                  onChange={(e) => patch({ restAdvOauth2ClientId: e.target.value })}
                />
                <Input
                  label="Client Secret"
                  type="password"
                  value={s.restAdvOauth2ClientSecret}
                  onChange={(e) => patch({ restAdvOauth2ClientSecret: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="Scope (optionnel)"
                  placeholder="read:api"
                  value={s.restAdvOauth2Scope}
                  onChange={(e) => patch({ restAdvOauth2Scope: e.target.value })}
                />
                <Input
                  label="Cache TTL (s)"
                  type="number"
                  placeholder="3600"
                  value={s.restAdvOauth2CacheTtl}
                  onChange={(e) => patch({ restAdvOauth2CacheTtl: e.target.value })}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  // ── Step 5 — Test & Confirmation ─────────────────────────────────────────
  function renderStep5() {
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
      if (s.type === 'soap') {
        if (s.wsdlSource === 'url') return s.wsdlUrl.trim().length > 0 && s.wsdlOperations.length > 0
        return s.wsdlFileId !== null && s.wsdlOperations.length > 0
      }
      return s.baseUrl.trim().length > 0
    }
    if (step === 3) return true
    if (step === 4) return true
    return false
  }

  function next() { if (step < 5) setStep((prev) => (prev + 1) as Step) }
  function prev() { if (step > 1) setStep((prev) => (prev - 1) as Step) }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col" style={{ maxHeight: '90vh' }}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div>
            <h2 className="font-semibold text-gray-900">Nouveau connecteur</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Étape {step}/5 — {stepLabel(step)}
            </p>
          </div>
          <button onClick={handleClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Progress */}
        <div className="flex px-6 pt-4 gap-1.5">
          {([1, 2, 3, 4, 5] as Step[]).map((n) => (
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
          {step === 5 && renderStep5()}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 gap-3">
          <Button variant="ghost" onClick={step === 1 ? handleClose : prev}>
            {step === 1 ? 'Annuler' : <><ChevronLeft className="h-4 w-4" /> Précédent</>}
          </Button>

          {step < 5 ? (
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
