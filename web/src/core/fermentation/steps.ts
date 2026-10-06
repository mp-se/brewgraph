import { tempToC, tempToF } from '../calculations/units'

export interface EditorFermentationStep {
  order: number
  name: string
  type: string
  temp: number
  days: number
  date: string | null
  control?: string
}

export interface FermentationStepOptions {
  /** Editor input/output temperatures are Fahrenheit; storage remains Celsius. */
  usesFahrenheit?: boolean
}

const useFahrenheit = (options: FermentationStepOptions) => options.usesFahrenheit === true

export function parseFermentationStepsForEditor(
  stepsRaw: unknown,
  options: FermentationStepOptions = {}
): EditorFermentationStep[] {
  if (!stepsRaw) return []

  try {
    const parsed = typeof stepsRaw === 'string' ? JSON.parse(stepsRaw) : stepsRaw
    if (!Array.isArray(parsed)) return []
    return parsed.map((step, index) => ({
      order: step.order ?? index,
      name: step.name ?? `Step ${index + 1}`,
      type: step.type ?? 'Hold',
      temp: useFahrenheit(options)
        ? Number(tempToF(Number(step.temp ?? 20)).toFixed(1))
        : Number(step.temp ?? 20),
      days: Number(step.days ?? 1),
      date: step.date ?? ''
    }))
  } catch {
    return []
  }
}

export function stepsInCelsius(
  steps: readonly EditorFermentationStep[],
  options: FermentationStepOptions = {}
): EditorFermentationStep[] {
  if (!Array.isArray(steps)) return []
  return useFahrenheit(options) ? steps.map((step) => ({ ...step, temp: tempToC(step.temp) })) : [...steps]
}

function normalizeStep(step: EditorFermentationStep, index: number) {
  return {
    order: step.order ?? index,
    name: step.name ?? `Step ${index + 1}`,
    type: step.type ?? '',
    temp: Number(step.temp ?? 20),
    days: Number(step.days ?? 1),
    date: typeof step.date === 'string' && step.date.trim() ? step.date : null,
    control: step.control ?? 'fridge'
  }
}

export function serializeFermentationSteps(
  steps: readonly EditorFermentationStep[],
  options: FermentationStepOptions = {}
): string {
  const normalized = stepsInCelsius(steps, options).map(normalizeStep)
  return normalized.length > 0 ? JSON.stringify(normalized) : ''
}

export function fermentationStepsPayload(
  batchId: string,
  steps: readonly EditorFermentationStep[],
  options: FermentationStepOptions = {}
) {
  return stepsInCelsius(steps, options).map((step, index) => ({
    ...normalizeStep({ ...step, order: index }, index),
    batchId
  }))
}

/** True when a date window includes `at`, defaulting to the current local day. */
export function hasActiveFermentationStepAt(steps: unknown, at: Date = new Date()): boolean {
  if (!Array.isArray(steps)) return false

  const today = new Date(at)
  today.setHours(0, 0, 0, 0)

  return steps.some((step) => {
    if (typeof step?.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(step.date)) return false

    const start = new Date(`${step.date}T00:00:00`)
    if (Number.isNaN(start.getTime())) return false

    const days = Math.max(1, Number(step.days ?? 1))
    const end = new Date(start)
    end.setDate(start.getDate() + days - 1)
    return start <= today && today <= end
  })
}
