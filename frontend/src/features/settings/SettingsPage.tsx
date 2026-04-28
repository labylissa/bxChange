import { Card } from '@/components/ui/Card'

export function SettingsPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold text-gray-900">Paramètres</h1>
      <Card>
        <p className="text-sm text-gray-500">Les paramètres seront disponibles dans une prochaine version.</p>
      </Card>
    </div>
  )
}
