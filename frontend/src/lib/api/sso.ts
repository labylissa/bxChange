import apiClient from './client'

export type IdpType = 'saml' | 'oidc'

export interface SSOConfig {
  id: string
  tenant_id: string
  idp_type: IdpType
  entity_id: string
  sso_url: string
  attr_mapping: Record<string, unknown> | null
  is_active: boolean
  created_at: string
}

export interface SSOConfigCreate {
  idp_type: IdpType
  entity_id: string
  sso_url: string
  certificate?: string
  attr_mapping?: Record<string, unknown>
  domains?: string[]
}

export interface SSOConfigUpdate {
  entity_id?: string
  sso_url?: string
  certificate?: string
  attr_mapping?: Record<string, unknown>
  is_active?: boolean
  domains?: string[]
}

export interface ScimToken {
  id: string
  tenant_id: string
  name: string
  expires_at: string | null
  is_active: boolean
  created_at: string
}

export interface ScimTokenCreated extends ScimToken {
  raw_token: string
}

export interface DomainHint {
  domain: string
  sso_config_id: string
}

export const ssoApi = {
  getConfig: () =>
    apiClient.get<SSOConfig>('/api/v1/sso/config').then((r) => r.data),

  createConfig: (data: SSOConfigCreate) =>
    apiClient.post<SSOConfig>('/api/v1/sso/config', data).then((r) => r.data),

  updateConfig: (data: SSOConfigUpdate) =>
    apiClient.put<SSOConfig>('/api/v1/sso/config', data).then((r) => r.data),

  deleteConfig: () =>
    apiClient.delete('/api/v1/sso/config'),

  getDomainHint: (domain: string) =>
    apiClient.get<DomainHint>(`/api/v1/sso/domain-hint/${domain}`).then((r) => r.data),

  listScimTokens: () =>
    apiClient.get<ScimToken[]>('/api/v1/sso/scim-tokens').then((r) => r.data),

  createScimToken: (data: { name: string; expires_at?: string }) =>
    apiClient.post<ScimTokenCreated>('/api/v1/sso/scim-tokens', data).then((r) => r.data),

  revokeScimToken: (id: string) =>
    apiClient.delete(`/api/v1/sso/scim-tokens/${id}`),
}
