import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { LoginPage } from '@/features/auth/LoginPage'
import { RegisterPage } from '@/features/auth/RegisterPage'
import { ProtectedRoute } from '@/features/auth/ProtectedRoute'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { ConnectorsPage } from '@/features/connectors/ConnectorsPage'
import { LogsPage } from '@/features/logs/LogsPage'
import { APIKeysPage } from '@/features/api-keys/APIKeysPage'
import { SettingsPage } from '@/features/settings/SettingsPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<DashboardLayout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/dashboard/connectors" element={<ConnectorsPage />} />
              <Route path="/dashboard/logs" element={<LogsPage />} />
              <Route path="/dashboard/api-keys" element={<APIKeysPage />} />
              <Route path="/dashboard/settings" element={<SettingsPage />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
