import apiClient from './client'

export interface SnippetResponse {
  lang: string
  connector_id: string
  connector_name: string
  snippet: string
}

export const snippetsApi = {
  getSnippet: (connectorId: string, lang: string, apiKeyId?: string): Promise<SnippetResponse> => {
    const params = new URLSearchParams({ lang })
    if (apiKeyId) params.set('api_key_id', apiKeyId)
    return apiClient
      .get<SnippetResponse>(`/api/v1/connectors/${connectorId}/snippet?${params}`)
      .then((r) => r.data)
  },
}
