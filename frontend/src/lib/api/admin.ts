import apiClient from './client'

export interface TenantStats {
  id: string
  name: string
  slug: string
  created_at: string
  plan: string | null
  subscription_status: string | null
  connector_limit: number | null
  users_limit: number | null
  connector_count: number
  user_count: number
}

export interface TenantCreate {
  company_name: string
  admin_email: string
  admin_name: string
  admin_password: string
  connector_limit: number
  users_limit: number
}

export interface UserInTenant {
  id: string
  email: string
  full_name: string | null
  role: string
  is_active: boolean
  created_at: string
}

export interface ConnectorInTenant {
  id: string
  name: string
  type: string
  status: string
  created_at: string
}

export interface TenantDetail extends TenantStats {
  users: UserInTenant[]
  connectors: ConnectorInTenant[]
}

export interface AdminUserRead {
  id: string
  email: string
  full_name: string | null
  role: string
  is_active: boolean
  tenant_id: string | null
  tenant_name: string | null
  created_at: string
}

export interface QuotaRead {
  connector_count: number
  connector_limit: number | null
  user_count: number
  users_limit: number | null
}

export const adminApi = {
  getTenants: () =>
    apiClient.get<TenantStats[]>('/api/v1/admin/tenants').then((r) => r.data),

  createTenant: (data: TenantCreate) =>
    apiClient.post<TenantStats>('/api/v1/admin/tenants', data).then((r) => r.data),

  getTenant: (id: string) =>
    apiClient.get<TenantDetail>(`/api/v1/admin/tenants/${id}`).then((r) => r.data),

  updateQuota: (id: string, connector_limit: number, users_limit: number) =>
    apiClient
      .patch(`/api/v1/admin/tenants/${id}/quota`, { connector_limit, users_limit })
      .then((r) => r.data),

  deactivateTenant: (id: string) =>
    apiClient.delete(`/api/v1/admin/tenants/${id}`),

  reactivateTenant: (id: string) =>
    apiClient.patch(`/api/v1/admin/tenants/${id}/reactivate`).then((r) => r.data),

  changePlan: (id: string, plan: string, connector_limit?: number, users_limit?: number) =>
    apiClient
      .patch(`/api/v1/admin/tenants/${id}/plan`, { plan, connector_limit, users_limit })
      .then((r) => r.data),

  getUsers: () =>
    apiClient.get<AdminUserRead[]>('/api/v1/admin/users').then((r) => r.data),

  updateRole: (id: string, role: string) =>
    apiClient.patch(`/api/v1/admin/users/${id}/role`, { role }).then((r) => r.data),

  toggleActivate: (id: string, is_active: boolean) =>
    apiClient.patch(`/api/v1/admin/users/${id}/activate`, { is_active }).then((r) => r.data),

  impersonate: (userId: string) =>
    apiClient
      .post<{ access_token: string; user_id: string; email: string; expires_in: number }>(
        `/api/v1/admin/impersonate/${userId}`
      )
      .then((r) => r.data),
}

export const quotaApi = {
  getQuota: () =>
    apiClient.get<QuotaRead>('/api/v1/auth/quota').then((r) => r.data),
}
