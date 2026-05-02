import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronRight, ChevronLeft, Plus, Trash2, GripVertical, GitMerge, HelpCircle } from 'lucide-react'
import { pipelinesApi, type PipelineRead, type PipelineStepCreate } from '@/lib/api/pipelines'
import { connectorsApi, type Connector } from '@/lib/api/connectors'

// ── Types ──────────────────────────────────────────────────────────────────────

interface StepDraft extends PipelineStepCreate {
  _key: string
}

const MERGE_OPTIONS = [
  { value: 'merge', label: 'Merge', desc: 'Fusion profonde de tous les résultats' },
  { value: 'first', label: 'Premier', desc: 'Retourne uniquement le résultat du step 1' },
  { value: 'last', label: 'Dernier', desc: 'Retourne uniquement le résultat du dernier step' },
  { value: 'custom', label: 'Custom', desc: 'Tous les résultats indexés par step — utilisez output_transform' },
] as const

// ── Step editor modal ──────────────────────────────────────────────────────────

function StepModal({
  step,
  stepIndex,
  connectors,
  previousSteps,
  onSave,
  onClose,
}: {
  step: StepDraft
  stepIndex: number
  connectors: { id: string; name: string; type: string }[]
  previousSteps: StepDraft[]
  onSave: (s: StepDraft) => void
  onClose: () => void
}) {
  const [draft, setDraft] = useState<StepDraft>({ ...step })
  const [paramsText, setParamsText] = useState(JSON.stringify(draft.params_template, null, 2))
  const [paramsError, setParamsError] = useState('')

  const suggestions = [
    '{{input.}}',
    ...previousSteps.map((s) => `{{steps.${s.step_order}.result.}}`),
    ...previousSteps.map((s) => `{{steps.${s.step_order}.status}}`),
  ]

  const handleSave = () => {
    try {
      draft.params_template = JSON.parse(paramsText)
      setParamsError('')
    } catch {
      setParamsError('JSON invalide')
      return
    }
    onSave(draft)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-xl w-full max-w-lg shadow-xl flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="font-semibold text-gray-900">Configurer le step {stepIndex + 1}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nom</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={draft.name}
              onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Connecteur</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={draft.connector_id}
              onChange={(e) => setDraft((d) => ({ ...d, connector_id: e.target.value }))}
            >
              <option value="">— Sélectionner —</option>
              {connectors.map((c) => (
                <option key={c.id} value={c.id}>{c.name} ({c.type})</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Mode d'exécution</label>
            <div className="flex gap-3">
              {(['sequential', 'parallel'] as const).map((m) => (
                <label key={m} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="execution_mode"
                    value={m}
                    checked={draft.execution_mode === m}
                    onChange={() => setDraft((d) => ({ ...d, execution_mode: m }))}
                    className="accent-brand-600"
                  />
                  <span className="text-sm text-gray-700">{m === 'sequential' ? 'Séquentiel' : 'Parallèle'}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">En cas d'erreur</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={draft.on_error}
              onChange={(e) => setDraft((d) => ({ ...d, on_error: e.target.value as StepDraft['on_error'] }))}
            >
              <option value="stop">Stopper le pipeline</option>
              <option value="skip">Ignorer (continuer sans ce résultat)</option>
              <option value="continue">Continuer</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Timeout (secondes)</label>
            <input
              type="number"
              min={1}
              max={300}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={draft.timeout_seconds}
              onChange={(e) => setDraft((d) => ({ ...d, timeout_seconds: Number(e.target.value) }))}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Condition (optionnel)</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="{{steps.1.status}} == 'success'"
              value={draft.condition ?? ''}
              onChange={(e) => setDraft((d) => ({ ...d, condition: e.target.value || null }))}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Params template (JSON)</label>
            {previousSteps.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-1">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => setParamsText((t) => t.replace(/"\s*}$/, `"${s}"}`).replace('{}', `{"key": "${s}"}`))}
                    className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600 hover:bg-gray-200 font-mono"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
            <textarea
              rows={5}
              className={`w-full border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500 ${paramsError ? 'border-red-300' : 'border-gray-300'}`}
              value={paramsText}
              onChange={(e) => setParamsText(e.target.value)}
            />
            {paramsError && <p className="text-xs text-red-500 mt-1">{paramsError}</p>}
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-200">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">Annuler</button>
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700"
          >
            Enregistrer
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Wizard state ───────────────────────────────────────────────────────────────

interface WizardState {
  name: string
  description: string
  mergeStrategy: 'merge' | 'first' | 'last' | 'custom'
  outputTransformText: string
  steps: StepDraft[]
}

function initWizardState(pipeline?: PipelineRead): WizardState {
  return {
    name: pipeline?.name ?? '',
    description: pipeline?.description ?? '',
    mergeStrategy: pipeline?.merge_strategy ?? 'merge',
    outputTransformText: pipeline?.output_transform
      ? JSON.stringify(pipeline.output_transform, null, 2)
      : '{}',
    steps: pipeline?.steps.map((s) => ({
      _key: s.id,
      connector_id: s.connector_id,
      step_order: s.step_order,
      name: s.name,
      execution_mode: s.execution_mode,
      params_template: s.params_template,
      condition: s.condition,
      on_error: s.on_error,
      timeout_seconds: s.timeout_seconds,
    })) ?? [],
  }
}

// ── Main Wizard ────────────────────────────────────────────────────────────────

export function PipelineWizard({ pipeline }: { pipeline?: PipelineRead } = {}) {
  const isEditMode = !!pipeline
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [wizardStep, setWizardStep] = useState(1)
  const [wizardState, setWizardState] = useState<WizardState>(() => initWizardState(pipeline))
  const [outputTransformError, setOutputTransformError] = useState('')
  const [editingStep, setEditingStep] = useState<{ step: StepDraft; index: number } | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const { name, description, mergeStrategy, outputTransformText, steps } = wizardState

  const patch = (updates: Partial<WizardState>) =>
    setWizardState((prev) => ({ ...prev, ...updates }))

  const { data: connectors = [] } = useQuery<Connector[]>({
    queryKey: ['connectors'],
    queryFn: connectorsApi.getConnectors,
  })

  const addStep = () => {
    const maxOrder = steps.length > 0 ? Math.max(...steps.map((s) => s.step_order)) : 0
    const newStep: StepDraft = {
      _key: crypto.randomUUID(),
      connector_id: '',
      step_order: maxOrder + 1,
      name: `Step ${maxOrder + 1}`,
      execution_mode: 'sequential',
      params_template: {},
      condition: null,
      on_error: 'stop',
      timeout_seconds: 30,
    }
    patch({ steps: [...steps, newStep] })
    setEditingStep({ step: newStep, index: steps.length })
  }

  const removeStep = (key: string) => {
    const filtered = steps.filter((s) => s._key !== key)
    patch({ steps: filtered.map((s, i) => ({ ...s, step_order: i + 1 })) })
  }

  const saveStep = (updated: StepDraft) => {
    patch({ steps: steps.map((s) => (s._key === updated._key ? updated : s)) })
    setEditingStep(null)
  }

  const canProceedStep1 = name.trim().length > 0
  const canProceedStep2 = steps.length >= 2 && steps.every((s) => s.connector_id)

  const handleSubmit = async () => {
    let outputTransform = null
    if (outputTransformText.trim() && outputTransformText.trim() !== '{}') {
      try {
        outputTransform = JSON.parse(outputTransformText)
      } catch {
        setOutputTransformError('JSON invalide')
        return
      }
    }

    setSubmitting(true)
    setError('')
    try {
      const payload = {
        name,
        description: description || undefined,
        merge_strategy: mergeStrategy,
        output_transform: outputTransform,
        steps: steps.map(({ _key, ...s }) => s),
      }

      if (isEditMode) {
        await pipelinesApi.update(pipeline.id, payload)
        qc.invalidateQueries({ queryKey: ['pipeline', pipeline.id] })
        qc.invalidateQueries({ queryKey: ['pipelines'] })
        navigate(`/dashboard/pipelines/${pipeline.id}`)
      } else {
        const created = await pipelinesApi.create(payload)
        navigate(`/dashboard/pipelines/${created.id}`)
      }
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? (isEditMode ? 'Erreur lors de la modification' : 'Erreur lors de la création'))
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          {isEditMode ? 'Modifier le pipeline' : 'Nouveau pipeline'}
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          {isEditMode
            ? `Modification de "${pipeline.name}"`
            : 'Enchaînez des connecteurs en 4 étapes'}
        </p>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-2">
        {['Informations', 'Étapes', 'Transform', 'Récapitulatif'].map((label, i) => (
          <div key={label} className="flex items-center gap-2">
            <div className={`flex items-center gap-1.5 ${i + 1 === wizardStep ? 'text-brand-600' : i + 1 < wizardStep ? 'text-green-600' : 'text-gray-400'}`}>
              <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border-2 ${i + 1 === wizardStep ? 'border-brand-600 bg-brand-50' : i + 1 < wizardStep ? 'border-green-600 bg-green-50' : 'border-gray-300'}`}>
                {i + 1}
              </span>
              <span className="text-sm font-medium hidden sm:block">{label}</span>
            </div>
            {i < 3 && <ChevronRight className="h-4 w-4 text-gray-300 flex-shrink-0" />}
          </div>
        ))}
      </div>

      {/* Wizard step 1 — Informations */}
      {wizardStep === 1 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-gray-800">Informations générales</h2>
            <Link
              to="/dashboard/pipelines/docs"
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-brand-600 transition-colors"
            >
              <HelpCircle className="h-3.5 w-3.5" />
              Comment ça marche ?
            </Link>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nom du pipeline *</label>
            <input
              autoFocus
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="ex: Qualification Lead Insurance"
              value={name}
              onChange={(e) => patch({ name: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description (optionnel)</label>
            <textarea
              rows={2}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="Décrivez ce que fait ce pipeline…"
              value={description}
              onChange={(e) => patch({ description: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Stratégie de fusion</label>
            <div className="grid grid-cols-2 gap-3">
              {MERGE_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className={`flex flex-col gap-0.5 p-3 rounded-lg border-2 cursor-pointer transition-colors ${mergeStrategy === opt.value ? 'border-brand-500 bg-brand-50' : 'border-gray-200 hover:border-gray-300'}`}
                >
                  <input type="radio" name="merge" value={opt.value} checked={mergeStrategy === opt.value} onChange={() => patch({ mergeStrategy: opt.value })} className="sr-only" />
                  <span className="text-sm font-semibold text-gray-900">{opt.label}</span>
                  <span className="text-xs text-gray-500">{opt.desc}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Wizard step 2 — Steps */}
      {wizardStep === 2 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <h2 className="font-semibold text-gray-800">Étapes du pipeline</h2>
          <p className="text-sm text-gray-500">Minimum 2 étapes. Cliquez "Éditer" pour configurer les params et les variables.</p>

          <div className="space-y-2">
            {steps.map((s, idx) => {
              const connector = connectors.find((c) => c.id === s.connector_id)
              return (
                <div key={s._key} className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 bg-gray-50">
                  <GripVertical className="h-4 w-4 text-gray-400 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-brand-100 text-brand-700 text-xs font-bold flex items-center justify-center flex-shrink-0">{s.step_order}</span>
                      <span className="font-medium text-sm text-gray-900 truncate">{s.name}</span>
                      <span className={`px-1.5 py-0.5 rounded text-xs ${s.execution_mode === 'parallel' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'}`}>
                        {s.execution_mode === 'parallel' ? 'parallèle' : 'séquentiel'}
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 mt-0.5 pl-7">
                      {connector ? `${connector.name} (${connector.type})` : <span className="text-red-400">Connecteur non sélectionné</span>}
                    </p>
                  </div>
                  <button onClick={() => setEditingStep({ step: s, index: idx })} className="text-xs text-brand-600 hover:underline px-2">Éditer</button>
                  <button onClick={() => removeStep(s._key)} className="text-gray-400 hover:text-red-500">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              )
            })}
          </div>

          <button
            onClick={addStep}
            className="w-full flex items-center justify-center gap-2 py-2.5 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-500 hover:border-brand-400 hover:text-brand-600 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Ajouter une étape
          </button>

          {steps.length < 2 && (
            <p className="text-xs text-amber-600 bg-amber-50 px-3 py-2 rounded-lg">Minimum 2 étapes requises</p>
          )}
        </div>
      )}

      {/* Wizard step 3 — Transform */}
      {wizardStep === 3 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <h2 className="font-semibold text-gray-800">Transform final (optionnel)</h2>
          <p className="text-sm text-gray-500">Appliqué sur le résultat fusionné. Laissez vide ou <code className="bg-gray-100 px-1 rounded">{'{}'}</code> pour ignorer.</p>
          <textarea
            rows={10}
            className={`w-full border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500 ${outputTransformError ? 'border-red-300' : 'border-gray-300'}`}
            value={outputTransformText}
            onChange={(e) => { patch({ outputTransformText: e.target.value }); setOutputTransformError('') }}
          />
          {outputTransformError && <p className="text-xs text-red-500">{outputTransformError}</p>}
        </div>
      )}

      {/* Wizard step 4 — Recap */}
      {wizardStep === 4 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <h2 className="font-semibold text-gray-800">Récapitulatif</h2>
          <div className="space-y-2 text-sm">
            <div className="flex gap-3"><span className="text-gray-500 w-28">Nom</span><span className="font-medium text-gray-900">{name}</span></div>
            {description && <div className="flex gap-3"><span className="text-gray-500 w-28">Description</span><span className="text-gray-700">{description}</span></div>}
            <div className="flex gap-3"><span className="text-gray-500 w-28">Fusion</span><span className="font-medium text-gray-900">{mergeStrategy}</span></div>
            <div className="flex gap-3">
              <span className="text-gray-500 w-28">Steps</span>
              <div className="flex-1 space-y-1">
                {steps.map((s) => {
                  const c = connectors.find((x) => x.id === s.connector_id)
                  return (
                    <div key={s._key} className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-gray-100 text-gray-600 text-xs font-bold flex items-center justify-center">{s.step_order}</span>
                      <span className="text-gray-800">{s.name}</span>
                      <span className="text-gray-400 text-xs">— {c?.name ?? '?'}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
          {error && <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between">
        <button
          onClick={() =>
            wizardStep > 1
              ? setWizardStep((s) => s - 1)
              : navigate(isEditMode ? `/dashboard/pipelines/${pipeline.id}` : '/dashboard/pipelines')
          }
          className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 hover:text-gray-900"
        >
          <ChevronLeft className="h-4 w-4" />
          {wizardStep > 1 ? 'Précédent' : 'Annuler'}
        </button>

        {wizardStep < 4 ? (
          <button
            onClick={() => setWizardStep((s) => s + 1)}
            disabled={wizardStep === 1 ? !canProceedStep1 : wizardStep === 2 ? !canProceedStep2 : false}
            className="flex items-center gap-2 px-5 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Suivant <ChevronRight className="h-4 w-4" />
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="flex items-center gap-2 px-5 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700 disabled:opacity-60"
          >
            <GitMerge className="h-4 w-4" />
            {submitting
              ? isEditMode ? 'Sauvegarde…' : 'Création…'
              : isEditMode ? 'Sauvegarder les modifications' : 'Créer le pipeline'}
          </button>
        )}
      </div>

      {/* Step edit modal */}
      {editingStep && (
        <StepModal
          step={editingStep.step}
          stepIndex={editingStep.index}
          connectors={connectors.map((c) => ({ id: c.id, name: c.name, type: c.type }))}
          previousSteps={steps.filter((s) => s.step_order < editingStep.step.step_order)}
          onSave={saveStep}
          onClose={() => setEditingStep(null)}
        />
      )}
    </div>
  )
}
