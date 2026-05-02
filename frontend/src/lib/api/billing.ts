import apiClient from './client'

export type LicenseStatus = 'trial' | 'active' | 'expired' | 'suspended'

export interface BillingUsage {
  license_status: LicenseStatus
  executions_used: number
  executions_limit: number
  executions_pct: number
  connectors_used: number
  connectors_limit: number
  contract_end: string | null
  days_remaining: number | null
  trial_ends_at: string | null
}

export interface LicenseRead {
  id: string
  tenant_id: string
  license_key: string
  status: LicenseStatus
  executions_limit: number
  connectors_limit: number
  contract_start: string
  contract_end: string
  annual_price_cents: number
  notes: string | null
  created_by: string
  created_at: string
  activated_at: string | null
  suspended_at: string | null
  suspension_reason: string | null
}

export interface LicenseCreate {
  tenant_id: string
  executions_limit: number
  connectors_limit: number
  contract_start: string
  contract_end: string
  annual_price_cents: number
  notes?: string
}

export interface LicenseUpdate {
  executions_limit?: number
  connectors_limit?: number
  contract_start?: string
  contract_end?: string
  annual_price_cents?: number
  notes?: string
}

export interface InvoiceItem {
  invoice_id: string
  date: string
  description: string
  amount_cents: number
  currency: string
  status: string
  invoice_url: string | null
  pdf_url: string | null
}

export interface TenantUsageAdmin {
  tenant_id: string
  tenant_name: string
  license_status: LicenseStatus
  executions_used: number
  executions_limit: number
  executions_pct: number
  connectors_count: number
  connectors_limit: number
  contract_start: string | null
  contract_end: string | null
  days_remaining: number | null
  trial_ends_at: string | null
  stripe_customer_id: string | null
  annual_price_cents: number
}

export const billingApi = {
  getUsage: () =>
    apiClient.get<BillingUsage>('/api/v1/billing/usage').then((r) => r.data),

  getLicense: () =>
    apiClient.get<LicenseRead | null>('/api/v1/billing/license').then((r) => r.data),

  getInvoices: () =>
    apiClient.get<InvoiceItem[]>('/api/v1/billing/invoices').then((r) => r.data),
}

export const adminLicensesApi = {
  listLicenses: () =>
    apiClient.get<LicenseRead[]>('/api/v1/admin/licenses').then((r) => r.data),

  createLicense: (data: LicenseCreate) =>
    apiClient.post<LicenseRead>('/api/v1/admin/licenses', data).then((r) => r.data),

  getLicense: (id: string) =>
    apiClient.get<LicenseRead>(`/api/v1/admin/licenses/${id}`).then((r) => r.data),

  updateLicense: (id: string, data: LicenseUpdate) =>
    apiClient.put<LicenseRead>(`/api/v1/admin/licenses/${id}`, data).then((r) => r.data),

  activateLicense: (id: string) =>
    apiClient.post<LicenseRead>(`/api/v1/admin/licenses/${id}/activate`).then((r) => r.data),

  suspendLicense: (id: string, reason: string) =>
    apiClient
      .post<LicenseRead>(`/api/v1/admin/licenses/${id}/suspend`, { reason })
      .then((r) => r.data),

  renewLicense: (id: string, new_annual_price_cents?: number) =>
    apiClient
      .post<LicenseRead>(`/api/v1/admin/licenses/${id}/renew`, { new_annual_price_cents })
      .then((r) => r.data),

  getTenantUsage: (tenantId: string) =>
    apiClient
      .get<TenantUsageAdmin>(`/api/v1/admin/tenants/${tenantId}/usage`)
      .then((r) => r.data),

  createInvoice: (data: {
    tenant_id: string
    description: string
    amount_cents: number
    due_date: string
  }) =>
    apiClient
      .post<{ invoice_id: string; invoice_url: string | null; pdf_url: string | null }>(
        '/api/v1/admin/invoices',
        data
      )
      .then((r) => r.data),
}
