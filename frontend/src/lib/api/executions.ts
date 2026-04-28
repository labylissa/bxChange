import apiClient from './client'

export interface Execution {
  id: string
  connector_id: string
  status: string
  duration_ms: number | null
  request_payload: Record<string, unknown> | null
  response_payload: Record<string, unknown> | null
  error_message: string | null
  http_status: number | null
  triggered_by: string
  created_at: string
}

export interface Metrics {
  total_calls: number
  success_count: number
  error_count: number
  success_rate: number
  avg_duration_ms: number
  p95_duration_ms: number
  calls_by_hour: Array<{ hour: string; count: number; errors: number }>
  calls_by_connector: Array<{ connector_id: string; name: string; count: number; error_rate: number }>
  calls_by_status: { success: number; error: number; timeout: number }
}

export interface RecentExecution {
  id: string
  connector_name: string
  status: string
  duration_ms: number | null
  http_status: number | null
  created_at: string
}

export const executionsApi = {
  getExecutions: (params?: { connector_id?: string; status?: string; page?: number }) =>
    apiClient.get<Execution[]>('/api/v1/executions', { params }).then((r) => r.data),

  getExecution: (id: string) =>
    apiClient.get<Execution>(`/api/v1/executions/${id}`).then((r) => r.data),
}

export interface Alert {
  type: string
  connector_id: string
  connector_name: string
  value: number
  threshold: number
  since: string | null
}

export const logsApi = {
  getMetrics: (period = '24h') =>
    apiClient.get<Metrics>('/api/v1/logs/metrics', { params: { period } }).then((r) => r.data),

  getRecent: () =>
    apiClient.get<RecentExecution[]>('/api/v1/logs/recent').then((r) => r.data),

  getAlerts: () =>
    apiClient.get<Alert[]>('/api/v1/logs/alerts').then((r) => r.data),
}
