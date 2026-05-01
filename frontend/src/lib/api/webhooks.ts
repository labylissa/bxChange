import apiClient from './client'

export type WebhookEvent = 'execution.success' | 'execution.failure' | 'execution.all'

export interface WebhookEndpoint {
  id: string
  connector_id: string
  tenant_id: string
  name: string
  url: string
  events: WebhookEvent[]
  is_active: boolean
  last_triggered_at: string | null
  last_status_code: number | null
  created_at: string
}

export interface WebhookCreate {
  connector_id: string
  name: string
  url: string
  secret: string
  events: WebhookEvent[]
}

export interface WebhookUpdate {
  name?: string
  url?: string
  secret?: string
  events?: WebhookEvent[]
  is_active?: boolean
}

export interface WebhookTestResult {
  status_code: number | null
  ok: boolean
  error?: string
}

export const webhooksApi = {
  list: (connectorId?: string) =>
    apiClient
      .get<WebhookEndpoint[]>('/api/v1/webhooks', {
        params: connectorId ? { connector_id: connectorId } : {},
      })
      .then((r) => r.data),

  get: (id: string) =>
    apiClient.get<WebhookEndpoint>(`/api/v1/webhooks/${id}`).then((r) => r.data),

  create: (data: WebhookCreate) =>
    apiClient.post<WebhookEndpoint>('/api/v1/webhooks', data).then((r) => r.data),

  update: (id: string, data: WebhookUpdate) =>
    apiClient.put<WebhookEndpoint>(`/api/v1/webhooks/${id}`, data).then((r) => r.data),

  delete: (id: string) => apiClient.delete(`/api/v1/webhooks/${id}`),

  toggle: (id: string) =>
    apiClient.post<WebhookEndpoint>(`/api/v1/webhooks/${id}/toggle`).then((r) => r.data),

  test: (id: string) =>
    apiClient.post<WebhookTestResult>(`/api/v1/webhooks/${id}/test`).then((r) => r.data),
}
