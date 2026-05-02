import apiClient from './client'

export interface PipelineStepCreate {
  connector_id: string
  step_order: number
  name: string
  execution_mode: 'sequential' | 'parallel'
  params_template: Record<string, unknown>
  condition: string | null
  on_error: 'stop' | 'skip' | 'continue'
  timeout_seconds: number
}

export interface PipelineStepRead extends PipelineStepCreate {
  id: string
  connector_name: string
  connector_type: 'soap' | 'rest' | string
}

export interface PipelineRead {
  id: string
  name: string
  description: string | null
  is_active: boolean
  merge_strategy: 'merge' | 'first' | 'last' | 'custom'
  output_transform: Record<string, unknown> | null
  steps: PipelineStepRead[]
  created_at: string
  executions_count: number
}

export interface PipelineCreate {
  name: string
  description?: string
  merge_strategy: 'merge' | 'first' | 'last' | 'custom'
  output_transform?: Record<string, unknown> | null
  steps: PipelineStepCreate[]
}

export interface PipelineUpdate {
  name?: string
  description?: string
  is_active?: boolean
  merge_strategy?: string
  output_transform?: Record<string, unknown> | null
  steps?: PipelineStepCreate[]
}

export interface PipelineExecutionRead {
  id: string
  pipeline_id: string
  tenant_id: string
  triggered_by: string
  status: string
  input_params: Record<string, unknown>
  result: Record<string, unknown>
  steps_detail: Record<string, {
    status: string
    result: Record<string, unknown>
    error_message: string | null
    duration_ms: number
    connector_id: string
  }>
  duration_ms: number
  error_step: number | null
  error_message: string | null
  created_at: string
}

export interface PipelineExecuteResponse {
  execution_id: string
  status: string
  result: Record<string, unknown>
  steps: Record<string, unknown>
  duration_ms: number
  error_step: number | null
  error_message: string | null
}

export const pipelinesApi = {
  list: () =>
    apiClient.get<PipelineRead[]>('/api/v1/pipelines').then((r) => r.data),

  create: (data: PipelineCreate) =>
    apiClient.post<PipelineRead>('/api/v1/pipelines', data).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<PipelineRead>(`/api/v1/pipelines/${id}`).then((r) => r.data),

  update: (id: string, data: PipelineUpdate) =>
    apiClient.put<PipelineRead>(`/api/v1/pipelines/${id}`, data).then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/api/v1/pipelines/${id}`),

  execute: (id: string, params: Record<string, unknown>, apiKey: string) =>
    apiClient
      .post<PipelineExecuteResponse>(
        `/api/v1/pipelines/${id}/execute`,
        { params },
        { headers: { 'X-API-Key': apiKey } },
      )
      .then((r) => r.data),

  listExecutions: (id: string) =>
    apiClient
      .get<PipelineExecutionRead[]>(`/api/v1/pipelines/${id}/executions`)
      .then((r) => r.data),
}
