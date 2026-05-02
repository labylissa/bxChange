import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { GitMerge, Plus, Trash2, Eye, Pencil, HelpCircle, Search } from 'lucide-react'
import { pipelinesApi, type PipelineRead } from '@/lib/api/pipelines'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { useToast } from '@/stores/toastStore'
import { Spinner } from '@/components/ui/Spinner'

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
  const toast = useToast()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [deleteTarget, setDeleteTarget] = useState<PipelineRead | null>(null)

  const { data: pipelines = [], isLoading } = useQuery({
    queryKey: ['pipelines'],
    queryFn: pipelinesApi.list,
  })

  const del = useMutation({
    mutationFn: (id: string) => pipelinesApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pipelines'] })
      toast.success('Pipeline supprimé')
      setDeleteTarget(null)
    },
    onError: () => toast.error('Erreur lors de la suppression'),
  })

  const filtered = pipelines.filter((p) => {
    const q = search.toLowerCase()
    if (q && !p.name.toLowerCase().includes(q) && !(p.description ?? '').toLowerCase().includes(q)) return false
    if (statusFilter === 'active' && !p.is_active) return false
    if (statusFilter === 'inactive' && p.is_active) return false
    return true
  })

  if (isLoading) return <div className="flex justify-center py-12"><Spinner size="lg" /></div>

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

      {pipelines.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <div className="p-4 bg-gray-100 rounded-full w-fit mx-auto mb-3">
            <GitMerge className="h-8 w-8 text-gray-400" />
          </div>
          <p className="text-gray-700 font-semibold">Aucun pipeline</p>
          <p className="text-gray-500 text-sm mt-1">Créez votre premier pipeline pour enchaîner des connecteurs</p>
          <Link to="/dashboard/pipelines/new" className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700">
            <Plus className="h-4 w-4" /> Nouveau pipeline
          </Link>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Rechercher un pipeline…"
                className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="pl-3 pr-8 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="all">Tous les statuts</option>
              <option value="active">Actifs</option>
              <option value="inactive">Inactifs</option>
            </select>
            {(search || statusFilter !== 'all') && (
              <button onClick={() => { setSearch(''); setStatusFilter('all') }} className="text-xs text-brand-600 hover:underline">
                Réinitialiser
              </button>
            )}
          </div>

          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['Nom', 'Steps', 'Stratégie fusion', 'Statut', 'Exécutions', ''].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filtered.map((p) => (
                  <tr key={p.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3">
                      <Link to={`/dashboard/pipelines/${p.id}`} className="font-medium text-gray-900 hover:text-brand-600">
                        {p.name}
                      </Link>
                      {p.description && <p className="text-xs text-gray-400 truncate max-w-xs mt-0.5">{p.description}</p>}
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
                        <Link to={`/dashboard/pipelines/${p.id}`} className="p-1.5 text-gray-400 hover:text-brand-600 hover:bg-brand-50 rounded" title="Voir">
                          <Eye className="h-4 w-4" />
                        </Link>
                        <Link to={`/dashboard/pipelines/${p.id}/edit`} className="p-1.5 text-gray-400 hover:text-brand-600 hover:bg-brand-50 rounded" title="Éditer">
                          <Pencil className="h-4 w-4" />
                        </Link>
                        <button onClick={() => setDeleteTarget(p)} className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded" title="Supprimer">
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filtered.length === 0 && (
              <div className="text-center py-10 text-gray-500 text-sm">
                Aucun pipeline ne correspond à votre recherche.
              </div>
            )}
          </div>
        </>
      )}

      {deleteTarget && (
        <ConfirmModal
          title="Supprimer le pipeline"
          message={`Supprimer "${deleteTarget.name}" ? Cette action est irréversible.`}
          confirmLabel="Supprimer"
          danger
          loading={del.isPending}
          onConfirm={() => del.mutate(deleteTarget.id)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  )
}
