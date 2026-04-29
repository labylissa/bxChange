import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Key, ExternalLink, Wifi, Globe, Zap, Copy, Check } from 'lucide-react'
import { connectorsApi } from '@/lib/api/connectors'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { CodeBlock, type Snippets } from './components/CodeBlock'

const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'
const SWAGGER_URL = `${API_URL}/docs`

// ── snippet builders ───────────────────────────────────────────────────────────

function makeQuickStart(auth: 'apikey' | 'jwt', connectorId: string): Snippets {
  const id = connectorId || '{CONNECTOR_ID}'
  const curlAuth =
    auth === 'apikey'
      ? '-H "X-API-Key: bxc_votre_cle"'
      : '-H "Authorization: Bearer votre_jwt_token"'
  const jsAuth =
    auth === 'apikey'
      ? `'X-API-Key': 'bxc_votre_cle'`
      : `'Authorization': 'Bearer votre_jwt_token'`
  const pyAuth =
    auth === 'apikey'
      ? `'X-API-Key': 'bxc_votre_cle'`
      : `'Authorization': 'Bearer votre_jwt_token'`

  return {
    curl: `curl -X POST ${API_URL}/api/v1/connectors/${id}/execute \\
  ${curlAuth} \\
  -H "Content-Type: application/json" \\
  -d '{"params": {"intA": 10, "intB": 20}}'`,
    javascript: `const response = await fetch(
  '${API_URL}/api/v1/connectors/${id}/execute',
  {
    method: 'POST',
    headers: {
      ${jsAuth},
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ params: { intA: 10, intB: 20 } }),
  }
)
const data = await response.json()
console.log(data)`,
    python: `import requests

response = requests.post(
    '${API_URL}/api/v1/connectors/${id}/execute',
    headers={${pyAuth}},
    json={'params': {'intA': 10, 'intB': 20}},
)
print(response.json())`,
  }
}

function makeExampleSnippets(type: 'soap' | 'rest' | 'transform', id: string): Snippets {
  const connId = id || '{CONNECTOR_ID}'

  if (type === 'soap') {
    return {
      curl: `curl -X POST ${API_URL}/api/v1/connectors/${connId}/execute \\
  -H "X-API-Key: bxc_votre_cle" \\
  -H "Content-Type: application/json" \\
  -d '{"params": {"intA": 10, "intB": 20}}'`,
      javascript: `const res = await fetch(
  '${API_URL}/api/v1/connectors/${connId}/execute',
  {
    method: 'POST',
    headers: {
      'X-API-Key': 'bxc_votre_cle',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ params: { intA: 10, intB: 20 } }),
  }
)
console.log(await res.json())`,
      python: `import requests

r = requests.post(
    '${API_URL}/api/v1/connectors/${connId}/execute',
    headers={'X-API-Key': 'bxc_votre_cle'},
    json={'params': {'intA': 10, 'intB': 20}},
)
print(r.json())`,
    }
  }

  if (type === 'rest') {
    return {
      curl: `curl -X POST ${API_URL}/api/v1/connectors/${connId}/execute \\
  -H "X-API-Key: bxc_votre_cle" \\
  -H "Content-Type: application/json" \\
  -d '{"body": {"key": "value"}}'`,
      javascript: `const res = await fetch(
  '${API_URL}/api/v1/connectors/${connId}/execute',
  {
    method: 'POST',
    headers: {
      'X-API-Key': 'bxc_votre_cle',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ body: { key: 'value' } }),
  }
)
console.log(await res.json())`,
      python: `import requests

r = requests.post(
    '${API_URL}/api/v1/connectors/${connId}/execute',
    headers={'X-API-Key': 'bxc_votre_cle'},
    json={'body': {'key': 'value'}},
)
print(r.json())`,
    }
  }

  // transform
  return {
    curl: `curl -X POST ${API_URL}/api/v1/connectors/${connId}/execute \\
  -H "X-API-Key: bxc_votre_cle" \\
  -H "Content-Type: application/json" \\
  -d '{
  "params": {"intA": 5, "intB": 3},
  "transform_override": {
    "rename": {"AddResult": "total"}
  }
}'`,
    javascript: `const res = await fetch(
  '${API_URL}/api/v1/connectors/${connId}/execute',
  {
    method: 'POST',
    headers: {
      'X-API-Key': 'bxc_votre_cle',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      params: { intA: 5, intB: 3 },
      transform_override: { rename: { AddResult: 'total' } },
    }),
  }
)
console.log(await res.json())`,
    python: `import requests

r = requests.post(
    '${API_URL}/api/v1/connectors/${connId}/execute',
    headers={'X-API-Key': 'bxc_votre_cle'},
    json={
        'params': {'intA': 5, 'intB': 3},
        'transform_override': {'rename': {'AddResult': 'total'}},
    },
)
print(r.json())`,
  }
}

// ── small inline-copy component ────────────────────────────────────────────────

function InlineCopy({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button
      onClick={copy}
      className="ml-2 text-gray-400 hover:text-gray-700 transition-colors"
      title="Copier"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  )
}

// ── tabs helper ────────────────────────────────────────────────────────────────

function Tabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { value: T; label: string }[]
  active: T
  onChange: (v: T) => void
}) {
  return (
    <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
      {tabs.map((t) => (
        <button
          key={t.value}
          onClick={() => onChange(t.value)}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            active === t.value
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}

// ── page ───────────────────────────────────────────────────────────────────────

export function APIDocsPage() {
  const navigate = useNavigate()
  const [authTab, setAuthTab] = useState<'apikey' | 'jwt'>('apikey')
  const [exampleTab, setExampleTab] = useState<'soap' | 'rest' | 'transform'>('soap')

  useEffect(() => { document.title = 'bxChange — API Docs' }, [])

  const { data: connectors } = useQuery({
    queryKey: ['connectors'],
    queryFn: connectorsApi.getConnectors,
  })

  const activeConnectors = connectors?.filter((c) => c.status === 'active') ?? []
  const firstId = activeConnectors[0]?.id ?? ''

  return (
    <div className="flex flex-col gap-8 max-w-4xl">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-brand-50 rounded-lg">
          <Zap className="h-5 w-5 text-brand-600" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Documentation API</h1>
          <p className="text-sm text-gray-500">Intégrez bxChange dans vos applications en quelques minutes</p>
        </div>
      </div>

      {/* ── SECTION 1 — Quick start ─────────────────────────────────────────── */}
      <Card>
        <h2 className="font-semibold text-gray-900 mb-1">Démarrage rapide</h2>
        <p className="text-sm text-gray-500 mb-4">
          Copiez l'exemple ci-dessous et remplacez les valeurs par les vôtres.
        </p>

        <div className="mb-4">
          <Tabs
            tabs={[
              { value: 'apikey', label: 'Avec X-API-Key' },
              { value: 'jwt', label: 'Avec JWT Bearer' },
            ]}
            active={authTab}
            onChange={setAuthTab}
          />
        </div>

        {authTab === 'apikey' && (
          <p className="text-xs text-gray-500 mb-3">
            Créez une clé API dans{' '}
            <button
              onClick={() => navigate('/dashboard/api-keys')}
              className="text-brand-600 hover:underline"
            >
              API Keys
            </button>{' '}
            et utilisez-la dans le header <code className="bg-gray-100 px-1 rounded">X-API-Key</code>.
          </p>
        )}

        {authTab === 'jwt' && (
          <p className="text-xs text-gray-500 mb-3">
            Obtenez un access token via{' '}
            <code className="bg-gray-100 px-1 rounded">POST /api/v1/auth/login</code>{' '}
            et passez-le dans <code className="bg-gray-100 px-1 rounded">Authorization: Bearer ...</code>.
          </p>
        )}

        <CodeBlock snippets={makeQuickStart(authTab, firstId)} />
      </Card>

      {/* ── SECTION 2 — Swagger iframe ──────────────────────────────────────── */}
      <Card padding="none" className="overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-start justify-between gap-4">
          <div>
            <h2 className="font-semibold text-gray-900">Explorer l'API interactive</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              Cliquez sur <strong>Authorize</strong> 🔓 et entrez votre{' '}
              <code className="bg-gray-100 px-1 rounded text-xs">X-API-Key</code> pour tester
              directement depuis votre navigateur.
            </p>
          </div>
          <a
            href={SWAGGER_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0"
          >
            <Button variant="secondary" className="flex items-center gap-1.5 text-xs">
              <ExternalLink className="h-3.5 w-3.5" />
              Ouvrir Swagger
            </Button>
          </a>
        </div>
        <iframe
          src={SWAGGER_URL}
          title="bxChange Swagger UI"
          className="w-full border-0"
          style={{ height: 640 }}
        />
      </Card>

      {/* ── SECTION 3 — My API info ─────────────────────────────────────────── */}
      <Card>
        <h2 className="font-semibold text-gray-900 mb-4">Mes informations d'API</h2>

        <div className="flex flex-col gap-3">
          {/* base URL */}
          <div className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-2.5">
            <div>
              <p className="text-xs text-gray-500 mb-0.5">URL de base</p>
              <code className="text-sm font-mono text-gray-900">{API_URL}/api/v1</code>
            </div>
            <InlineCopy text={`${API_URL}/api/v1`} />
          </div>

          {/* CTA → API Keys */}
          <div className="flex items-center justify-between bg-brand-50 rounded-lg px-4 py-2.5">
            <div className="flex items-center gap-2">
              <Key className="h-4 w-4 text-brand-600" />
              <span className="text-sm text-brand-800">Besoin d'une clé API ?</span>
            </div>
            <Button
              size="sm"
              onClick={() => navigate('/dashboard/api-keys')}
              className="text-xs"
            >
              Générer une clé
            </Button>
          </div>

          {/* Active connectors list */}
          {activeConnectors.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
                Connecteurs actifs
              </p>
              <div className="flex flex-col gap-1.5">
                {activeConnectors.map((c) => (
                  <div
                    key={c.id}
                    className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-2"
                  >
                    <div className="flex items-center gap-2">
                      {c.type === 'soap' ? (
                        <Wifi className="h-3.5 w-3.5 text-purple-500" />
                      ) : (
                        <Globe className="h-3.5 w-3.5 text-blue-500" />
                      )}
                      <span className="text-sm font-medium text-gray-800">{c.name}</span>
                      <Badge variant={c.type === 'soap' ? 'blue' : 'gray'} className="text-xs">
                        {c.type.toUpperCase()}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-1">
                      <code className="text-xs font-mono text-gray-500 truncate max-w-[180px]">
                        {c.id}
                      </code>
                      <InlineCopy text={c.id} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeConnectors.length === 0 && (
            <p className="text-sm text-gray-500 text-center py-4">
              Aucun connecteur actif.{' '}
              <button
                onClick={() => navigate('/dashboard/connectors')}
                className="text-brand-600 hover:underline"
              >
                Créez votre premier connecteur
              </button>
            </p>
          )}
        </div>
      </Card>

      {/* ── SECTION 4 — Examples ────────────────────────────────────────────── */}
      <Card>
        <h2 className="font-semibold text-gray-900 mb-4">Exemples par cas d'usage</h2>

        <div className="mb-5">
          <Tabs
            tabs={[
              { value: 'soap', label: 'SOAP' },
              { value: 'rest', label: 'REST' },
              { value: 'transform', label: 'Avec Transform' },
            ]}
            active={exampleTab}
            onChange={setExampleTab}
          />
        </div>

        {exampleTab === 'soap' && (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-gray-600">
              Appel d'un connecteur SOAP avec des paramètres nommés. Les clés de{' '}
              <code className="bg-gray-100 px-1 rounded text-xs">params</code> correspondent aux
              arguments de l'opération WSDL.
            </p>
            <CodeBlock snippets={makeExampleSnippets('soap', firstId)} />
          </div>
        )}

        {exampleTab === 'rest' && (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-gray-600">
              Appel d'un connecteur REST. Utilisez{' '}
              <code className="bg-gray-100 px-1 rounded text-xs">body</code> pour les requêtes POST/PUT
              et <code className="bg-gray-100 px-1 rounded text-xs">params</code> pour les query strings.
            </p>
            <CodeBlock snippets={makeExampleSnippets('rest', firstId)} />
          </div>
        )}

        {exampleTab === 'transform' && (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-gray-600">
              Utilisez <code className="bg-gray-100 px-1 rounded text-xs">transform_override</code> pour
              appliquer des règles de transformation à la volée sans modifier la configuration du
              connecteur. Pratique pour tester de nouveaux mappings.
            </p>
            <CodeBlock snippets={makeExampleSnippets('transform', firstId)} />
          </div>
        )}
      </Card>
    </div>
  )
}
