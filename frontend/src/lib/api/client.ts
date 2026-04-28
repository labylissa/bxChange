import axios from 'axios'
import { useAuthStore } from '@/stores/authStore'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let isRefreshing = false
let failedQueue: Array<{ resolve: (value: unknown) => void; reject: (reason?: unknown) => void }> = []

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error)
    else resolve(token)
  })
  failedQueue = []
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error)
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject })
      }).then((token) => {
        originalRequest.headers.Authorization = `Bearer ${token}`
        return apiClient(originalRequest)
      })
    }

    originalRequest._retry = true
    isRefreshing = true

    const { refreshToken, refreshTokens, logout } = useAuthStore.getState()

    if (!refreshToken) {
      logout()
      window.location.href = '/login'
      return Promise.reject(error)
    }

    try {
      const { data } = await axios.post(`${import.meta.env.VITE_API_URL}/api/v1/auth/refresh`, {
        refresh_token: refreshToken,
      })
      refreshTokens(data.access_token, data.refresh_token)
      processQueue(null, data.access_token)
      originalRequest.headers.Authorization = `Bearer ${data.access_token}`
      return apiClient(originalRequest)
    } catch (err) {
      processQueue(err, null)
      logout()
      window.location.href = '/login'
      return Promise.reject(err)
    } finally {
      isRefreshing = false
    }
  }
)

export default apiClient
