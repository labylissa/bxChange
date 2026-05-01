import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, Copy, Download } from 'lucide-react'
import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import python from 'highlight.js/lib/languages/python'
import javascript from 'highlight.js/lib/languages/javascript'
import php from 'highlight.js/lib/languages/php'
import java from 'highlight.js/lib/languages/java'
import 'highlight.js/styles/github-dark.css'
import { apiKeysApi } from '@/lib/api/apiKeys'
import { snippetsApi } from '@/lib/api/snippets'

hljs.registerLanguage('bash', bash)
hljs.registerLanguage('python', python)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('php', php)
hljs.registerLanguage('java', java)

const LANGS = [
  { id: 'curl', label: 'cURL', ext: 'sh', hlLang: 'bash' },
  { id: 'python', label: 'Python', ext: 'py', hlLang: 'python' },
  { id: 'javascript', label: 'JavaScript', ext: 'js', hlLang: 'javascript' },
  { id: 'php', label: 'PHP', ext: 'php', hlLang: 'php' },
  { id: 'java', label: 'Java', ext: 'java', hlLang: 'java' },
]

interface Props {
  connectorId: string
  connectorName: string
}

export function IntegrationTab({ connectorId, connectorName }: Props) {
  const [lang, setLang] = useState('curl')
  const [selectedKeyId, setSelectedKeyId] = useState('')
  const [copied, setCopied] = useState(false)
  const codeRef = useRef<HTMLElement>(null)

  const { data: apiKeys = [] } = useQuery({
    queryKey: ['api-keys'],
    queryFn: apiKeysApi.getApiKeys,
  })

  const { data: snippetData, isLoading } = useQuery({
    queryKey: ['snippet', connectorId, lang, selectedKeyId],
    queryFn: () => snippetsApi.getSnippet(connectorId, lang, selectedKeyId || undefined),
  })

  const currentLang = LANGS.find((l) => l.id === lang)!

  useEffect(() => {
    if (codeRef.current && snippetData?.snippet) {
      delete (codeRef.current.dataset as Record<string, string>)['highlighted']
      codeRef.current.textContent = snippetData.snippet
      hljs.highlightElement(codeRef.current)
    }
  }, [snippetData?.snippet, lang])

  async function copySnippet() {
    if (!snippetData?.snippet) return
    await navigator.clipboard.writeText(snippetData.snippet)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  function downloadSnippet() {
    if (!snippetData?.snippet) return
    const slug = connectorName.replace(/[^a-zA-Z0-9]+/g, '_').toLowerCase()
    const pascal = connectorName.replace(/[^a-zA-Z0-9]/g, '')
    const filename =
      lang === 'java' ? `${pascal}Client.java` : `${slug}_client.${currentLang.ext}`

    const blob = new Blob([snippetData.snippet], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col gap-5 max-w-3xl">
      {/* Language tabs */}
      <div className="flex gap-2 flex-wrap">
        {LANGS.map((l) => (
          <button
            key={l.id}
            type="button"
            onClick={() => setLang(l.id)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
              lang === l.id
                ? 'bg-brand-600 text-white border-brand-600'
                : 'bg-white text-gray-600 border-gray-300 hover:border-brand-400'
            }`}
          >
            {l.label}
          </button>
        ))}
      </div>

      {/* Code block */}
      <div className="rounded-xl overflow-hidden border border-gray-700">
        <div className="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-700">
          <span className="text-xs text-gray-400 font-mono">{currentLang.label}</span>
          <div className="flex gap-1">
            <button
              onClick={copySnippet}
              disabled={isLoading || !snippetData}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs text-gray-400 hover:text-white hover:bg-gray-700 transition-colors disabled:opacity-40"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? 'Copié !' : 'Copier'}
            </button>
            <button
              onClick={downloadSnippet}
              disabled={isLoading || !snippetData}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs text-gray-400 hover:text-white hover:bg-gray-700 transition-colors disabled:opacity-40"
            >
              <Download size={12} />
              Télécharger
            </button>
          </div>
        </div>

        <div className="bg-[#0d1117] overflow-x-auto min-h-[200px]">
          {isLoading ? (
            <div className="h-48 flex items-center justify-center">
              <span className="text-gray-500 text-sm">Chargement...</span>
            </div>
          ) : (
            <pre className="p-5 text-sm leading-relaxed m-0">
              <code ref={codeRef} className={`language-${currentLang.hlLang} !bg-transparent`} />
            </pre>
          )}
        </div>
      </div>

      {/* API key selector */}
      <div className="border border-gray-200 rounded-xl p-4 flex flex-col gap-3 bg-gray-50">
        <p className="text-sm font-medium text-gray-700">🔑 Clé API à utiliser</p>
        <select
          className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
          value={selectedKeyId}
          onChange={(e) => setSelectedKeyId(e.target.value)}
        >
          <option value="">— Sélectionner une clé API (optionnel) —</option>
          {apiKeys
            .filter((k) => k.is_active)
            .map((k) => (
              <option key={k.id} value={k.id}>
                {k.name}
              </option>
            ))}
        </select>
        <p className="text-xs text-gray-400">
          Le nom de la clé apparaît dans le snippet comme indicateur. Ne partagez jamais votre clé
          en clair.
        </p>
      </div>
    </div>
  )
}
