import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft } from 'lucide-react'
import { pipelinesApi } from '@/lib/api/pipelines'
import { PipelineWizard } from './PipelineWizard'

export function PipelineEditPage() {
  const { id } = useParams<{ id: string }>()

  const { data: pipeline, isLoading } = useQuery({
    queryKey: ['pipeline', id],
    queryFn: () => pipelinesApi.get(id!),
    enabled: !!id,
  })

  if (isLoading) {
    return <div className="text-center py-16 text-gray-400">Chargement…</div>
  }

  if (!pipeline) {
    return (
      <div className="text-center py-16 space-y-3">
        <p className="text-red-500">Pipeline introuvable</p>
        <Link to="/dashboard/pipelines" className="flex items-center justify-center gap-1 text-sm text-gray-500 hover:text-gray-700">
          <ChevronLeft className="h-4 w-4" /> Retour aux pipelines
        </Link>
      </div>
    )
  }

  return <PipelineWizard pipeline={pipeline} />
}
