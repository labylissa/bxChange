import { Plus, Trash2 } from 'lucide-react'

export interface KVPair {
  key: string
  value: string
}

interface Props {
  label: string
  pairs: KVPair[]
  onChange: (pairs: KVPair[]) => void
  keyPlaceholder?: string
  valuePlaceholder?: string
  addLabel?: string
}

export function KeyValueEditor({
  label,
  pairs,
  onChange,
  keyPlaceholder = 'Clé',
  valuePlaceholder = 'Valeur',
  addLabel = 'Ajouter',
}: Props) {
  function update(i: number, field: 'key' | 'value', val: string) {
    const next = [...pairs]
    next[i] = { ...next[i], [field]: val }
    onChange(next)
  }

  function remove(i: number) {
    onChange(pairs.filter((_, j) => j !== i))
  }

  function add() {
    onChange([...pairs, { key: '', value: '' }])
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="text-sm font-medium text-gray-700">{label}</label>
        <button
          type="button"
          onClick={add}
          className="text-xs text-brand-600 hover:underline flex items-center gap-1"
        >
          <Plus className="h-3 w-3" /> {addLabel}
        </button>
      </div>
      <div className="flex flex-col gap-2">
        {pairs.map((pair, i) => (
          <div key={i} className="flex gap-2 items-center">
            <input
              className="flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder={keyPlaceholder}
              value={pair.key}
              onChange={(e) => update(i, 'key', e.target.value)}
            />
            <input
              className="flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder={valuePlaceholder}
              value={pair.value}
              onChange={(e) => update(i, 'value', e.target.value)}
            />
            <button
              type="button"
              onClick={() => remove(i)}
              className="text-gray-400 hover:text-red-500 shrink-0"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        {pairs.length === 0 && (
          <p className="text-xs text-gray-400 italic">Aucune entrée</p>
        )}
      </div>
    </div>
  )
}
