import apiClient from './client'

export interface ApiKey {
  id: string
  name: string
  permissions: Record<string, unknown> | null
  rate_limit: number | null
  expires_at: string | null
  is_active: boolean
  created_at: string
}

export interface ApiKeyCreate {
  name: string
  rate_limit?: number
  expires_at?: string
  permissions?: Record<string, unknown>
}

export interface ApiKeyCreated extends ApiKey {
  raw_key: string
}

export const apiKeysApi = {
  getApiKeys: () =>
    apiClient.get<ApiKey[]>('/api/v1/api-keys').then((r) => r.data),

  createApiKey: (data: ApiKeyCreate) =>
    apiClient.post<ApiKeyCreated>('/api/v1/api-keys', data).then((r) => r.data),

  revokeApiKey: (id: string) =>
    apiClient.delete(`/api/v1/api-keys/${id}`),
}
