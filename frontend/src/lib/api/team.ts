import apiClient from './client'

export interface TeamMember {
  id: string
  email: string
  full_name: string | null
  role: string
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export interface TeamInvite {
  email: string
  full_name: string
  password: string
  role: 'admin' | 'developer' | 'viewer'
}

export interface TeamMemberUpdate {
  full_name?: string
  role?: string
}

export const teamApi = {
  getMembers: () =>
    apiClient.get<TeamMember[]>('/api/v1/team/members').then((r) => r.data),

  invite: (data: TeamInvite) =>
    apiClient.post<TeamMember>('/api/v1/team/invite', data).then((r) => r.data),

  updateRole: (id: string, role: string) =>
    apiClient.patch<TeamMember>(`/api/v1/team/members/${id}/role`, { role }).then((r) => r.data),

  update: (id: string, data: TeamMemberUpdate) =>
    apiClient.put<TeamMember>(`/api/v1/team/members/${id}`, data).then((r) => r.data),

  deactivate: (id: string) =>
    apiClient.patch<TeamMember>(`/api/v1/team/members/${id}/deactivate`).then((r) => r.data),

  reactivate: (id: string) =>
    apiClient.patch<TeamMember>(`/api/v1/team/members/${id}/reactivate`).then((r) => r.data),

  resetPassword: (id: string) =>
    apiClient.post<{ temp_password: string }>(`/api/v1/team/members/${id}/reset-password`).then((r) => r.data),
}
