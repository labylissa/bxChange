import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { LoginPage } from '@/features/auth/LoginPage'
import { RegisterPage } from '@/features/auth/RegisterPage'
import { ProtectedRoute } from '@/features/auth/ProtectedRoute'
import { RoleGuard } from '@/features/auth/RoleGuard'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { ConnectorsPage } from '@/features/connectors/ConnectorsPage'
import { ConnectorDetailPage } from '@/features/connectors/ConnectorDetailPage'
import { LogsPage } from '@/features/logs/LogsPage'
import { APIKeysPage } from '@/features/api-keys/APIKeysPage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { TeamPage } from '@/features/team/TeamPage'
import { APIDocsPage } from '@/features/docs/APIDocsPage'
import { AdminPage } from '@/features/admin/AdminPage'
import { TenantsPage } from '@/features/admin/TenantsPage'
import { TenantDetailPage } from '@/features/admin/TenantDetailPage'
import { LicensesPage } from '@/features/admin/LicensesPage'
import { BillingPage } from '@/features/billing/BillingPage'
import { PipelinesPage } from '@/features/pipelines/PipelinesPage'
import { PipelineWizard } from '@/features/pipelines/PipelineWizard'
import { PipelineDetailPage } from '@/features/pipelines/PipelineDetailPage'
import { SSOConfigPage } from '@/features/sso/SSOConfigPage'
import { ScheduledJobsPage } from '@/features/scheduled-jobs/ScheduledJobsPage'
import { WebhooksPage } from '@/features/webhooks/WebhooksPage'

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
            {/* Dashboard (all authenticated users) */}
            <Route element={<DashboardLayout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/dashboard/connectors" element={<ConnectorsPage />} />
              <Route path="/dashboard/connectors/:id" element={<ConnectorDetailPage />} />
              <Route path="/dashboard/logs" element={<LogsPage />} />
              <Route path="/dashboard/api-keys" element={<APIKeysPage />} />
              <Route path="/dashboard/api-docs" element={<APIDocsPage />} />
              <Route path="/dashboard/scheduled-jobs" element={<ScheduledJobsPage />} />
              <Route path="/dashboard/webhooks" element={<WebhooksPage />} />
              <Route path="/dashboard/billing" element={<BillingPage />} />
              <Route path="/dashboard/pipelines" element={<PipelinesPage />} />
              <Route path="/dashboard/pipelines/new" element={<PipelineWizard />} />
              <Route path="/dashboard/pipelines/:id" element={<PipelineDetailPage />} />
              <Route path="/dashboard/settings" element={<SettingsPage />} />

              {/* Admin only: team management + SSO */}
              <Route element={<RoleGuard requiredRole="admin" />}>
                <Route path="/dashboard/team" element={<TeamPage />} />
                <Route path="/dashboard/sso" element={<SSOConfigPage />} />
              </Route>
            </Route>

            {/* Super admin only: admin panel */}
            <Route element={<RoleGuard requiredRole="super_admin" />}>
              <Route element={<DashboardLayout />}>
                <Route path="/admin" element={<AdminPage />} />
                <Route path="/admin/tenants" element={<TenantsPage />} />
                <Route path="/admin/tenants/:id" element={<TenantDetailPage />} />
                <Route path="/admin/licenses" element={<LicensesPage />} />
              </Route>
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
