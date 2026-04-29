import apiClient from './client'

export type ConnectorType = 'soap' | 'rest'
export type AuthType = 'none' | 'basic' | 'bearer' | 'apikey' | 'oauth2'
export type ConnectorStatus = 'active' | 'error' | 'disabled' | 'draft'

export interface Connector {
  id: string
  tenant_id: string
  name: string
  type: ConnectorType
  base_url: string | null
  wsdl_url: string | null
  auth_type: AuthType
  status: ConnectorStatus
  created_at: string
}

export interface ConnectorCreate {
  name: string
  type: ConnectorType
  base_url?: string
  wsdl_url?: string
  auth_type?: AuthType
  auth_config?: Record<string, unknown>
  headers?: Record<string, string>
  transform_config?: Record<string, unknown>
}

export interface ConnectorUpdate {
  name?: string
  base_url?: string
  wsdl_url?: string
  auth_type?: AuthType
  auth_config?: Record<string, unknown>
  headers?: Record<string, string>
  transform_config?: Record<string, unknown>
  status?: ConnectorStatus
}

export interface WSDLParseResult {
  operations: Record<string, Record<string, unknown>>
  count: number
}

export interface RestTestPayload {
  method: string
  path: string
  params?: Record<string, unknown>
  body?: Record<string, unknown>
}

export interface ExecutePayload {
  params?: Record<string, unknown>
  body?: Record<string, unknown>
  transform_override?: Record<string, unknown>
}

export interface ExecuteResult {
  execution_id: string
  status: string
  result: Record<string, unknown> | null
  duration_ms: number | null
  error_message: string | null
}

export interface PreviewTransformPayload {
  raw_xml: string
  transform_config?: Record<string, unknown>
}

export interface PreviewTransformResult {
  result: unknown
  steps: Record<string, unknown>
}

export const connectorsApi = {
  getConnectors: () =>
    apiClient.get<Connector[]>('/api/v1/connectors').then((r) => r.data),

  getConnector: (id: string) =>
    apiClient.get<Connector>(`/api/v1/connectors/${id}`).then((r) => r.data),

  createConnector: (data: ConnectorCreate) =>
    apiClient.post<Connector>('/api/v1/connectors', data).then((r) => r.data),

  updateConnector: (id: string, data: ConnectorUpdate) =>
    apiClient.put<Connector>(`/api/v1/connectors/${id}`, data).then((r) => r.data),

  deleteConnector: (id: string) =>
    apiClient.delete(`/api/v1/connectors/${id}`),

  testWsdl: (id: string) =>
    apiClient.post<WSDLParseResult>(`/api/v1/connectors/${id}/test-wsdl`).then((r) => r.data),

  testRest: (id: string, payload: RestTestPayload) =>
    apiClient.post<Record<string, unknown>>(`/api/v1/connectors/${id}/test-rest`, payload).then((r) => r.data),

  executeConnector: (id: string, payload: ExecutePayload) =>
    apiClient.post<ExecuteResult>(`/api/v1/connectors/${id}/execute`, payload).then((r) => r.data),

  previewTransform: (id: string, payload: PreviewTransformPayload) =>
    apiClient.post<PreviewTransformResult>(`/api/v1/connectors/${id}/preview-transform`, payload).then((r) => r.data),
}
