import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, GitMerge, Plus } from 'lucide-react'

// ── SVG Pipeline Diagram ───────────────────────────────────────────────────────

function PipelineSVG() {
  return (
    <svg viewBox="0 0 400 420" className="w-full max-w-md mx-auto" aria-hidden="true">
      <style>{`
        @keyframes flow { 0%,100%{opacity:.3} 50%{opacity:1} }
        .flow1{animation:flow 2s ease-in-out infinite}
        .flow2{animation:flow 2s ease-in-out .4s infinite}
        .flow3{animation:flow 2s ease-in-out .8s infinite}
        .flow4{animation:flow 2s ease-in-out 1.2s infinite}
      `}</style>

      {/* Input */}
      <rect x="125" y="10" width="150" height="40" rx="20" fill="#f3f4f6" stroke="#d1d5db" strokeWidth="1.5"/>
      <text x="200" y="35" textAnchor="middle" fontSize="12" fill="#6b7280" fontFamily="system-ui">Un seul appel API</text>

      {/* Arrow down */}
      <line x1="200" y1="50" x2="200" y2="80" stroke="#d1d5db" strokeWidth="1.5" className="flow1"/>
      <polygon points="195,78 205,78 200,88" fill="#d1d5db" className="flow1"/>

      {/* Pipeline box */}
      <rect x="100" y="88" width="200" height="52" rx="10" fill="#3b82f6" />
      <text x="200" y="108" textAnchor="middle" fontSize="11" fill="white" fontWeight="600" fontFamily="system-ui">Pipeline bxChange</text>
      <text x="200" y="126" textAnchor="middle" fontSize="10" fill="#bfdbfe" fontFamily="system-ui">orchestration automatique</text>

      {/* Three arrows spreading */}
      <line x1="145" y1="140" x2="80" y2="185" stroke="#d1d5db" strokeWidth="1.5" className="flow2"/>
      <polygon points="75,181 85,181 80,191" fill="#d1d5db" className="flow2"/>
      <line x1="200" y1="140" x2="200" y2="185" stroke="#d1d5db" strokeWidth="1.5" className="flow2"/>
      <polygon points="195,183 205,183 200,193" fill="#d1d5db" className="flow2"/>
      <line x1="255" y1="140" x2="320" y2="185" stroke="#d1d5db" strokeWidth="1.5" className="flow2"/>
      <polygon points="315,181 325,181 320,191" fill="#d1d5db" className="flow2"/>

      {/* Service boxes */}
      <rect x="30" y="193" width="100" height="44" rx="8" fill="#3b82f6"/>
      <text x="80" y="212" textAnchor="middle" fontSize="10" fill="white" fontWeight="600" fontFamily="system-ui">SOAP</text>
      <text x="80" y="227" textAnchor="middle" fontSize="9" fill="#bfdbfe" fontFamily="system-ui">Service 1</text>

      <rect x="150" y="193" width="100" height="44" rx="8" fill="#10b981"/>
      <text x="200" y="212" textAnchor="middle" fontSize="10" fill="white" fontWeight="600" fontFamily="system-ui">REST</text>
      <text x="200" y="227" textAnchor="middle" fontSize="9" fill="#a7f3d0" fontFamily="system-ui">Service 2</text>

      <rect x="270" y="193" width="100" height="44" rx="8" fill="#3b82f6"/>
      <text x="320" y="212" textAnchor="middle" fontSize="10" fill="white" fontWeight="600" fontFamily="system-ui">SOAP</text>
      <text x="320" y="227" textAnchor="middle" fontSize="9" fill="#bfdbfe" fontFamily="system-ui">Service 3</text>

      {/* Three arrows converging */}
      <line x1="80" y1="237" x2="160" y2="285" stroke="#d1d5db" strokeWidth="1.5" className="flow3"/>
      <line x1="200" y1="237" x2="200" y2="285" stroke="#d1d5db" strokeWidth="1.5" className="flow3"/>
      <line x1="320" y1="237" x2="240" y2="285" stroke="#d1d5db" strokeWidth="1.5" className="flow3"/>
      <polygon points="195,283 205,283 200,293" fill="#d1d5db" className="flow3"/>

      {/* Merge box */}
      <rect x="110" y="293" width="180" height="40" rx="8" fill="#f9fafb" stroke="#e5e7eb" strokeWidth="1.5"/>
      <text x="200" y="318" textAnchor="middle" fontSize="11" fill="#6b7280" fontFamily="system-ui">Fusion automatique</text>

      {/* Arrow down */}
      <line x1="200" y1="333" x2="200" y2="358" stroke="#d1d5db" strokeWidth="1.5" className="flow4"/>
      <polygon points="195,356 205,356 200,366" fill="#d1d5db" className="flow4"/>

      {/* Result box */}
      <rect x="110" y="366" width="180" height="44" rx="10" fill="#ecfdf5" stroke="#10b981" strokeWidth="1.5"/>
      <text x="200" y="385" textAnchor="middle" fontSize="11" fill="#065f46" fontWeight="700" fontFamily="system-ui">Résultat unifié</text>
      <text x="200" y="401" textAnchor="middle" fontSize="9" fill="#34d399" fontFamily="system-ui">JSON propre · prêt à l'emploi</text>
    </svg>
  )
}

// ── Accordion ──────────────────────────────────────────────────────────────────

function Accordion({ items }: { items: { id: string; title: string; content: React.ReactNode }[] }) {
  const [open, setOpen] = useState<string | null>(null)
  return (
    <div className="divide-y divide-gray-200 border border-gray-200 rounded-xl overflow-hidden">
      {items.map((item) => (
        <div key={item.id}>
          <button
            onClick={() => setOpen(open === item.id ? null : item.id)}
            className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-gray-50 transition-colors"
          >
            <span className="font-medium text-gray-900">{item.title}</span>
            <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${open === item.id ? 'rotate-180' : ''}`} />
          </button>
          {open === item.id && (
            <div className="px-5 pb-5 pt-1 text-sm text-gray-600 bg-white">
              {item.content}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Code block ────────────────────────────────────────────────────────────────

function CodeBlock({ code, lang }: { code: string; lang: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <div className="relative group rounded-lg overflow-hidden border border-gray-200">
      <div className="flex items-center justify-between bg-gray-800 px-4 py-2">
        <span className="text-xs text-gray-400 font-mono">{lang}</span>
        <button
          onClick={copy}
          className="text-xs text-gray-400 hover:text-white transition-colors opacity-0 group-hover:opacity-100"
        >
          {copied ? '✓ Copié' : 'Copier'}
        </button>
      </div>
      <pre className="bg-gray-900 text-gray-100 text-xs p-4 overflow-x-auto leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  )
}

// ── Variable table ─────────────────────────────────────────────────────────────

function VarTable() {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-50">
            <th className="border border-gray-200 px-3 py-2 text-left font-semibold text-gray-700">Variable</th>
            <th className="border border-gray-200 px-3 py-2 text-left font-semibold text-gray-700">Description</th>
            <th className="border border-gray-200 px-3 py-2 text-left font-semibold text-gray-700">Exemple</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {[
            ['{{input.X}}', 'Paramètre passé à l\'appel initial', '{{input.numeroContrat}}'],
            ['{{steps.N.result.X}}', 'Valeur extraite du résultat du step N', '{{steps.1.result.immatriculation}}'],
            ['{{steps.N.status}}', 'Statut d\'un step (success / error / skipped)', '{{steps.2.status}}'],
            ['{{tenant.id}}', 'Identifiant du tenant courant', '{{tenant.id}}'],
          ].map(([v, d, e]) => (
            <tr key={v} className="hover:bg-gray-50">
              <td className="border border-gray-200 px-3 py-2 font-mono text-xs text-blue-700 bg-blue-50">{v}</td>
              <td className="border border-gray-200 px-3 py-2 text-gray-600">{d}</td>
              <td className="border border-gray-200 px-3 py-2 font-mono text-xs text-gray-500">{e}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Merge strategy table ───────────────────────────────────────────────────────

function MergeTable() {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-50">
            <th className="border border-gray-200 px-3 py-2 text-left font-semibold text-gray-700">Stratégie</th>
            <th className="border border-gray-200 px-3 py-2 text-left font-semibold text-gray-700">Comportement</th>
            <th className="border border-gray-200 px-3 py-2 text-left font-semibold text-gray-700">Quand l'utiliser</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {[
            ['merge', 'Fusionne tous les résultats en un seul objet (deep merge)', 'Services retournant des données complémentaires'],
            ['first', 'Retourne uniquement le résultat du premier step réussi', 'Services redondants — fallback'],
            ['last', 'Retourne uniquement le résultat du dernier step réussi', 'Chaque step enrichit le précédent'],
            ['custom', 'Retourne {step_1: …, step_2: …}', 'Contrôle via output_transform'],
          ].map(([s, b, w]) => (
            <tr key={s} className="hover:bg-gray-50">
              <td className="border border-gray-200 px-3 py-2 font-mono text-xs font-bold text-brand-700">{s}</td>
              <td className="border border-gray-200 px-3 py-2 text-gray-600">{b}</td>
              <td className="border border-gray-200 px-3 py-2 text-gray-500 text-xs">{w}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── On-error table ─────────────────────────────────────────────────────────────

function OnErrorTable() {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-50">
            <th className="border border-gray-200 px-3 py-2 text-left font-semibold text-gray-700">Option</th>
            <th className="border border-gray-200 px-3 py-2 text-left font-semibold text-gray-700">Comportement</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {[
            ['stop', 'Arrêter immédiatement le pipeline et retourner l\'erreur'],
            ['skip', 'Ignorer ce step — continuer avec les steps suivants sans son résultat'],
            ['continue', 'Continuer même en erreur — inclure l\'erreur dans le résultat final'],
          ].map(([o, b]) => (
            <tr key={o} className="hover:bg-gray-50">
              <td className="border border-gray-200 px-3 py-2 font-mono text-xs font-bold text-red-700">{o}</td>
              <td className="border border-gray-200 px-3 py-2 text-gray-600">{b}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Business examples ──────────────────────────────────────────────────────────

const EXAMPLES = [
  {
    id: 'insurance',
    label: 'Assurance Auto',
    desc: 'Vérification véhicule + scoring risque',
    pipeline: `Pipeline : "Vérification véhicule + scoring risque"

Step 1 — ConnecteurSIV (SOAP)
  Nom    : Récupération véhicule
  Params : { "immatriculation": "{{input.immatriculation}}" }

Step 2 — ConnecteurHistorique (SOAP)
  Nom    : Historique sinistres
  Params : {
    "vin": "{{steps.1.result.numeroVIN}}",
    "proprietaire": "{{input.nomProprietaire}}"
  }

Step 3 — ConnecteurScoring (REST)
  Nom    : Calcul score risque
  Params : {
    "age_vehicule": "{{steps.1.result.anneeConstruction}}",
    "nb_sinistres": "{{steps.2.result.nombreSinistres}}",
    "puissance": "{{steps.1.result.puissanceFiscale}}"
  }

Fusion : merge`,
    curl: `curl -X POST https://api.bxchange.io/api/v1/pipelines/{id}/execute \\
  -H "X-API-Key: bxc_..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "params": {
      "immatriculation": "AB-123-CD",
      "nomProprietaire": "Dupont Jean"
    }
  }'`,
    result: `{
  "numeroVIN": "VF1RFD...",
  "marque": "Renault",
  "modele": "Clio",
  "anneeConstruction": 2018,
  "puissanceFiscale": 6,
  "nombreSinistres": 1,
  "dernierSinistre": "2022-03-15",
  "score_risque": 72,
  "categorie_risque": "MODERE",
  "prime_estimee": 485.50
}`,
  },
  {
    id: 'banking',
    label: 'Banque — KYC',
    desc: 'Vérification d\'identité et scoring crédit en parallèle',
    pipeline: `Pipeline : "Vérification KYC client"

Step 1 — ConnecteurIdentite (SOAP) [séquentiel]
  Nom    : Vérification identité
  Params : {
    "nom": "{{input.nom}}",
    "prenom": "{{input.prenom}}",
    "dateNaissance": "{{input.dateNaissance}}"
  }

Step 2 — ConnecteurBanqueDeFrance (SOAP) [parallèle]
  Nom    : Fichage BDF
  Params : { "iban": "{{input.iban}}" }

Step 3 — ConnecteurScoreCredit (REST) [parallèle]
  Nom      : Score crédit
  Params   : { "siren": "{{steps.1.result.sirenEntreprise}}" }
  Condition: "{{steps.1.status}} == 'success'"

Fusion : merge`,
    curl: `curl -X POST https://api.bxchange.io/api/v1/pipelines/{id}/execute \\
  -H "X-API-Key: bxc_..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "params": {
      "nom": "Martin",
      "prenom": "Sophie",
      "dateNaissance": "1985-04-12",
      "iban": "FR7630006000011234567890189"
    }
  }'`,
    result: `{
  "identite_verifiee": true,
  "sirenEntreprise": "123456789",
  "fiché_bdf": false,
  "score_credit": 820,
  "capacite_emprunt": 250000,
  "categorie": "EXCELLENT"
}`,
  },
  {
    id: 'fallback',
    label: 'Fallback technique',
    desc: 'Service principal avec repli automatique',
    pipeline: `Pipeline : "Service avec fallback"

Step 1 — ConnecteurPrincipal (SOAP)
  on_error : skip   ← ne pas arrêter si erreur
  Params   : { "id": "{{input.id}}" }

Step 2 — ConnecteurFallback (SOAP)
  Condition: "{{steps.1.status}} == 'error'"
  Params   : { "id": "{{input.id}}" }
  ← s'exécute SEULEMENT si step 1 a échoué

Fusion : first
← retourne le premier résultat disponible`,
    curl: `curl -X POST https://api.bxchange.io/api/v1/pipelines/{id}/execute \\
  -H "X-API-Key: bxc_..." \\
  -H "Content-Type: application/json" \\
  -d '{"params": {"id": "REF-2024-001"}}'`,
    result: `{
  "execution_id": "...",
  "status": "success",
  "steps": {
    "1": { "status": "error", "error_message": "Service unavailable" },
    "2": { "status": "success" }
  },
  "result": { "data": "...", "source": "fallback" }
}`,
  },
]

// ── Code snippets ──────────────────────────────────────────────────────────────

const SNIPPETS: Record<string, string> = {
  curl: `curl -X POST https://api.bxchange.io/api/v1/pipelines/{pipeline_id}/execute \\
  -H "X-API-Key: bxc_..." \\
  -H "Content-Type: application/json" \\
  -d '{"params": {"immatriculation": "AB-123-CD"}}'`,

  python: `import requests

resp = requests.post(
    "https://api.bxchange.io/api/v1/pipelines/{pipeline_id}/execute",
    headers={"X-API-Key": "bxc_..."},
    json={"params": {"immatriculation": "AB-123-CD"}}
)
data = resp.json()
print(data["result"])`,

  javascript: `const resp = await fetch(
  "https://api.bxchange.io/api/v1/pipelines/{pipeline_id}/execute",
  {
    method: "POST",
    headers: {
      "X-API-Key": "bxc_...",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      params: { immatriculation: "AB-123-CD" }
    }),
  }
);
const data = await resp.json();
console.log(data.result);`,

  php: `<?php
$resp = file_get_contents(
    "https://api.bxchange.io/api/v1/pipelines/{pipeline_id}/execute",
    false,
    stream_context_create([
        "http" => [
            "method"  => "POST",
            "header"  => "X-API-Key: bxc_...\\r\\nContent-Type: application/json\\r\\n",
            "content" => json_encode(["params" => ["immatriculation" => "AB-123-CD"]]),
        ]
    ])
);
$data = json_decode($resp, true);`,

  java: `HttpClient client = HttpClient.newHttpClient();
HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create("https://api.bxchange.io/api/v1/pipelines/{id}/execute"))
    .header("X-API-Key", "bxc_...")
    .header("Content-Type", "application/json")
    .POST(HttpRequest.BodyPublishers.ofString(
        "{\"params\":{\"immatriculation\":\"AB-123-CD\"}}"
    ))
    .build();
HttpResponse<String> resp = client.send(request,
    HttpResponse.BodyHandlers.ofString());`,
}

const SNIPPET_LANGS = ['curl', 'python', 'javascript', 'php', 'java']

// ── Main page ──────────────────────────────────────────────────────────────────

const SECTIONS = [
  { id: 'intro', label: 'Introduction' },
  { id: 'concepts', label: 'Concepts clés' },
  { id: 'examples', label: 'Exemples métier' },
  { id: 'quota', label: 'Quota' },
  { id: 'integration', label: 'Intégration' },
]

export function PipelineDocs() {
  const [exampleTab, setExampleTab] = useState('insurance')
  const [snippetLang, setSnippetLang] = useState('curl')

  const accordionItems = [
    {
      id: 'steps',
      title: 'Steps — comment ça fonctionne',
      content: (
        <div className="space-y-3">
          <p>Chaque étape appelle un connecteur (SOAP ou REST). Les steps s'exécutent dans l'ordre défini par <code className="bg-gray-100 px-1 rounded text-xs">step_order</code>.</p>
          <p>Si deux steps ont le même <code className="bg-gray-100 px-1 rounded text-xs">step_order</code> et le mode <strong>parallèle</strong>, ils tournent simultanément via <code className="bg-gray-100 px-1 rounded text-xs">asyncio.gather</code> — utile pour appeler deux services indépendants et économiser du temps.</p>
          <p>Chaque step dispose de son propre <strong>params_template</strong> — un objet JSON avec des variables <code className="bg-gray-100 px-1 rounded text-xs font-mono">{'{{input.X}}'}</code> ou <code className="bg-gray-100 px-1 rounded text-xs font-mono">{'{{steps.N.result.X}}'}</code> qui sont résolues juste avant l'appel.</p>
        </div>
      ),
    },
    {
      id: 'variables',
      title: 'Variables de template',
      content: (
        <div className="space-y-3">
          <p>Utilisez ces variables dans le champ <strong>params_template</strong> de chaque step :</p>
          <VarTable />
          <p className="text-xs text-gray-500 mt-2">Le chemin utilise la notation pointée : <code className="bg-gray-100 px-1 rounded">{'{{steps.1.result.adresse.codePostal}}'}</code> pour accéder à un champ imbriqué.</p>
        </div>
      ),
    },
    {
      id: 'merge',
      title: 'Stratégies de fusion',
      content: (
        <div className="space-y-3">
          <p>Après l'exécution de tous les steps, bxChange fusionne les résultats selon la stratégie choisie :</p>
          <MergeTable />
          <p className="text-xs text-gray-500 mt-2">Les steps en erreur sont toujours exclus de la fusion, quelle que soit la stratégie.</p>
        </div>
      ),
    },
    {
      id: 'onerror',
      title: 'Comportement en cas d\'erreur',
      content: (
        <div className="space-y-3">
          <p>Chaque step a un champ <code className="bg-gray-100 px-1 rounded text-xs">on_error</code> qui définit ce qui se passe si ce step échoue :</p>
          <OnErrorTable />
          <p className="text-xs text-gray-500 mt-2">Astuce : combinez <code className="bg-gray-100 px-1 rounded">on_error: skip</code> sur le step 1 avec une <strong>condition</strong> <code className="bg-gray-100 px-1 rounded font-mono text-xs">{'{{steps.1.status}} == \'error\''}</code> sur le step 2 pour implémenter un fallback.</p>
        </div>
      ),
    },
  ]

  const selectedExample = EXAMPLES.find((e) => e.id === exampleTab) ?? EXAMPLES[0]

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex gap-8">
        {/* Left sticky nav — desktop */}
        <nav className="hidden lg:block w-44 flex-shrink-0">
          <div className="sticky top-6 space-y-1">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3 px-2">Sur cette page</p>
            {SECTIONS.map((s) => (
              <a
                key={s.id}
                href={`#${s.id}`}
                className="block px-2 py-1.5 text-sm text-gray-500 hover:text-brand-600 hover:bg-brand-50 rounded-lg transition-colors"
              >
                {s.label}
              </a>
            ))}
            <div className="mt-6 pt-4 border-t border-gray-100">
              <Link
                to="/dashboard/pipelines/new"
                className="flex items-center gap-1.5 px-2 py-1.5 text-sm font-medium text-brand-600 hover:bg-brand-50 rounded-lg transition-colors"
              >
                <Plus className="h-3.5 w-3.5" />
                Créer un pipeline
              </Link>
            </div>
          </div>
        </nav>

        {/* Main content */}
        <div className="flex-1 min-w-0 space-y-14 pb-16">

          {/* Section 1 — Introduction */}
          <section id="intro">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-8 h-8 rounded-lg bg-brand-100 flex items-center justify-center flex-shrink-0">
                <GitMerge className="h-4 w-4 text-brand-600" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900">Qu'est-ce qu'un Pipeline ?</h1>
            </div>

            <div className="grid md:grid-cols-2 gap-8 items-center">
              <div className="space-y-4">
                <p className="text-gray-600 leading-relaxed">
                  Un <strong>Pipeline</strong> enchaîne plusieurs connecteurs (SOAP ou REST) en <strong>un seul appel API</strong>.
                </p>
                <p className="text-gray-600 leading-relaxed">
                  Au lieu d'appeler 3 services séparément et de fusionner les résultats dans votre code, bxChange le fait automatiquement. Vous recevez un JSON propre, prêt à l'emploi.
                </p>
                <div className="space-y-2">
                  {[
                    'Réduction du nombre d\'appels côté client',
                    'Chaining de données entre services (output → input)',
                    'Gestion d\'erreurs et fallback intégrés',
                    'Un seul point d\'authentification (API Key)',
                  ].map((benefit) => (
                    <div key={benefit} className="flex items-start gap-2 text-sm text-gray-600">
                      <span className="mt-0.5 w-4 h-4 rounded-full bg-green-100 text-green-600 flex items-center justify-center flex-shrink-0 text-xs">✓</span>
                      {benefit}
                    </div>
                  ))}
                </div>
              </div>
              <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
                <PipelineSVG />
              </div>
            </div>
          </section>

          {/* Section 2 — Concepts */}
          <section id="concepts">
            <h2 className="text-xl font-bold text-gray-900 mb-6">Concepts clés</h2>
            <Accordion items={accordionItems} />
          </section>

          {/* Section 3 — Business examples */}
          <section id="examples">
            <h2 className="text-xl font-bold text-gray-900 mb-2">Exemples métier</h2>
            <p className="text-sm text-gray-500 mb-6">Des pipelines concrets prêts à adapter à votre contexte.</p>

            {/* Tabs */}
            <div className="flex gap-1 border-b border-gray-200 mb-6">
              {EXAMPLES.map((e) => (
                <button
                  key={e.id}
                  onClick={() => setExampleTab(e.id)}
                  className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
                    exampleTab === e.id
                      ? 'border-brand-600 text-brand-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {e.label}
                </button>
              ))}
            </div>

            <div className="space-y-4">
              <p className="text-sm text-gray-600 italic">{selectedExample.desc}</p>

              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Configuration du pipeline</p>
                <CodeBlock code={selectedExample.pipeline} lang="pipeline config" />
              </div>

              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Appel API</p>
                <CodeBlock code={selectedExample.curl} lang="bash" />
              </div>

              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Résultat</p>
                <CodeBlock code={selectedExample.result} lang="json" />
              </div>
            </div>
          </section>

          {/* Section 4 — Quota */}
          <section id="quota">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Quota et facturation</h2>
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 space-y-3">
              <div className="flex items-start gap-3">
                <span className="text-2xl">⚡</span>
                <div className="space-y-2">
                  <p className="font-semibold text-amber-900">Chaque step consomme 1 exécution de votre quota</p>
                  <p className="text-sm text-amber-800">Un pipeline de 3 steps = 3 exécutions consommées par appel.</p>
                  <p className="text-sm text-amber-800">Un step <strong>ignoré</strong> (status: <code className="bg-amber-100 px-1 rounded">skipped</code>) ne consomme pas de quota — seulement les steps qui appellent effectivement le connecteur.</p>
                </div>
              </div>
              <div className="border-t border-amber-200 pt-3 text-sm text-amber-700">
                Consultez votre quota sur la page <Link to="/dashboard/billing" className="underline font-medium">Facturation</Link>.
              </div>
            </div>
          </section>

          {/* Section 5 — Integration */}
          <section id="integration">
            <h2 className="text-xl font-bold text-gray-900 mb-2">Intégration</h2>
            <p className="text-sm text-gray-500 mb-6">
              Remplacez <code className="bg-gray-100 px-1 rounded text-xs">{'{pipeline_id}'}</code> par l'ID de votre pipeline et <code className="bg-gray-100 px-1 rounded text-xs">bxc_...</code> par votre clé API.
            </p>

            {/* Lang tabs */}
            <div className="flex gap-1 mb-4">
              {SNIPPET_LANGS.map((lang) => (
                <button
                  key={lang}
                  onClick={() => setSnippetLang(lang)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    snippetLang === lang
                      ? 'bg-brand-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {lang}
                </button>
              ))}
            </div>

            <CodeBlock code={SNIPPETS[snippetLang]} lang={snippetLang} />

            <div className="mt-6 p-4 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-600 space-y-1">
              <p><strong>Réponse :</strong> <code className="bg-gray-100 px-1 rounded text-xs">{'{"execution_id": "...", "status": "success", "result": {...}, "steps": {...}, "duration_ms": 342}'}</code></p>
              <p className="text-xs text-gray-500">Gérez vos clés API depuis la page <Link to="/dashboard/api-keys" className="underline">API Keys</Link>.</p>
            </div>
          </section>

          {/* Bottom CTA */}
          <div className="border-t border-gray-200 pt-8 text-center space-y-3">
            <p className="text-gray-600">Prêt à créer votre premier pipeline ?</p>
            <Link
              to="/dashboard/pipelines/new"
              className="inline-flex items-center gap-2 px-6 py-3 bg-brand-600 text-white rounded-xl font-medium hover:bg-brand-700 transition-colors"
            >
              <Plus className="h-4 w-4" />
              Créer mon premier pipeline
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
