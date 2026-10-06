<!--
  Copyright (c) 2024-2026 Magnus Persson
  SPDX-License-Identifier: GPL-3.0-only
  BrewGraph — https://github.com/mp-se/brewgraph

  This file is part of BrewGraph. For open source use it is licensed under
  the GNU General Public License v3.0. For commercial use without source
  disclosure, a separate Commercial License is required.
  See LICENSE for details.
-->

<template>
  <div class="app-page">
    <AppPageHeader title="Integrations" />

    <p class="text-grey-7">
      Forward accepted gravity, pressure, pour, and temperature readings to an external service
      in the background. Configure any number of targets, including several of the same type for
      the same measurement.
    </p>
    <hr />
    <p class="text-subtitle1">{{ editingId ? 'Edit target' : 'Add target' }}</p>

    <div class="row q-col-gutter-sm">
      <div class="col-md-6">
        <AppTextInput v-model="form.name" label="Name" help="" :disabled="global.disabled" />
      </div>
      <div class="col-md-3">
        <AppSelect
          v-model="form.measurement"
          :options="measurementOptions"
          label="Measurement"
          help=""
          :disabled="global.disabled || !!editingId"
          @update:modelValue="onMeasurementChange"
        ></AppSelect>
      </div>
      <div class="col-md-3">
        <AppSelect
          v-model="form.type"
          :options="typeOptionsForMeasurement"
          label="Type"
          help=""
          :disabled="global.disabled || !!editingId"
        ></AppSelect>
      </div>
      <div :class="isCustom ? 'col-md-9' : 'col-md-12'">
        <AppTextInput
          v-model="form.config.url"
          type="url"
          label="URL"
          help="Destination the reading is forwarded to"
          placeholder="https://..."
          :disabled="global.disabled"
        />
        <div v-if="urlError" class="app-field-help text-negative">{{ urlError }}</div>
      </div>
      <div v-if="isCustom" class="col-md-3">
        <AppSelect
          v-model="form.config.method"
          :options="methodOptions"
          label="Method"
          help=""
          :disabled="global.disabled"
        ></AppSelect>
      </div>

      <template v-if="isCustom">
        <div class="col-md-12">
          <label class="app-field-label">Headers</label>
          <div v-for="(h, idx) in headerRows" :key="idx" class="row q-gutter-sm q-mb-sm">
            <input
              type="text"
              class="app-native-input"
              v-model="h.key"
              placeholder="Header name"
              :disabled="global.disabled"
            />
            <input
              type="text"
              class="app-native-input"
              v-model="h.value"
              placeholder="Header value"
              :disabled="global.disabled"
            />
            <app-button
              type="button"
              variant="outline-negative" dense
              @click="removeHeaderRow(idx)"
              :disabled="global.disabled"
              aria-label="Remove header"
            >
              <q-icon name="close" />
            </app-button>
          </div>
          <app-button
            type="button"
            variant="outline-secondary" dense
            @click="addHeaderRow"
            :disabled="global.disabled"
          >
            <q-icon name="add" /> Add header
          </app-button>
        </div>
        <div class="col-md-12">
          <label class="app-field-label">Template</label>
          <div class="q-mb-sm row wrap q-gutter-xs">
            <app-button
              v-for="token in templateTokens"
              :key="token"
              type="button"
              variant="outline-secondary" dense
              @click="insertToken(token)"
              :disabled="global.disabled"
            >
              {{ '${' + token + '}' }}
            </app-button>
          </div>
          <textarea
            ref="templateRef"
            v-model="form.config.template"
            class="app-native-input"
            rows="12"
            :placeholder="TEMPLATE_EXAMPLES[form.measurement as Measurement]"
            :disabled="global.disabled"
          ></textarea>
        </div>
      </template>

      <div class="col-md-12 row q-gutter-sm q-mt-sm">
        <app-button
          type="button"
          variant="primary"
          @click="saveTarget"
          :disabled="global.disabled || !canSave"
        >
          <q-icon :name="editingId ? 'save' : 'add_circle'" />
          {{ editingId ? 'Save target' : 'Add target' }}
        </app-button>
        <app-button
          v-if="editingId"
          type="button"
          variant="outline-secondary"
          @click="resetForm"
          :disabled="global.disabled"
        >
          <q-icon name="close" /> Cancel
        </app-button>
        <app-button
          type="button"
          variant="secondary"
          @click="doPreview"
          :disabled="global.disabled"
        >
          <q-icon name="visibility" /> Preview payload
        </app-button>
      </div>
    </div>

    <div v-if="preview" class="row q-mt-md">
      <div class="col-md-12">
        <p class="text-subtitle2">Preview</p>
        <p class="q-mb-xs"><strong>Method:</strong> {{ preview.method }}</p>
        <template v-if="Object.keys(preview.headers).length > 0">
          <p class="q-mb-xs"><strong>Headers</strong></p>
          <pre>{{ JSON.stringify(preview.headers, null, 2) }}</pre>
        </template>
        <p class="q-mb-xs"><strong>Body</strong></p>
        <pre>{{ previewBody }}</pre>
      </div>
    </div>

    <hr />
    <p class="text-subtitle1">Configured targets</p>

    <div v-if="integrationList.length > 0" class="row q-col-gutter-sm q-mb-lg">
      <div class="col-md-6" v-for="i in integrationList" :key="i.id">
        <div class="app-legacy-card full-height">
          <div class="app-legacy-card__body">
            <div class="row justify-between items-start">
              <p class="app-legacy-card__title q-mb-xs text-body1">{{ i.name }}</p>
              <div class="row q-gutter-xs no-wrap">
                <app-button
                  type="button"
                  variant="outline-primary" dense
                  @click.prevent="editTarget(i)"
                  :disabled="global.disabled"
                  title="Edit target"
                  aria-label="Edit target"
                >
                  <q-icon name="edit" />
                </app-button>
                <app-button
                  type="button"
                  variant="outline-negative" dense
                  @click.prevent="deleteTarget(i.id, i.name)"
                  :disabled="global.disabled"
                  title="Delete target"
                  aria-label="Delete target"
                >
                  <q-icon name="delete" />
                </app-button>
              </div>
            </div>
            <div class="row items-center wrap q-gutter-sm q-mb-sm">
              <span class="app-badge app-badge--primary">{{ measurementLabel(i.measurement) }}</span>
              <span class="app-badge app-badge--secondary">{{ typeLabel(i.type) }}</span>
              <AppToggle
                inline
                class="app-switch q-mb-none q-ml-xs"
                :model-value="i.enabled"
                :label="i.enabled ? 'Enabled' : 'Disabled'"
                :disabled="global.disabled"
                @update:model-value="toggleEnabled(i)"
              />
            </div>
            <p class="text-grey-7 text-caption q-mb-none ellipsis" :title="i.config.url">
              {{ i.config.url }}
            </p>
            <p class="text-caption q-mb-sm">
              <span v-if="i.lastSuccessAt">Last success: {{ new Date(i.lastSuccessAt).toLocaleString() }}.</span>
              <span v-if="i.lastFailureAt" class="q-ml-sm text-warning">Last failure: {{ i.lastFailureCode }}.</span>
              <span v-if="i.consecutiveFailures" class="q-ml-sm">{{ i.consecutiveFailures }} consecutive failures.</span>
              <span v-if="!i.enabled && i.disabledReason" class="q-ml-sm">Paused: {{ i.disabledReason }}.</span>
            </p>
            <div class="row q-gutter-sm">
              <app-button type="button" variant="outline-primary" dense :disabled="global.disabled" @click="sendTest(i)">Send test payload</app-button>
              <app-button v-if="!i.enabled" type="button" variant="outline-positive" dense :disabled="global.disabled" @click="resume(i)">Resume</app-button>
            </div>
          </div>
        </div>
      </div>
    </div>
    <template v-else>
      <p class="text-grey-7 q-mb-lg">No integration targets configured.</p>
    </template>

    <AppConfirmDialog
      :callback="confirmDeleteCallback"
      :message="confirmDeleteMessage"
      id="deleteIntegration"
      title="Delete target"
      :disabled="global.disabled"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { global, integrationStore } from '@/modules/pinia'
import { logDebug } from '@/ui'
import {
  Integration,
  integrationTypeOptions,
  integrationTypeOptionsFor,
  measurementOptions,
  INTEGRATION_TYPE_ISPINDEL_FORWARD,
  INTEGRATION_TYPE_CUSTOM_FORWARD,
  MEASUREMENT_GRAVITY
} from '@/modules/classes'
import AppPageHeader from '@/components/AppPageHeader.vue'
import {
  integrationTypeAfterMeasurementChange,
  previewIntegration,
  TEMPLATE_EXAMPLES,
  TEMPLATE_TOKENS_BY_MEASUREMENT,
  type Measurement,
  type IntegrationPreview
} from '@brewgraph/core'

interface HeaderRow {
  key: string
  value: string
}

const integrationList = computed(() => integrationStore.integrationList)
const methodOptions = [
  { label: 'POST', value: 'POST' },
  { label: 'GET', value: 'GET' }
]

const form = reactive({
  name: '',
  measurement: MEASUREMENT_GRAVITY as string,
  type: INTEGRATION_TYPE_ISPINDEL_FORWARD as string,
  config: {
    url: '',
    method: 'POST',
    template: ''
  }
})

const typeOptionsForMeasurement = computed(() => integrationTypeOptionsFor(form.measurement))
const templateTokens = computed(
  () => TEMPLATE_TOKENS_BY_MEASUREMENT[form.measurement as Measurement]
)

/** Gravity offers all three types, pressure and temperature Brewfather custom stream and Custom,
 * pour only Custom — if the currently-selected type isn't valid for the newly-selected
 * measurement, fall back to the one type every measurement offers. */
function onMeasurementChange() {
  form.type = integrationTypeAfterMeasurementChange(form.type, form.measurement)
}

// A custom target starts from the complete JSON example for its measurement; the user edits it down.
// An empty template, or one that is still an untouched example, follows the measurement and type.
watch(
  () => [form.type, form.measurement] as const,
  ([type, measurement]) => {
    if (type !== INTEGRATION_TYPE_CUSTOM_FORWARD) return
    const current = form.config.template.trim()
    if (current === '' || Object.values(TEMPLATE_EXAMPLES).includes(form.config.template)) {
      form.config.template = TEMPLATE_EXAMPLES[measurement as Measurement]
    }
  }
)

const headerRows = ref<HeaderRow[]>([])
const editingId = ref<string | null>(null)
const templateRef = ref<HTMLTextAreaElement | null>(null)
const preview = ref<IntegrationPreview | null>(null)

const confirmDeleteId = ref<string | null>(null)
const confirmDeleteMessage = ref('')

const isCustom = computed(() => form.type === INTEGRATION_TYPE_CUSTOM_FORWARD)

/** Syntactic check only — scheme + host, mirroring the server's own first check
 * (`core.utils.assert_outbound_url_safe`). The DNS/loopback/link-local check that
 * function also does is IO-bearing and stays server-side; this just keeps an
 * obviously-malformed address from ever reaching that call. */
function isValidHttpUrl(value: string): boolean {
  let parsed: URL
  try {
    parsed = new URL(value)
  } catch {
    return false
  }
  return (parsed.protocol === 'http:' || parsed.protocol === 'https:') && parsed.hostname !== ''
}

const urlError = computed(() => {
  const url = form.config.url.trim()
  if (!url || isValidHttpUrl(url)) return ''
  return 'Enter a valid http:// or https:// URL'
})

const canSave = computed(() => {
  if (!form.name.trim() || !form.config.url.trim()) return false
  if (!isValidHttpUrl(form.config.url.trim())) return false
  if (isCustom.value && !form.config.template.trim()) return false
  return true
})

const previewBody = computed(() => {
  if (!preview.value) return ''
  if (preview.value.bodyIsJson) return JSON.stringify(preview.value.body, null, 2)
  return String(preview.value.body)
})

function typeLabel(type: string): string {
  return integrationTypeOptions.find((o) => o.value === type)?.label ?? type
}

function measurementLabel(measurement: string): string {
  return measurementOptions.find((o) => o.value === measurement)?.label ?? measurement
}

function headersRecord(): Record<string, string> {
  const out: Record<string, string> = {}
  for (const row of headerRows.value) {
    if (row.key.trim()) out[row.key.trim()] = row.value
  }
  return out
}

function addHeaderRow() {
  headerRows.value.push({ key: '', value: '' })
}

function removeHeaderRow(idx: number) {
  headerRows.value.splice(idx, 1)
}

function insertToken(token: string) {
  const insertText = '${' + token + '}'
  const textarea = templateRef.value
  if (!textarea) {
    form.config.template += insertText
    return
  }
  const start = textarea.selectionStart ?? form.config.template.length
  const end = textarea.selectionEnd ?? form.config.template.length
  form.config.template =
    form.config.template.slice(0, start) + insertText + form.config.template.slice(end)
  nextTick(() => {
    textarea.focus()
    const pos = start + insertText.length
    textarea.setSelectionRange(pos, pos)
  })
}

function doPreview() {
  logDebug('IntegrationsView.doPreview()', form.type, form.measurement)
  preview.value = previewIntegration(
    form.type,
    {
      url: form.config.url,
      method: form.config.method as 'POST' | 'GET',
      headers: headersRecord(),
      template: form.config.template
    },
    form.measurement as Measurement,
    form.name
  )
}

function resetForm() {
  editingId.value = null
  form.name = ''
  form.measurement = MEASUREMENT_GRAVITY
  form.type = INTEGRATION_TYPE_ISPINDEL_FORWARD
  form.config.url = ''
  form.config.method = 'POST'
  form.config.template = ''
  headerRows.value = []
  preview.value = null
}

function editTarget(i: Pick<Integration, keyof Integration>) {
  logDebug('IntegrationsView.editTarget()', i.id)
  global.clearMessages()
  editingId.value = i.id
  form.name = i.name
  form.measurement = i.measurement
  form.type = i.type
  form.config.url = i.config.url
  form.config.method = i.config.method ?? 'POST'
  form.config.template = i.config.template ?? ''
  headerRows.value = Object.entries(i.config.headers ?? {}).map(([key, value]) => ({
    key,
    value: String(value)
  }))
  preview.value = null
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function saveTarget() {
  if (editingId.value) {
    await updateTarget(editingId.value)
  } else {
    await addTarget()
  }
}

async function updateTarget(id: string) {
  logDebug('IntegrationsView.updateTarget()', id)
  global.clearMessages()
  const config: Record<string, unknown> = { url: form.config.url.trim() }
  if (isCustom.value) {
    config.method = form.config.method
    config.headers = headersRecord()
    config.template = form.config.template.trim()
  }
  const updated = await integrationStore.updateIntegration(id, {
    name: form.name.trim(),
    config
  })
  if (updated) {
    global.messageSuccess = 'Integration target saved'
    resetForm()
  } else if (!global.messageError) {
    global.messageError = 'Failed to save integration target'
  }
}

async function addTarget() {
  logDebug('IntegrationsView.addTarget()')
  global.clearMessages()
  const integration = new Integration({
    name: form.name.trim(),
    measurement: form.measurement,
    type: form.type,
    enabled: true,
    config: {
      url: form.config.url.trim(),
      method: form.config.method,
      headers: headersRecord(),
      template: isCustom.value ? form.config.template.trim() : null
    }
  })
  const created = await integrationStore.addIntegration(integration)
  if (created) {
    global.messageSuccess = 'Integration target added'
    resetForm()
  } else if (!global.messageError) {
    // apiClient already set the specific server-side reason (e.g. the SSRF check's
    // "URL resolves to disallowed address ..."); only fall back to a generic
    // message if for some reason it didn't.
    global.messageError = 'Failed to add integration target'
  }
}

async function toggleEnabled(i: Pick<Integration, keyof Integration>) {
  logDebug('IntegrationsView.toggleEnabled()', i.id)
  global.clearMessages()
  const updated = await integrationStore.updateIntegration(i.id, { enabled: !i.enabled })
  if (!updated && !global.messageError) global.messageError = 'Failed to update integration target'
}

async function sendTest(i: Pick<Integration, keyof Integration>) {
  if (!window.confirm(`Send a test payload to "${i.name}"?`)) return
  global.clearMessages()
  const outcome = await integrationStore.testIntegration(i.id)
  if (outcome === 'delivered') global.messageSuccess = 'Test payload delivered'
  else if (outcome && !global.messageError) global.messageError = `Test payload ${outcome}`
}

async function resume(i: Pick<Integration, keyof Integration>) {
  global.clearMessages()
  const updated = await integrationStore.updateIntegration(i.id, { enabled: true })
  if (updated) global.messageSuccess = 'Integration resumed'
}

function deleteTarget(id: string, name: string) {
  logDebug('IntegrationsView.deleteTarget()', id)
  confirmDeleteId.value = id
  confirmDeleteMessage.value = `Do you want to delete integration target "${name}"?`
  document.getElementById('deleteIntegration')?.click()
}

const confirmDeleteCallback = async (result: boolean) => {
  logDebug('IntegrationsView.confirmDeleteCallback()', result)
  if (result && confirmDeleteId.value) {
    global.clearMessages()
    const ok = await integrationStore.deleteIntegration(confirmDeleteId.value)
    if (ok) {
      global.messageSuccess = 'Integration target deleted'
    } else if (!global.messageError) {
      global.messageError = 'Failed to delete integration target'
    }
  }
}

onMounted(() => {
  logDebug('IntegrationsView.onMounted()')
  integrationStore.getIntegrationList()
})
</script>
