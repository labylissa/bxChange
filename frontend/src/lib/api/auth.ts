import apiClient from './client'

export interface UpdateProfilePayload {
  full_name: string
  email: string
}

export interface ChangePasswordPayload {
  current_password: string
  new_password: string
}

export const authApi = {
  updateProfile: (data: UpdateProfilePayload) =>
    apiClient.put('/api/v1/auth/me', data).then((r) => r.data),

  changePassword: (data: ChangePasswordPayload) =>
    apiClient.post('/api/v1/auth/change-password', data).then((r) => r.data),

  deleteAccount: () =>
    apiClient.delete('/api/v1/auth/me'),
}
