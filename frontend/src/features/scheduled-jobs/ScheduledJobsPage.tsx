import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Play, Plus, Trash2, Search, ChevronDown } from 'lucide-react'
import { scheduledJobsApi } from '@/lib/api/scheduledJobs'
import type { ScheduledJob } from '@/lib/api/scheduledJobs'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { useToast } from '@/stores/toastStore'
import { ScheduledJobForm } from './ScheduledJobForm'

function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function scheduleLabel(job: ScheduledJob): string {
  if (job.schedule_type === 'cron') return job.cron_expression ?? '—'
  const s = job.interval_seconds ?? 0
  if (s >= 86400 && s % 86400 === 0) return `Toutes les ${s / 86400}j`
  if (s >= 3600 && s % 3600 === 0) return `Toutes les ${s / 3600}h`
  return `Toutes les ${Math.floor(s / 60)} min`
}

interface RowProps { job: ScheduledJob; onEdit: (job: ScheduledJob) => void; onDelete: (job: ScheduledJob) => void }

function JobRow({ job, onEdit, onDelete }: RowProps) {
  const qc = useQueryClient()
  const toast = useToast()

  const toggle = useMutation({
    mutationFn: () => scheduledJobsApi.toggle(job.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduled-jobs'] }),
  })

  const runNow = useMutation({
    mutationFn: () => scheduledJobsApi.runNow(job.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['scheduled-jobs'] }); toast.success('Job lancé') },
    onError: () => toast.error('Erreur lors du lancement'),
  })

  return (
    <tr className="hover:bg-gray-50 transition-colors">
      <td className="px-4 py-3">
        <button onClick={() => onEdit(job)} className="text-sm font-medium text-gray-900 hover:text-brand-600 text-left">{job.name}</button>
      </td>
      <td className="px-4 py-3 text-sm text-gray-600">{job.connector_name ?? '—'}</td>
      <td className="px-4 py-3">
        <Badge variant={job.schedule_type === 'cron' ? 'blue' : 'gray'} className="text-xs">{job.schedule_type}</Badge>
      </td>
      <td className="px-4 py-3 text-xs text-gray-600 font-mono">{scheduleLabel(job)}</td>
      <td className="px-4 py-3">
        <button onClick={() => toggle.mutate()} disabled={toggle.isPending}
          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none ${job.is_active ? 'bg-brand-600' : 'bg-gray-200'}`}>
          <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${job.is_active ? 'translate-x-4' : 'translate-x-1'}`} />
        </button>
      </td>
      <td className="px-4 py-3 text-xs text-gray-500">{formatDateTime(job.last_run_at)}</td>
      <td className="px-4 py-3 text-xs text-gray-500">{formatDateTime(job.next_run_at)}</td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
          <button onClick={() => runNow.mutate()} disabled={runNow.isPending} title="Exécuter maintenant"
            className="p-1 rounded text-gray-400 hover:text-brand-600 hover:bg-brand-50 transition-colors">
            <Play className="h-3.5 w-3.5" />
          </button>
          <button onClick={() => onDelete(job)} title="Supprimer"
            className="p-1 rounded text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors">
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </td>
    </tr>
  )
}

interface Props { connectorId?: string }

export function ScheduledJobsPage({ connectorId }: Props) {
  const qc = useQueryClient()
  const toast = useToast()
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<ScheduledJob | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ScheduledJob | null>(null)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  const { data: jobs, isLoading } = useQuery({
    queryKey: ['scheduled-jobs', connectorId],
    queryFn: () => scheduledJobsApi.list(connectorId),
  })

  const del = useMutation({
    mutationFn: (id: string) => scheduledJobsApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['scheduled-jobs'] }); toast.success('Job supprimé'); setDeleteTarget(null) },
    onError: () => toast.error('Erreur lors de la suppression'),
  })

  const filtered = (jobs ?? []).filter((j) => {
    const q = search.toLowerCase()
    if (q && !j.name.toLowerCase().includes(q) && !(j.connector_name ?? '').toLowerCase().includes(q)) return false
    if (typeFilter !== 'all' && j.schedule_type !== typeFilter) return false
    if (statusFilter === 'active' && !j.is_active) return false
    if (statusFilter === 'inactive' && j.is_active) return false
    return true
  })

  function openEdit(job: ScheduledJob) { setEditing(job); setShowForm(true) }
  function closeForm() { setShowForm(false); setEditing(null) }

  if (isLoading) return <div className="flex justify-center py-8"><Spinner /></div>

  if (showForm) {
    return (
      <Card>
        <h3 className="text-sm font-semibold text-gray-900 mb-4">{editing ? 'Modifier le job planifié' : 'Nouveau job planifié'}</h3>
        <ScheduledJobForm connectorId={connectorId} existing={editing ?? undefined} onSuccess={closeForm} onCancel={closeForm} />
      </Card>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        {!connectorId && <h1 className="text-2xl font-bold text-gray-900">Jobs planifiés</h1>}
        <Button size="sm" className="flex items-center gap-1.5 ml-auto" onClick={() => setShowForm(true)}>
          <Plus className="h-3.5 w-3.5" /> Nouveau job planifié
        </Button>
      </div>

      {(jobs?.length ?? 0) > 0 && (
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input type="text" value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Rechercher un job…"
              className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div className="relative">
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}
              className="appearance-none pl-3 pr-8 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
              <option value="all">Tous les types</option>
              <option value="cron">Cron</option>
              <option value="interval">Intervalle</option>
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400 pointer-events-none" />
          </div>
          <div className="relative">
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
              className="appearance-none pl-3 pr-8 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
              <option value="all">Tous les statuts</option>
              <option value="active">Actifs</option>
              <option value="inactive">Inactifs</option>
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400 pointer-events-none" />
          </div>
        </div>
      )}

      {!jobs?.length ? (
        <Card>
          <div className="flex flex-col items-center py-12 gap-3 text-center">
            <div className="p-4 bg-gray-100 rounded-full"><Play className="h-7 w-7 text-gray-400" /></div>
            <p className="font-medium text-gray-700">Aucun job planifié</p>
            <p className="text-sm text-gray-500">Automatisez vos exécutions de connecteurs à intervalles réguliers.</p>
            <Button size="sm" onClick={() => setShowForm(true)} className="flex items-center gap-1.5">
              <Plus className="h-3.5 w-3.5" /> Créer le premier job
            </Button>
          </div>
        </Card>
      ) : (
        <Card padding="none">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="border-b border-gray-100 bg-gray-50">
                <tr>
                  {['Nom', 'Connecteur', 'Type', 'Planning', 'Actif', 'Dernière exéc.', 'Prochaine exéc.', ''].map((h) => (
                    <th key={h} className="px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filtered.map((job) => (
                  <JobRow key={job.id} job={job} onEdit={openEdit} onDelete={setDeleteTarget} />
                ))}
              </tbody>
            </table>
            {filtered.length === 0 && (
              <div className="text-center py-8 text-gray-500 text-sm">Aucun job ne correspond à votre recherche.</div>
            )}
          </div>
        </Card>
      )}

      {deleteTarget && (
        <ConfirmModal
          title="Supprimer le job planifié"
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
