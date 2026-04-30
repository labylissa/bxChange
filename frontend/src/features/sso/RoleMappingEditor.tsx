import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

type RoleOption = 'admin' | 'developer' | 'viewer'

interface RoleMapping {
  group: string
  role: RoleOption
}

interface Props {
  value: Record<string, string>
  onChange: (mapping: Record<string, string>) => void
}

export function RoleMappingEditor({ value, onChange }: Props) {
  const [rows, setRows] = useState<RoleMapping[]>(() =>
    Object.entries(value).map(([group, role]) => ({ group, role: role as RoleOption }))
  )

  function addRow() {
    setRows((prev) => [...prev, { group: '', role: 'viewer' }])
  }

  function removeRow(idx: number) {
    const updated = rows.filter((_, i) => i !== idx)
    setRows(updated)
    onChange(Object.fromEntries(updated.map((r) => [r.group, r.role])))
  }

  function updateRow(idx: number, field: keyof RoleMapping, val: string) {
    const updated = rows.map((r, i) =>
      i === idx ? { ...r, [field]: val } : r
    )
    setRows(updated)
    onChange(Object.fromEntries(updated.filter((r) => r.group).map((r) => [r.group, r.role])))
  }

  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm font-medium text-gray-700">
        Mapping groupe → rôle
      </label>

      {rows.length === 0 && (
        <p className="text-xs text-gray-400 italic">
          Aucun mapping — tous les utilisateurs SSO reçoivent le rôle <strong>viewer</strong>.
        </p>
      )}

      {rows.map((row, idx) => (
        <div key={idx} className="flex items-center gap-2">
          <Input
            placeholder="Nom du groupe IdP"
            value={row.group}
            onChange={(e) => updateRow(idx, 'group', e.target.value)}
            className="flex-1"
          />
          <select
            value={row.role}
            onChange={(e) => updateRow(idx, 'role', e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="admin">admin</option>
            <option value="developer">developer</option>
            <option value="viewer">viewer</option>
          </select>
          <button
            type="button"
            onClick={() => removeRow(idx)}
            className="text-gray-400 hover:text-red-500 transition-colors p-1"
          >
            <Trash2 size={16} />
          </button>
        </div>
      ))}

      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={addRow}
        className="self-start flex items-center gap-1 text-brand-600"
      >
        <Plus size={14} />
        Ajouter un mapping
      </Button>
    </div>
  )
}
