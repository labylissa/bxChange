import apiClient from './client'

// ── OAuth2 Clients ──────────────────────────────────────────────────────────

export type OAuth2Scope = 'execute:connectors' | 'execute:pipelines' | 'read:results'

export interface OAuth2Client {
  id: string
  tenant_id: string
  client_id: string
  client_secret_preview: string
  name: string
  scopes: OAuth2Scope[]
  is_active: boolean
  token_ttl_seconds: number
  allowed_ips: string[]
  last_used_at: string | null
  created_at: string
  created_by: string
}

export interface OAuth2ClientCreated extends OAuth2Client {
  client_secret: string
}

export interface OAuth2ClientCreate {
  name: string
  scopes: OAuth2Scope[]
  token_ttl_seconds: number
  allowed_ips: string[]
}

export interface OAuth2ClientUpdate {
  name?: string
  scopes?: OAuth2Scope[]
  token_ttl_seconds?: number
  allowed_ips?: string[]
  is_active?: boolean
}

// ── mTLS Certificates ───────────────────────────────────────────────────────

export interface MTLSCertificate {
  id: string
  tenant_id: string
  name: string
  fingerprint_sha256: string
  subject_dn: string
  issuer_dn: string
  valid_from: string
  valid_until: string
  is_active: boolean
  last_used_at: string | null
  created_at: string
  created_by: string
}

export interface MTLSCertificateCreate {
  name: string
  certificate_pem: string
}

// ── API ─────────────────────────────────────────────────────────────────────

export const oauth2ClientsApi = {
  list: () =>
    apiClient.get<OAuth2Client[]>('/api/v1/oauth2-clients').then((r) => r.data),

  create: (data: OAuth2ClientCreate) =>
    apiClient.post<OAuth2ClientCreated>('/api/v1/oauth2-clients', data).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<OAuth2Client>(`/api/v1/oauth2-clients/${id}`).then((r) => r.data),

  update: (id: string, data: OAuth2ClientUpdate) =>
    apiClient.put<OAuth2Client>(`/api/v1/oauth2-clients/${id}`, data).then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/api/v1/oauth2-clients/${id}`),

  rotate: (id: string) =>
    apiClient.post<OAuth2ClientCreated>(`/api/v1/oauth2-clients/${id}/rotate`).then((r) => r.data),
}

export const mtlsCertificatesApi = {
  list: () =>
    apiClient.get<MTLSCertificate[]>('/api/v1/mtls/certificates').then((r) => r.data),

  create: (data: MTLSCertificateCreate) =>
    apiClient.post<MTLSCertificate>('/api/v1/mtls/certificates', data).then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/api/v1/mtls/certificates/${id}`),
}
