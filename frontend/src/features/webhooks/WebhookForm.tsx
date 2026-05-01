import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { webhooksApi } from '@/lib/api/webhooks'
import type { WebhookEndpoint, WebhookEvent } from '@/lib/api/webhooks'
import { Button } from '@/components/ui/Button'

const schema = z.object({
  name: z.string().min(1, 'Nom requis'),
  url: z.string().startsWith('https://', 'URL must start with https://'),
  secret: z.string().min(16, 'Secret doit faire au moins 16 caractères'),
  events: z.array(z.string()).min(1, 'Au moins un événement requis'),
})

const EVENT_OPTIONS: { value: WebhookEvent; label: string }[] = [
  { value: 'execution.success', label: 'Succès' },
  { value: 'execution.failure', label: 'Échec' },
  { value: 'execution.all', label: 'Tous' },
]

function generateSecret(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*'
  return Array.from({ length: 32 }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
}

interface Props {
  connectorId: string
  webhook?: WebhookEndpoint
  onDone: () => void
  onCancel: () => void
}

export function WebhookForm({ connectorId, webhook, onDone, onCancel }: Props) {
  const qc = useQueryClient()
  const isEdit = !!webhook

  const [name, setName] = useState(webhook?.name ?? '')
  const [url, setUrl] = useState(webhook?.url ?? '')
  const [secret, setSecret] = useState('')
  const [events, setEvents] = useState<string[]>(webhook?.events ?? ['execution.success'])
  const [errors, setErrors] = useState<Record<string, string>>({})

  const save = useMutation({
    mutationFn: () => {
      const editSchema = schema.partial({ secret: true }).extend({
        secret: z.string().min(16).optional(),
      })
      const validResult = isEdit
        ? editSchema.safeParse({ name, url, events, secret: secret || undefined })
        : schema.safeParse({ name, url, events, secret })

      if (!validResult.success) {
        const errs: Record<string, string> = {}
        for (const issue of validResult.error.issues) {
          errs[issue.path[0] as string] = issue.message
        }
        setErrors(errs)
        throw new Error('Validation failed')
      }
      setErrors({})

      if (isEdit) {
        const update: Record<string, unknown> = { name, url, events }
        if (secret) update.secret = secret
        return webhooksApi.update(webhook.id, update)
      }
      return webhooksApi.create({ connector_id: connectorId, name, url, secret, events: events as WebhookEvent[] })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['webhooks', connectorId] })
      onDone()
    },
  })

  const toggleEvent = (ev: string) => {
    setEvents((prev) => prev.includes(ev) ? prev.filter((e) => e !== ev) : [...prev, ev])
  }

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-sm font-semibold text-gray-900">
        {isEdit ? 'Modifier le webhook' : 'Nouveau webhook'}
      </h3>

      {/* Name */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">Nom</label>
        <input
          className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Mon webhook"
        />
        {errors.name && <p className="text-xs text-red-600 mt-1">{errors.name}</p>}
      </div>

      {/* URL */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">URL cible</label>
        <input
          className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com/webhook"
          type="url"
        />
        {errors.url && <p className="text-xs text-red-600 mt-1">{errors.url}</p>}
      </div>

      {/* Secret */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">
          Secret HMAC {isEdit && <span className="text-gray-400">(laisser vide pour ne pas changer)</span>}
        </label>
        <div className="flex gap-2">
          <input
            className="flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            placeholder={isEdit ? '••••••••••••••••' : 'min 16 caractères'}
            type="password"
          />
          <button
            type="button"
            onClick={() => setSecret(generateSecret())}
            className="px-3 py-1.5 rounded-lg border border-gray-300 text-xs text-gray-600 hover:bg-gray-50 whitespace-nowrap"
          >
            Générer
          </button>
        </div>
        {errors.secret && <p className="text-xs text-red-600 mt-1">{errors.secret}</p>}
      </div>

      {/* Events */}
      <div>
        <label className="block text-xs text-gray-500 mb-2">Événements déclencheurs</label>
        <div className="flex flex-col gap-1.5">
          {EVENT_OPTIONS.map(({ value, label }) => (
            <label key={value} className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={events.includes(value)}
                onChange={() => toggleEvent(value)}
                className="rounded border-gray-300 text-brand-600 focus:ring-brand-500"
              />
              <span className="text-sm text-gray-700">{label}</span>
            </label>
          ))}
        </div>
        {errors.events && <p className="text-xs text-red-600 mt-1">{errors.events}</p>}
      </div>

      {save.isError && !Object.keys(errors).length && (
        <p className="text-xs text-red-600">Erreur lors de la sauvegarde</p>
      )}

      <div className="flex gap-2 justify-end pt-1">
        <Button variant="secondary" size="sm" onClick={onCancel}>
          Annuler
        </Button>
        <Button size="sm" onClick={() => save.mutate()} loading={save.isPending}>
          {isEdit ? 'Enregistrer' : 'Créer'}
        </Button>
      </div>
    </div>
  )
}
