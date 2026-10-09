<!-- Shared editor UX; calculations and validation live in the framework-neutral core. -->
<template>
  <q-card class="gravity-formula-editor q-mb-md" data-testid="gravity-formula-editor">
    <q-card-section>
      <q-tabs v-model="view" align="left" dense no-caps active-color="primary" indicator-color="primary"
        class="q-mb-md gravity-formula-tabs" aria-label="Gravity formula view">
        <q-tab v-for="option in viewOptions" :key="option.value" :name="option.value" :label="option.label" />
      </q-tabs>
      <p class="text-body2 q-mb-md">
        Saving stores the formula in BrewGraph. It does not change the formula on the device.
        Stored readings are not changed by saving.
      </p>

      <div v-if="view === 'formula'">
        <div class="row q-col-gutter-md">
          <div class="col-12">
            <q-input :model-value="formulaText" @update:model-value="setFormula"
              label="Formula" outlined autogrow type="textarea" input-class="text-mono"
              :maxlength="GRAVITY_FORMULA_MAX_LENGTH" :disable="disabled"
              :error="!!visibleFormulaError" :error-message="visibleFormulaError || undefined"
              aria-label="Formula" />
            <div class="text-caption text-secondary">{{ formulaText.length }} / {{ GRAVITY_FORMULA_MAX_LENGTH }}</div>
          </div>
        </div>
        <p class="text-caption q-mt-sm">
          Use tilt (degrees) and temp (°C), numbers, + - * / ^ and parentheses. The result is in {{ outputUnitLabel }}, the gravity unit of the app.
        </p>

        <div class="row q-col-gutter-sm items-end q-mt-sm">
          <div class="col-6 col-sm-3">
            <q-input v-model="testAngle" label="Test angle (°)" type="number" outlined dense
              min="15" max="90" :disable="disabled" />
          </div>
          <div v-if="usesTemp" class="col-6 col-sm-3">
            <q-input v-model="testTemperature" :label="temperatureUnit === 'f' ? 'Temperature (°F)' : 'Temperature (°C)'"
              type="number" outlined dense :disable="disabled" />
          </div>
          <div class="col-12 col-sm-6" aria-live="polite">{{ testResult }}</div>
        </div>

        <div class="text-subtitle2 q-mt-lg q-mb-sm">Fit candidates</div>
        <div v-for="candidate in candidates" :key="candidate.degree" class="candidate-row q-py-sm">
          <div class="row items-center no-wrap">
            <div class="text-weight-medium">Degree {{ candidate.degree }}</div>
            <div v-if="candidate.formula" class="text-caption text-secondary q-ml-md" aria-live="polite">
              Maximum deviation {{ formatDeviation(candidate.maxDeviation) }}
            </div>
            <q-space />
            <q-btn outline no-caps dense class="q-px-md" label="Use" :disable="disabled || !candidate.formula"
              :aria-label="'Use degree ' + candidate.degree + ' formula'"
              @click="useCandidate(candidate.formula)" />
          </div>
          <div class="text-mono text-caption q-mt-xs" aria-live="polite">{{ candidate.formula || candidate.reason }}</div>
        </div>
      </div>

      <div v-else-if="view === 'table'">
        <div class="row items-center q-gutter-sm q-mb-sm">
          <q-btn outline no-caps icon="add" label="Add point" :disable="disabled || rows.length >= GRAVITY_CALIBRATION_MAX_POINTS"
            @click="addPoint" />
          <span>{{ rows.length }} / 20 points{{ rows.length >= 20 ? ' — maximum reached' : '' }}</span>
        </div>
        <div v-if="rows.length === 0" class="text-secondary">
          No calibration points yet. Add points to fit a formula, or type one.
        </div>
        <div v-for="(row, index) in rows" :key="row.key" class="row q-col-gutter-sm items-start q-mb-sm point-row">
          <div class="col-6 col-sm-2">
            <q-input v-model="row.angle" label="Angle (°)" type="number" outlined dense
              :disable="disabled" :error="!!rowErrors[index]?.angle" :error-message="rowErrors[index]?.angle"
              @update:model-value="markEditing"
              @blur="commitRows" />
          </div>
          <div class="col-6 col-sm-3">
            <q-input v-model="row.gravity" :label="'Gravity (' + displayUnitLabel + ')'"
              type="number" outlined dense :disable="disabled" :error="!!rowErrors[index]?.gravity"
              :error-message="rowErrors[index]?.gravity" @update:model-value="markEditing" @blur="commitRows" />
          </div>
          <div class="col-6 col-sm-3 text-caption q-pt-md">
            Formula: {{ formulaAt(Number(row.angle)) }}
          </div>
          <div class="col-4 col-sm-3 text-caption q-pt-md">
            Δ: {{ deviationAt(index) }}
          </div>
          <div class="col-2 col-sm-1">
            <q-btn flat round icon="delete" color="negative" aria-label="Remove point"
              :disable="disabled" @click="removePoint(index)" />
          </div>
        </div>
        <div v-if="rows.length" class="text-caption q-mt-sm" aria-live="polite">
          Maximum absolute deviation: {{ maxDeviationText }}
        </div>
      </div>

      <div v-else>
        <div v-if="validPoints.length === 0" class="text-secondary">
          Add calibration points to see the graph.
        </div>
        <div v-else class="row q-col-gutter-md">
          <div class="col-12 col-md-9"><canvas ref="chartCanvas"
            :aria-label="'Gravity calibration chart, angle in degrees and gravity in ' + outputUnitLabel"
            role="img" /></div>
          <div class="col-12 col-md-3" aria-live="polite">
            {{ validPoints.length }} points, maximum deviation {{ maxDeviationText }}
          </div>
        </div>
      </div>

      <div v-if="view === 'formula'" class="row q-gutter-sm q-mt-lg">
        <q-btn outline no-caps icon="content_copy" label="Copy formula" :disable="!formulaText"
          @click="copyFormula" />
      </div>
      <input ref="profileInput" type="file" accept=".json,application/json" style="display: none"
        aria-label="Import gravity formula profile" @change="importProfile" />
      <div v-if="profileMessage" class="q-mt-sm" role="status" aria-live="polite">{{ profileMessage }}</div>
      <ul v-if="profileErrors.length" class="text-negative q-mt-sm" role="alert">
        <li v-for="error in profileErrors" :key="error">{{ error }}</li>
      </ul>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { copyToClipboard } from 'quasar'
import { Chart, registerables } from 'chart.js'
import {
  GRAVITY_FORMULA_MAX_LENGTH, GRAVITY_CALIBRATION_MAX_POINTS,
  evaluateFormula, fitPolynomial, parseProfile, serializeProfile, validateFormula,
  FormulaProfileError, type CalibrationPoint, type FormulaUnit
} from '@/core/gravityFormula'
import { gravityToPlato, platoToGravity } from '@/core/calculations/units'

Chart.register(...registerables)

type Row = { key: number; angle: string; gravity: string }
type Issue = { angle?: string; gravity?: string }
type Candidate = { degree: number; formula: string; maxDeviation: number; reason: string }
const props = withDefaults(defineProps<{
  formula: string | null
  unit: FormulaUnit | null
  points: CalibrationPoint[]
  deviceName: string
  deviceType: string | null
  displayUnit?: FormulaUnit
  temperatureUnit?: 'c' | 'f'
  disabled?: boolean
}>(), { displayUnit: 'sg', temperatureUnit: 'c', disabled: false })
const emit = defineEmits<{
  'update:formula': [value: string | null]
  'update:unit': [value: FormulaUnit | null]
  'update:points': [value: CalibrationPoint[]]
  valid: [value: boolean]
  editing: [value: boolean]
  copied: []
}>()
const viewOptions = [{ label: 'Table', value: 'table' }, { label: 'Formula', value: 'formula' }, { label: 'Graph', value: 'graph' }]
// With nothing entered yet the table is what the user needs first.
const view = ref(props.points.length === 0 ? 'table' : 'formula')
// Values are entered in the unit the user chose for the app; there is no switch of its own.
const gravityViewUnit = computed<FormulaUnit>(() => props.displayUnit)
const formulaText = ref(props.formula ?? '')
const visibleFormulaError = ref('')
const testAngle = ref('45')
const testTemperature = ref('20')
const profileInput = ref<HTMLInputElement | null>(null)
const profileErrors = ref<string[]>([])
const profileMessage = ref('')
const chartCanvas = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null
let timer: ReturnType<typeof setTimeout> | undefined
let rowKey = 0
const toDisplay = (sg: number) => gravityViewUnit.value === 'plato' ? gravityToPlato(sg) : sg
const toSg = (value: number) => gravityViewUnit.value === 'plato' ? platoToGravity(value) : value
// Entered values are shown rounded, so a conversion never leaves floating-point noise in a field.
const displayText = (sg: number) => String(Number(toDisplay(sg).toFixed(gravityViewUnit.value === 'plato' ? 3 : 6)))
const rows = ref<Row[]>(props.points.map(p => ({ key: rowKey++, angle: String(p.angle), gravity: displayText(p.gravity) })))
// With no formula and no explicit choice there is nothing to interpret, so the unit starts at
// the user's own gravity preference; a saved formula keeps the unit it was saved with.
const effectiveUnit = computed<FormulaUnit>(() =>
  props.formula ? (props.unit ?? props.displayUnit) : props.displayUnit)
const displayUnitLabel = computed(() => gravityViewUnit.value === 'plato' ? '°P' : 'SG')
// The unit the formula itself returns; the Formula and Graph views are shown in it, while the
const outputUnitLabel = computed(() => effectiveUnit.value === 'plato' ? '°P' : 'SG')
const toOutput = (sg: number) => effectiveUnit.value === 'plato' ? gravityToPlato(sg) : sg
const gravityLimitText = computed(() => {
  const decimals = gravityViewUnit.value === 'plato' ? 2 : 3
  return toDisplay(0.98).toFixed(decimals) + ' and ' + toDisplay(1.25).toFixed(decimals) + ' ' + displayUnitLabel.value
})
const usesTemp = computed(() => /\btemp\b/.test(formulaText.value))
const formulaError = computed(() => {
  if (!formulaText.value.trim()) return ''
  try { validateFormula(formulaText.value); return '' } catch (error) { return (error as Error).message }
})
watch(formulaText, () => {
  clearTimeout(timer)
  timer = setTimeout(() => { visibleFormulaError.value = formulaError.value }, 200)
})
watch(() => props.formula, value => { if ((value ?? '') !== formulaText.value) formulaText.value = value ?? '' })
watch(() => props.points, value => {
  rows.value = value.map(p => ({ key: rowKey++, angle: String(p.angle), gravity: displayText(p.gravity) }))
}, { deep: true })
const rowErrors = computed<Issue[]>(() => rows.value.map((row, index) => {
  const angle = Number(row.angle)
  const gravity = Number(row.gravity)
  const issue: Issue = {}
  if (!row.angle.trim() || !Number.isFinite(angle) || angle < 15 || angle > 90) issue.angle = 'Angle must be between 15° and 90°'
  else if (rows.value.some((other, otherIndex) => otherIndex !== index && Number(other.angle) === angle)) issue.angle = 'Duplicate angle ' + angle
  const sg = toSg(gravity)
  if (!row.gravity.trim() || !Number.isFinite(gravity) || !Number.isFinite(sg) || sg < 0.98 || sg > 1.25) {
    issue.gravity = 'Gravity must be between ' + gravityLimitText.value
  }
  return issue
}))
const validPoints = computed<CalibrationPoint[]>(() => rows.value.flatMap((row, index) =>
  rowErrors.value[index]?.angle || rowErrors.value[index]?.gravity ? [] :
    [{ angle: Number(row.angle), gravity: toSg(Number(row.gravity)) }]))
const isValid = computed(() => !formulaError.value && rowErrors.value.every(issue => !issue.angle && !issue.gravity))
watch(isValid, value => emit('valid', value), { immediate: true })
function markEditing() { emit('editing', true) }
function setFormula(value: string | number | null) {
  formulaText.value = String(value ?? '')
  // The first formula is saved with an explicit unit, so a later change of the preference
  // never changes how the stored formula is read.
  if (formulaText.value.trim() && !props.formula) emit('update:unit', effectiveUnit.value)
  emit('update:formula', formulaText.value.trim() || null)
}
function commitRows() {
  if (rowErrors.value.some(issue => issue.angle || issue.gravity)) return
  emit('update:points', [...validPoints.value].sort((a, b) => a.angle - b.angle))
  emit('editing', false)
}
function addPoint() {
  if (rows.value.length >= GRAVITY_CALIBRATION_MAX_POINTS) return
  rows.value.push({ key: rowKey++, angle: '', gravity: '' })
  markEditing()
}
function removePoint(index: number) { rows.value.splice(index, 1); commitRows() }
const candidates = computed<Candidate[]>(() => [1, 2, 3, 4].map(degree => {
  if (validPoints.value.length < degree + 1) return { degree, formula: '', maxDeviation: 0,
    reason: 'Needs ' + (degree + 1 - validPoints.value.length) + ' more points' }
  try {
    const fit = fitPolynomial(validPoints.value, degree, effectiveUnit.value)
    return { degree, formula: fit.formula, maxDeviation: fit.maxDeviation, reason: '' }
  } catch (error) {
    return { degree, formula: '', maxDeviation: 0, reason: (error as Error).message }
  }
}))
function formatDeviation(value: number) {
  return (value >= 0 ? '+' : '') + value.toFixed(effectiveUnit.value === 'plato' ? 2 : 4) +
    (effectiveUnit.value === 'plato' ? ' °P' : ' SG')
}
function useCandidate(formula: string) { setFormula(formula) }
const testResult = computed(() => {
  if (!formulaText.value.trim()) return 'Enter a formula to test it.'
  if (formulaError.value) return formulaError.value
  try {
    const temperature = usesTemp.value ? Number(testTemperature.value) : undefined
    const celsius = temperature === undefined ? undefined :
      props.temperatureUnit === 'f' ? (temperature - 32) / 1.8 : temperature
    const sg = evaluateFormula(formulaText.value, Number(testAngle.value), celsius, effectiveUnit.value)
    return 'Result: ' + toOutput(sg).toFixed(effectiveUnit.value === 'plato' ? 2 : 4) + ' ' + outputUnitLabel.value
  } catch (error) { return (error as Error).message }
})
function formulaSgAt(angle: number): number | null {
  if (!formulaText.value.trim() || formulaError.value) return null
  try { return evaluateFormula(formulaText.value, angle, undefined, effectiveUnit.value) }
  catch { return null }
}
function formulaAt(angle: number): string {
  const sg = formulaSgAt(angle)
  return sg == null ? '—' : toDisplay(sg).toFixed(gravityViewUnit.value === 'plato' ? 2 : 4)
}
function deviationAt(index: number): string {
  const point = validPoints.value.find(p => p.angle === Number(rows.value[index]?.angle))
  const sg = point && formulaSgAt(point.angle)
  if (!point || sg == null) return '—'
  const delta = effectiveUnit.value === 'plato' ? gravityToPlato(sg) - gravityToPlato(point.gravity) : sg - point.gravity
  return formatDeviation(delta)
}
const maxDeviationText = computed(() => {
  const deviations = validPoints.value.map(point => {
    const sg = formulaSgAt(point.angle)
    if (sg == null) return null
    return Math.abs(effectiveUnit.value === 'plato' ? gravityToPlato(sg) - gravityToPlato(point.gravity) : sg - point.gravity)
  }).filter((value): value is number => value !== null)
  return deviations.length ? formatDeviation(Math.max(...deviations)) : '—'
})
const curveColours = ['#ef6c00', '#8e24aa', '#00897b', '#6d4c41']
function curve(text: string) {
  const points: { x: number; y: number }[] = []
  for (let index = 0; index <= 50; index++) {
    const angle = 15 + index * 1.5
    try { points.push({ x: angle, y: toOutput(evaluateFormula(text, angle, undefined, effectiveUnit.value)) }) } catch { /* outside the valid range */ }
  }
  return points
}
async function drawChart() {
  chart?.destroy(); chart = null
  if (view.value !== 'graph' || !chartCanvas.value || !validPoints.value.length) return
  const current = formulaText.value.trim()
  const currentValid = !!current && !formulaError.value
  const selected = candidates.value.find(candidate => candidate.formula && candidate.formula === current)
  const datasets: object[] = candidates.value.filter(candidate => candidate.formula).map(candidate => {
    const isSelected = candidate === selected
    return { label: 'Degree ' + candidate.degree + (isSelected ? ' (selected)' : ''), type: 'line', data: curve(candidate.formula),
      borderColor: isSelected ? '#2e7d32' : curveColours[candidate.degree - 1], borderWidth: isSelected ? 4 : 1.5,
      borderDash: isSelected ? [] : [6, 4], pointRadius: 0, showLine: true, order: isSelected ? 1 : 2 }
  })
  if (currentValid && !selected) {
    datasets.push({ label: 'Selected formula', type: 'line', data: curve(current), borderColor: '#2e7d32', borderWidth: 4,
      pointRadius: 0, showLine: true, order: 1 })
  }
  chart = new Chart(chartCanvas.value, {
    type: 'scatter',
    data: { datasets: [
      { label: 'Calibration points', data: validPoints.value.map(p => ({ x: p.angle, y: toOutput(p.gravity) })),
        pointRadius: 5, backgroundColor: '#1976d2', order: 0 },
      ...datasets
    ] } as never,
    options: { responsive: true, scales: { x: { type: 'linear', title: { display: true, text: 'Angle (°)' } },
      y: { title: { display: true, text: 'Gravity (' + outputUnitLabel.value + ')' } } } }
  })
}
watch([view, validPoints, formulaText, effectiveUnit, candidates], async () => {
  await nextTick(); await drawChart()
})
onBeforeUnmount(() => { clearTimeout(timer); chart?.destroy() })
async function copyFormula() {
  await copyToClipboard(formulaText.value)
  emit('copied')
}
async function importProfile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  profileErrors.value = []; profileMessage.value = ''
  try {
    const profile = parseProfile(await file.text(), props.deviceType ?? '')
    setFormula(profile.gravityFormula)
    emit('update:unit', profile.gravityFormulaUnit)
    emit('update:points', profile.gravityCalibrationData)
    emit('editing', false)
    profileMessage.value = 'Imported. Review and save.'
  } catch (error) {
    profileErrors.value = error instanceof FormulaProfileError ? error.issues : [(error as Error).message]
  }
}
function exportProfile() {
  try {
    if (rowErrors.value.some(issue => issue.angle || issue.gravity)) {
      throw new Error('Fix invalid calibration points before exporting')
    }
    const json = serializeProfile(formulaText.value.trim() || null, effectiveUnit.value, validPoints.value)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'gravity-formula-' + props.deviceName.replace(/[^a-z0-9-]+/gi, '-').toLowerCase() + '.json'
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) { profileErrors.value = [(error as Error).message] }
}

// The page places the import and export buttons; the editor owns what they do.
defineExpose({ openImport: () => profileInput.value?.click(), exportProfile })
</script>

<style scoped>
.gravity-formula-editor { max-width: 100%; }
.candidate-row + .candidate-row { border-top: 1px solid var(--q-separator-color, #ddd); }
.text-mono { overflow-wrap: anywhere; }
canvas { max-width: 100%; }
</style>
