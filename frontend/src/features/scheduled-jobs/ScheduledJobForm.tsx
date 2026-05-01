import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { connectorsApi } from '@/lib/api/connectors'
import { scheduledJobsApi } from '@/lib/api/scheduledJobs'
import type { ScheduledJob } from '@/lib/api/scheduledJobs'
import { Button } from '@/components/ui/Button'
import { KeyValueEditor } from '@/components/ui/KeyValueEditor'
import type { KVPair } from '@/components/ui/KeyValueEditor'

const schema = z
  .object({
    name: z.string().min(1, 'Nom requis'),
    schedule_type: z.enum(['cron', 'interval']),
    cron_expression: z.string().optional(),
    interval_value: z.coerce.number().int().min(1).optional(),
    interval_unit: z.enum(['minutes', 'hours', 'days']),
  })
  .refine(
    (d) => d.schedule_type !== 'cron' || (d.cron_expression && d.cron_expression.trim().length > 0),
    { message: 'Expression cron requise', path: ['cron_expression'] }
  )
  .refine((d) => d.schedule_type !== 'interval' || (d.interval_value && d.interval_value >= 1), {
    message: 'Intervalle requis (min 1)',
    path: ['interval_value'],
  })

function toSeconds(value: number, unit: 'minutes' | 'hours' | 'days'): number {
  if (unit === 'minutes') return value * 60
  if (unit === 'hours') return value * 3600
  return value * 86400
}

interface Props {
  connectorId?: string
  existing?: ScheduledJob
  onSuccess: () => void
  onCancel: () => void
}

export function ScheduledJobForm({ connectorId, existing, onSuccess, onCancel }: Props) {
  const qc = useQueryClient()

  const [name, setName] = useState(existing?.name ?? '')
  const [scheduleType, setScheduleType] = useState<'cron' | 'interval'>(
    existing?.schedule_type ?? 'interval'
  )
  const [cronExpr, setCronExpr] = useState(existing?.cron_expression ?? '')
  const [intervalValue, setIntervalValue] = useState(() => {
    if (!existing?.interval_seconds) return '1'
    const v = existing.interval_seconds
    if (v % 86400 === 0) return String(v / 86400)
    if (v % 3600 === 0) return String(v / 3600)
    return String(Math.floor(v / 60))
  })
  const [intervalUnit, setIntervalUnit] = useState<'minutes' | 'hours' | 'days'>(() => {
    if (!existing?.interval_seconds) return 'hours'
    const v = existing.interval_seconds
    if (v % 86400 === 0) return 'days'
    if (v % 3600 === 0) return 'hours'
    return 'minutes'
  })
  const [selectedConnectorId, setSelectedConnectorId] = useState(
    connectorId ?? existing?.connector_id ?? ''
  )
  const [inputParams, setInputParams] = useState<KVPair[]>(() =>
    Object.entries(existing?.input_params ?? {}).map(([key, value]) => ({
      key,
      value: String(value),
    }))
  )
  const [errors, setErrors] = useState<Record<string, string>>({})

  const { data: connectors } = useQuery({
    queryKey: ['connectors'],
    queryFn: connectorsApi.getConnectors,
    enabled: !connectorId,
  })

  const mutation = useMutation({
    mutationFn: () => {
      const result = schema.safeParse({
        name,
        schedule_type: scheduleType,
        cron_expression: cronExpr,
        interval_value: intervalValue,
        interval_unit: intervalUnit,
      })
      if (!result.success) {
        const errs: Record<string, string> = {}
        for (const issue of result.error.issues) {
          const key = issue.path[0]
          if (key !== undefined) errs[String(key)] = issue.message
        }
        setErrors(errs)
        throw new Error('Validation failed')
      }
      setErrors({})

      const params: Record<string, string> = {}
      inputParams.filter((p) => p.key.trim()).forEach((p) => {
        params[p.key] = p.value
      })

      const basePayload = {
        name: name.trim(),
        schedule_type: scheduleType,
        cron_expression: scheduleType === 'cron' ? cronExpr.trim() : undefined,
        interval_seconds:
          scheduleType === 'interval'
            ? toSeconds(Number(intervalValue), intervalUnit)
            : undefined,
        input_params: params,
      }

      if (existing) {
        return scheduledJobsApi.update(existing.id, basePayload)
      }
      return scheduledJobsApi.create({
        ...basePayload,
        connector_id: connectorId ?? selectedConnectorId,
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scheduled-jobs'] })
      onSuccess()
    },
  })

  const intervalSeconds =
    scheduleType === 'interval' ? toSeconds(Number(intervalValue) || 0, intervalUnit) : null
  const minOk = intervalSeconds === null || intervalSeconds >= 60

  return (
    <div className="flex flex-col gap-4">
      {/* Connector selector (hidden when connectorId is locked) */}
      {!connectorId && !existing && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Connecteur</label>
          <select
            className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            value={selectedConnectorId}
            onChange={(e) => setSelectedConnectorId(e.target.value)}
          >
            <option value="">— Sélectionner un connecteur —</option>
            {connectors?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.type.toUpperCase()})
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Name */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Nom</label>
        <input
          className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Ex: Sync toutes les heures"
        />
        {errors.name && <p className="text-xs text-red-600 mt-1">{errors.name}</p>}
      </div>

      {/* Schedule type toggle */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Type de planification</label>
        <div className="flex gap-2">
          {(['interval', 'cron'] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setScheduleType(t)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                scheduleType === t
                  ? 'bg-brand-600 text-white border-brand-600'
                  : 'bg-white text-gray-600 border-gray-300 hover:border-brand-400'
              }`}
            >
              {t === 'interval' ? 'Intervalle' : 'Cron'}
            </button>
          ))}
        </div>
      </div>

      {/* Interval fields */}
      {scheduleType === 'interval' && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Répéter toutes les</label>
          <div className="flex gap-2">
            <input
              type="number"
              min={1}
              className="w-24 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={intervalValue}
              onChange={(e) => setIntervalValue(e.target.value)}
            />
            <select
              className="flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={intervalUnit}
              onChange={(e) => setIntervalUnit(e.target.value as 'minutes' | 'hours' | 'days')}
            >
              <option value="minutes">minutes</option>
              <option value="hours">heures</option>
              <option value="days">jours</option>
            </select>
          </div>
          {!minOk && (
            <p className="text-xs text-red-600 mt-1">Minimum 60 secondes (1 minute)</p>
          )}
          {errors.interval_value && (
            <p className="text-xs text-red-600 mt-1">{errors.interval_value}</p>
          )}
        </div>
      )}

      {/* Cron fields */}
      {scheduleType === 'cron' && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Expression cron{' '}
            <span className="font-normal text-gray-400">(min heure j-mois mois j-semaine)</span>
          </label>
          <input
            className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
            placeholder="0 9 * * 1-5"
            value={cronExpr}
            onChange={(e) => setCronExpr(e.target.value)}
          />
          <p className="text-xs text-gray-400 mt-1">
            Exemples : <code>0 9 * * 1-5</code> (lun–ven à 9h) · <code>*/30 * * * *</code> (toutes les 30 min)
          </p>
          {errors.cron_expression && (
            <p className="text-xs text-red-600 mt-1">{errors.cron_expression}</p>
          )}
        </div>
      )}

      {/* Input params */}
      <KeyValueEditor
        label="Paramètres d'entrée"
        pairs={inputParams}
        onChange={setInputParams}
        keyPlaceholder="Paramètre"
        valuePlaceholder="Valeur"
        addLabel="Ajouter un paramètre"
      />

      {mutation.isError && !(mutation.error as Error).message.includes('Validation') && (
        <p className="text-sm text-red-600">
          {(mutation.error as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ?? 'Erreur lors de la sauvegarde'}
        </p>
      )}

      <div className="flex gap-2 pt-1">
        <Button onClick={() => mutation.mutate()} loading={mutation.isPending} disabled={!minOk}>
          {existing ? 'Enregistrer' : 'Créer le job'}
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          Annuler
        </Button>
      </div>
    </div>
  )
}
