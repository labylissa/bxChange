interface JsonViewerProps {
  data: unknown
  maxHeight?: string
}

function colorize(json: string): string {
  return json
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(
      /("(\\u[\dA-Fa-f]{4}|\\[^u]|[^"\\])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
      (match) => {
        let cls = 'text-blue-600'
        if (/^"/.test(match)) {
          cls = /:$/.test(match) ? 'text-purple-700 font-medium' : 'text-green-700'
        } else if (/true|false/.test(match)) {
          cls = 'text-orange-600'
        } else if (/null/.test(match)) {
          cls = 'text-gray-400'
        }
        return `<span class="${cls}">${match}</span>`
      }
    )
}

export function JsonViewer({ data, maxHeight = '400px' }: JsonViewerProps) {
  const formatted = JSON.stringify(data, null, 2)
  return (
    <pre
      className="text-xs font-mono bg-gray-900 text-gray-100 rounded-lg p-4 overflow-auto leading-relaxed"
      style={{ maxHeight }}
      dangerouslySetInnerHTML={{ __html: colorize(formatted) }}
    />
  )
}
