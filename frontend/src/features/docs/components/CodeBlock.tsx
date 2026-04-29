import { useState } from 'react'
import { Copy, Check } from 'lucide-react'

type Lang = 'curl' | 'javascript' | 'python'

export interface Snippets {
  curl: string
  javascript: string
  python: string
}

interface CodeBlockProps {
  snippets: Snippets
  defaultLang?: Lang
}

const LANG_LABELS: Record<Lang, string> = {
  curl: 'cURL',
  javascript: 'JavaScript',
  python: 'Python',
}

export function CodeBlock({ snippets, defaultLang = 'curl' }: CodeBlockProps) {
  const [lang, setLang] = useState<Lang>(defaultLang)
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(snippets[lang])
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // fallback: select text
    }
  }

  return (
    <div className="rounded-xl overflow-hidden border border-gray-700 text-sm">
      {/* header bar */}
      <div className="flex items-center justify-between bg-gray-800 px-4 py-2">
        <div className="flex gap-1">
          {(Object.keys(snippets) as Lang[]).map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                lang === l
                  ? 'bg-gray-600 text-white'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700'
              }`}
            >
              {LANG_LABELS[l]}
            </button>
          ))}
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors px-2 py-1 rounded hover:bg-gray-700"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-green-400" />
              <span className="text-green-400">Copié !</span>
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              <span>Copier</span>
            </>
          )}
        </button>
      </div>
      {/* code */}
      <pre className="bg-gray-900 text-gray-100 text-xs font-mono p-4 overflow-x-auto leading-relaxed whitespace-pre">
        {snippets[lang]}
      </pre>
    </div>
  )
}
