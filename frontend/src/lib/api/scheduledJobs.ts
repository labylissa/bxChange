import apiClient from './client'

export type ScheduleType = 'cron' | 'interval'

export interface ScheduledJob {
  id: string
  connector_id: string
  tenant_id: string
  name: string
  schedule_type: ScheduleType
  cron_expression: string | null
  interval_seconds: number | null
  input_params: Record<string, unknown>
  is_active: boolean
  last_run_at: string | null
  next_run_at: string | null
  created_at: string
  created_by: string | null
  connector_name: string | null
}

export interface ScheduledJobCreate {
  connector_id: string
  name: string
  schedule_type: ScheduleType
  cron_expression?: string
  interval_seconds?: number
  input_params?: Record<string, unknown>
}

export interface ScheduledJobUpdate {
  name?: string
  schedule_type?: ScheduleType
  cron_expression?: string
  interval_seconds?: number
  input_params?: Record<string, unknown>
  is_active?: boolean
}

export const scheduledJobsApi = {
  list: (connectorId?: string) =>
    apiClient
      .get<ScheduledJob[]>('/api/v1/scheduled-jobs', {
        params: connectorId ? { connector_id: connectorId } : {},
      })
      .then((r) => r.data),

  get: (id: string) =>
    apiClient.get<ScheduledJob>(`/api/v1/scheduled-jobs/${id}`).then((r) => r.data),

  create: (data: ScheduledJobCreate) =>
    apiClient.post<ScheduledJob>('/api/v1/scheduled-jobs', data).then((r) => r.data),

  update: (id: string, data: ScheduledJobUpdate) =>
    apiClient.put<ScheduledJob>(`/api/v1/scheduled-jobs/${id}`, data).then((r) => r.data),

  delete: (id: string) => apiClient.delete(`/api/v1/scheduled-jobs/${id}`),

  toggle: (id: string) =>
    apiClient.post<ScheduledJob>(`/api/v1/scheduled-jobs/${id}/toggle`).then((r) => r.data),

  runNow: (id: string) =>
    apiClient
      .post<{ dispatched: boolean; job_id: string }>(`/api/v1/scheduled-jobs/${id}/run-now`)
      .then((r) => r.data),
}
