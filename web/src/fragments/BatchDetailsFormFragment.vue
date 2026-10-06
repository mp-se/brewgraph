<!--
  Copyright (c) 2024-2026 Magnus Persson
  SPDX-License-Identifier: GPL-3.0-only
  BrewGraph — https://github.com/mp-se/brewgraph

  This file is part of BrewGraph. For open source use it is licensed under
  the GNU General Public License v3.0. For commercial use without source
  disclosure, a separate Commercial License is required.
  See LICENSE for details.
-->

<!--
  Batch overview/metadata fields, extracted from BatchView.vue (structural
  refactor, no behavior change). Renders as bare `col-md-*` grid cells so it
  can be dropped directly inside the parent's existing `.row` alongside the
  fermentation-step/dry-hop/vessel sections that stay in BatchView.
-->
<template>
  <div class="col-md-6">
    <AppTextInput
      v-model="batch.name"
      label="Name"
      :disabled="disabled"
      :help="batch.brewfatherBatchId ? 'Linked to 🔗 Brewfather' : ''"
      required
    >
    </AppTextInput>
  </div>

  <div class="col-md-3">
    <AppSelect
      v-model="batch.gravityDeviceId"
      label="Gravity Device"
      :options="gravityDeviceOptions"
      help=""
      :disabled="disabled"
    ></AppSelect>
    <div v-if="gravityDevice" class="text-caption text-grey-7 q-mt-xs">
      <DeviceColorSwatch :color="gravityDevice.deviceColor" class="q-mr-xs" />
      {{ gravityDevice.deviceColor }}
    </div>
  </div>
  <div class="col-md-3">
    <AppSelect
      v-model="batch.pressureDeviceId"
      label="Pressure Device"
      :options="pressureDeviceOptions"
      help=""
      :disabled="disabled"
    ></AppSelect>
    <div v-if="pressureDevice" class="text-caption text-grey-7 q-mt-xs">
      <DeviceColorSwatch :color="pressureDevice.deviceColor" class="q-mr-xs" />
      {{ pressureDevice.deviceColor }}
    </div>
  </div>
  <div class="col-md-3">
    <AppSelect
      v-model="batch.chamberDeviceId"
      label="Fermentation chamber"
      :options="tempControlDeviceOptions"
      help=""
      :disabled="disabled"
    ></AppSelect>
    <div v-if="chamberDevice" class="text-caption text-grey-7 q-mt-xs">
      <DeviceColorSwatch :color="chamberDevice.deviceColor" class="q-mr-xs" />
      {{ chamberDevice.deviceColor }}
    </div>
  </div>
  <div class="col-md-2" v-if="showControllerActive">
    <AppField label="&nbsp;">
      <div class="app-number-group">
        <p class="text-body1"><span class="app-badge app-badge app-badge--warning">Controller active</span></p>
      </div>
    </AppField>
  </div>
  <div class="col-md-12">
    <AppTextInput
      v-model="batch.description"
      label="Description"
      help=""
      :disabled="disabled"
    >
    </AppTextInput>
  </div>
  <div class="col-md-4">
    <AppTextInput v-model="batch.brewer" label="Brewer" help="" :disabled="disabled">
    </AppTextInput>
  </div>
  <div class="col-md-4">
    <AppInputDate
      v-model="batch.brewDate"
      label="Brew date"
      :disabled="disabled"
    />
  </div>
  <div class="col-md-4">
    <AppSelect
      v-model="batch.style"
      label="Style"
      :options="beerStyleOptions"
      help=""
      :disabled="disabled"
    >
    </AppSelect>
  </div>
  <!-- Yeast selector -->
  <div class="col-md-10">
    <BatchYeastSelectorFragment
      v-model:yeast="batch.yeast"
      v-model:yeast-product-id="batch.yeastProductId"
    />
  </div>
  <div class="col-md-2">
    <AppToggle
      v-model="batch.acceptIngest"
      label="Accepting"
      :disabled="disabled"
    />
  </div>
  <div class="col-md-4">
    <AppInputNumber
      v-model="batch.abv"
      width="8"
      label="Alcohol"
      unit="% ABV"
      min="0"
      max="100"
      step="0.01"
      help=""
      :disabled="disabled"
    >
    </AppInputNumber>
  </div>
  <div class="col-md-4">
    <AppInputNumber
      v-model="batch.ebc"
      nullable
      width="8"
      label="Color"
      unit="EBC"
      min="0"
      max="100"
      step="0.1"
      help=""
      :disabled="disabled"
    >
    </AppInputNumber>
  </div>
  <div class="col-md-4">
    <AppInputNumber
      v-model="batch.ibu"
      nullable
      width="8"
      label="Bitterness"
      unit="IBU"
      min="0"
      max="100"
      step="0.1"
      help=""
      :disabled="disabled"
    >
    </AppInputNumber>
  </div>
  <div class="col-md-4">
    <AppInputNumber
      v-model="ogDisplayValue"
      nullable
      width="8"
      label="Original Gravity"
      :unit="gravityUnit"
      min="0"
      max="40"
      :step="ogStep"
      :disabled="disabled"
    >
    </AppInputNumber>
  </div>
  <div class="col-md-4">
    <AppInputNumber
      v-model="fgDisplayValue"
      nullable
      width="8"
      label="Final Gravity"
      :unit="gravityUnit"
      min="0"
      max="40"
      :step="fgStep"
      :disabled="disabled"
    >
    </AppInputNumber>
  </div>
  <div class="col-md-4">
    <AppInputNumber
      v-model="batch.carbonationVolumes"
      width="8"
      label="Carbonation"
      unit="vol"
      min="0"
      max="10"
      step="0.1"
      help=""
      :disabled="disabled"
    >
    </AppInputNumber>
  </div>
  <div class="col-md-4">
    <AppInputNumber
      v-model="batch.volume"
      width="8"
      label="Volume"
      unit="L"
      min="0"
      max="1000"
      :step="volumeStep"
      help=""
      :disabled="disabled"
    >
    </AppInputNumber>
  </div>
  <div class="col-md-4">
    <AppInputDate
      v-model="batch.packageDate"
      label="Package date"
      :disabled="disabled"
    />
  </div>
  <div class="col-md-4">
    <AppInputNumber
      v-model="batch.conditioningDays"
      width="8"
      label="Conditioning"
      unit="days"
      min="0"
      max="365"
      step="1"
      help=""
      :disabled="disabled"
    >
    </AppInputNumber>
  </div>
  <div v-if="batch.readyDate" class="col-md-4">
    <AppReadonlyInput label="Ready date" :model-value="readyStatus"></AppReadonlyInput>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { global } from '@/modules/pinia'
import DeviceColorSwatch from '@/components/DeviceColorSwatch.vue'
import BatchYeastSelectorFragment from '@/fragments/BatchYeastSelectorFragment.vue'
import { useGravityConversion, stepFor } from '@/modules/useUnitConversion'
import { beerStyleOptions } from '@/modules/constants/beerStyles'

const batch = defineModel('batch', { type: Object, required: true })

const props = defineProps({
  gravityDeviceOptions: { type: Array, default: () => [] },
  pressureDeviceOptions: { type: Array, default: () => [] },
  tempControlDeviceOptions: { type: Array, default: () => [] },
  gravityDevice: { type: Object, default: null },
  pressureDevice: { type: Object, default: null },
  chamberDevice: { type: Object, default: null },
  showControllerActive: { type: Boolean, default: false },
  isArchived: { type: Boolean, default: false }
})

// Archived batches are read-only (see docs/spec-data-model.md §5.7 "Archiving") —
// enforced server-side; this just keeps the form from inviting an edit that would
// be rejected anyway.
const disabled = computed(() => global.disabled || props.isArchived)

const {
  displayValue: ogDisplayValue,
  unit: gravityUnit,
  step: ogStep
} = useGravityConversion(batch, 'og')
const { displayValue: fgDisplayValue, step: fgStep } = useGravityConversion(batch, 'fg')
const volumeStep = stepFor('volume')

// Same formula BatchView.vue applies inline.
const readyStatus = computed(() => {
  const ready = batch.value?.readyDate
  if (!ready) return ''
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const readyDate = new Date(ready)
  if (today >= readyDate) return `${ready} — Ready`
  const daysLeft = Math.ceil((readyDate.getTime() - today.getTime()) / 86400000)
  return `${ready} — ${daysLeft} days left`
})
</script>
