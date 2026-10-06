<template>
  <div class="device-classification-fields">
    <div class="device-form-section">
      <div class="device-form-toggle">
        <label class="app-field-label" for="chip-family">Chip Family</label>
        <QBtnToggle
          id="chip-family"
          :model-value="device.chipFamily"
          @update:model-value="$emit('update:chipFamily', $event)"
          :options="chipFamilyOptions"
          :disable="disabled || device.isIspindel"
          class="device-form-toggle__buttons"
          no-caps
          unelevated
          toggle-color="primary"
          toggle-text-color="white"
          aria-label="Chip Family"
        />
      </div>
    </div>

    <div class="device-form-section">
      <div class="device-form-toggle">
        <label class="app-field-label" for="device-type">Device Type</label>
        <QBtnToggle
          id="device-type"
          :model-value="device.deviceType"
          @update:model-value="$emit('update:deviceType', $event)"
          :options="deviceTypeOptions"
          :disable="disabled"
          class="device-form-toggle__buttons"
          no-caps
          unelevated
          toggle-color="primary"
          toggle-text-color="white"
          aria-label="Device Type"
        />
      </div>
    </div>

    <div class="device-form-section">
      <div class="device-form-toggle device-form-toggle--color">
        <label class="app-field-label" for="device-color">Device Color</label>
        <QBtnToggle
          id="device-color"
          :model-value="device.deviceColor"
          @update:model-value="$emit('update:deviceColor', $event)"
          :options="deviceColorOptions"
          :disable="disabled"
          class="device-form-toggle__buttons device-color-toggle__buttons"
          no-caps
          unelevated
          toggle-color="primary"
          toggle-text-color="white"
          aria-label="Device Color"
        />
        <p class="device-form-toggle__help">Physical color used to identify this device.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { QBtnToggle } from 'quasar'

interface DeviceClassification {
  chipFamily: string
  deviceType: string
  deviceColor: string
  isIspindel: boolean
}

type ToggleOption = {
  label: string
  value: string | null
  icon?: string
  slot?: string
  attrs?: Record<string, unknown>
  [key: string]: unknown
}

interface Props {
  device: DeviceClassification
  disabled?: boolean
  chipFamilyOptions: ToggleOption[]
  deviceTypeOptions: ToggleOption[]
  deviceColorOptions: ToggleOption[]
}

withDefaults(defineProps<Props>(), { disabled: false })

defineEmits<{
  'update:chipFamily': [value: string]
  'update:deviceType': [value: string]
  'update:deviceColor': [value: string]
}>()
</script>

<style scoped>
.device-classification-fields {
  min-width: 0;
}

.device-form-section {
  margin-top: 4px;
}

.device-form-toggle {
  display: grid;
  min-width: 0;
  gap: 8px;
}

.device-form-toggle__buttons {
  display: flex;
  max-width: 100%;
  flex-wrap: wrap;
  gap: 4px;
}

.device-form-toggle__buttons :deep(.q-btn) {
  min-height: 36px;
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.device-form-toggle__buttons :deep(.q-btn[aria-pressed='true']) {
  border-color: var(--brand);
  background: var(--brand);
  color: var(--on-primary);
}

.device-color-toggle__buttons :deep(.q-btn::before) {
  width: 0.7rem;
  height: 0.7rem;
  margin-right: 6px;
  border: 1px solid var(--app-swatch-outline);
  border-radius: 50%;
  content: '';
}

.device-color-toggle__buttons :deep(.q-btn:nth-child(1)::before) { background: black; }
.device-color-toggle__buttons :deep(.q-btn:nth-child(2)::before) { background: red; }
.device-color-toggle__buttons :deep(.q-btn:nth-child(3)::before) { background: orange; }
.device-color-toggle__buttons :deep(.q-btn:nth-child(4)::before) { background: yellow; }
.device-color-toggle__buttons :deep(.q-btn:nth-child(5)::before) { background: green; }
.device-color-toggle__buttons :deep(.q-btn:nth-child(6)::before) { background: blue; }
.device-color-toggle__buttons :deep(.q-btn:nth-child(7)::before) { background: purple; }
.device-color-toggle__buttons :deep(.q-btn:nth-child(8)::before) { background: pink; }
.device-color-toggle__buttons :deep(.q-btn:nth-child(9)::before) { background: white; }

.device-form-toggle__help {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.875rem;
}

@media (max-width: 599px) {
  .device-form-toggle__buttons {
    width: 100%;
  }
}
</style>
