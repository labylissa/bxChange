import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { GitMerge, Plus, Trash2, Eye, Pencil, HelpCircle } from 'lucide-react'
import { pipelinesApi, type PipelineRead } from '@/lib/api/pipelines'

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
      {active ? 'Actif' : 'Inactif'}
    </span>
  )
}

function MergeBadge({ strategy }: { strategy: string }) {
  const colors: Record<string, string> = {
    merge: 'bg-blue-50 text-blue-700',
    first: 'bg-purple-50 text-purple-700',
    last: 'bg-indigo-50 text-indigo-700',
    custom: 'bg-orange-50 text-orange-700',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colors[strategy] ?? 'bg-gray-100 text-gray-600'}`}>
      {strategy}
    </span>
  )
}

export function PipelinesPage() {
  const qc = useQueryClient()
  const { data: pipelines = [], isLoading } = useQuery({
    queryKey: ['pipelines'],
    queryFn: pipelinesApi.list,
  })

  const handleDelete = async (p: PipelineRead) => {
    if (!confirm(`Supprimer le pipeline "${p.name}" ?`)) return
    await pipelinesApi.delete(p.id)
    qc.invalidateQueries({ queryKey: ['pipelines'] })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Pipelines</h1>
          <p className="text-sm text-gray-500 mt-1">Enchaînez plusieurs connecteurs en un seul appel API</p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/dashboard/pipelines/docs"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 text-gray-600 text-sm font-medium hover:bg-gray-50 transition-colors"
            title="Documentation Pipeline"
          >
            <HelpCircle className="h-4 w-4" />
            Guide
          </Link>
          <Link
            to="/dashboard/pipelines/new"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Nouveau pipeline
          </Link>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-gray-400">Chargement…</div>
      ) : pipelines.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <GitMerge className="h-10 w-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 font-medium">Aucun pipeline</p>
          <p className="text-gray-400 text-sm mt-1">Créez votre premier pipeline pour enchaîner des connecteurs</p>
          <Link to="/dashboard/pipelines/new" className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700">
            <Plus className="h-4 w-4" /> Nouveau pipeline
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Nom</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Steps</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Stratégie fusion</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Statut</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Exécutions</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {pipelines.map((p) => (
                <tr key={p.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <Link to={`/dashboard/pipelines/${p.id}`} className="font-medium text-gray-900 hover:text-brand-600">
                      {p.name}
                    </Link>
                    {p.description && <p className="text-xs text-gray-400 truncate max-w-xs">{p.description}</p>}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1 text-gray-700">
                      <GitMerge className="h-3.5 w-3.5 text-gray-400" />
                      {p.steps.length} step{p.steps.length > 1 ? 's' : ''}
                    </span>
                  </td>
                  <td className="px-4 py-3"><MergeBadge strategy={p.merge_strategy} /></td>
                  <td className="px-4 py-3"><StatusBadge active={p.is_active} /></td>
                  <td className="px-4 py-3 text-gray-600">{p.executions_count}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 justify-end">
                      <Link
                        to={`/dashboard/pipelines/${p.id}`}
                        className="p-1.5 text-gray-400 hover:text-brand-600 hover:bg-brand-50 rounded"
                        title="Voir"
                      >
                        <Eye className="h-4 w-4" />
                      </Link>
                      <Link
                        to={`/dashboard/pipelines/${p.id}/edit`}
                        className="p-1.5 text-gray-400 hover:text-brand-600 hover:bg-brand-50 rounded"
                        title="Éditer"
                      >
                        <Pencil className="h-4 w-4" />
                      </Link>
                      <button
                        onClick={() => handleDelete(p)}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                        title="Supprimer"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
