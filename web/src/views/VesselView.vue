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
    <AppPageHeader title="Vessel" />

    <template v-if="vessel != null">
      <form
        @submit.prevent="save"
        class="app-validation"
        :class="{ 'was-validated': showValidation }"
        novalidate
      >
        <div class="row q-col-gutter-sm">
          <div class="col-md-6">
            <AppTextInput
              v-model="vessel.name"
              label="Name"
              help=""
              :disabled="global.disabled"
              required
            />
          </div>
          <div class="col-md-6">
            <AppSelect
              v-model="vessel.batchId"
              :options="batchOptions"
              label="Batch"
              help=""
              :disabled="global.disabled || !isNew()"
            />
          </div>
          <div class="col-md-2">
            <AppInputNumber
              v-model="vessel.vesselNumber"
              width="8"
              label="Vessel #"
              min="1"
              max="9999"
              step="1"
              help=""
              :disabled="global.disabled"
            />
          </div>
          <div class="col-md-4">
            <AppSelect
              v-model="vessel.vesselType"
              :options="[
                { label: 'Keg', value: 'keg' },
                { label: 'Bottle', value: 'bottles' }
              ]"
              label="Type"
              help=""
              :disabled="global.disabled || !isNew()"
            />
          </div>
          <div class="col-md-4">
            <AppSelect
              v-model="vessel.status"
              :options="vesselStatusOptions"
              label="Status"
              help=""
              :disabled="global.disabled"
            />
          </div>
          <div class="col-md-4">
            <AppInputDate
              v-model="vessel.fillDate"
              label="Fill date"
              :disabled="global.disabled"
            />
          </div>
          <div class="col-md-4">
            <AppInputNumber
              v-model="totalVolumeDisplay"
              width="5"
              label="Total volume"
              :unit="volumeUnit"
              min="0"
              :max="volumeMaxL(200)"
              :step="volumeStep"
              help=""
              :disabled="global.disabled"
            />
          </div>
          <div class="col-md-4">
            <AppInputNumber
              v-model="volumeRemainingDisplay"
              width="5"
              label="Volume remaining"
              :unit="volumeUnit"
              min="0"
              :max="volumeMaxL(200)"
              :step="volumeStep"
              help=""
              :disabled="global.disabled"
            />
          </div>
          <div class="col-md-4">
            <AppTextInput
              v-model="vessel.location"
              label="Location"
              help=""
              :disabled="global.disabled"
            />
          </div>

          <template v-if="vessel.vesselType === VESSEL_TYPE_BOTTLE">
            <div class="col-md-4">
              <AppInputNumber
                v-model="bottleVolumeDisplay"
                width="5"
                label="Bottle size"
                :unit="volumeUnit"
                min="0"
                :max="volumeMaxL(3)"
                :step="volumeStep"
                help=""
                :disabled="global.disabled"
              />
            </div>
            <div class="col-md-4">
              <AppInputNumber
                v-model="vessel.bottleCount"
                width="5"
                label="Bottle count"
                unit=""
                min="0"
                max="1000"
                step="1"
                help=""
                :disabled="global.disabled"
              />
            </div>
            <div class="col-md-4">
              <AppInputNumber
                v-model="vessel.bottlesRemaining"
                width="5"
                label="Bottles remaining"
                unit=""
                min="0"
                max="1000"
                step="1"
                help=""
                :disabled="global.disabled"
              />
            </div>
          </template>

          <div class="col-md-12">
            <AppTextInput v-model="vessel.notes" label="Notes" help="" :disabled="global.disabled" />
          </div>
        </div>

        <!-- Pour recording — only for existing kegs currently on tap -->
        <template v-if="!isNew() && vessel.vesselType === VESSEL_TYPE_KEG && vessel.isOnTap">
          <div class="row q-col-gutter-sm q-mt-sm">
            <div class="col-md-12"><hr /></div>
            <div class="col-md-12"><p class="text-subtitle2">Record Pour</p></div>
            <div class="col-md-4">
              <AppInputNumber
                v-model="pourDisplayAmount"
                width="5"
                label="Pour amount"
                :unit="pourUnit"
                min="0.1"
                :max="pourMax"
                :step="pourStep"
                help=""
                :disabled="global.disabled"
              />
            </div>
            <div class="col-md-12">
              <app-button
                type="button"
                variant="positive"
                :disabled="global.disabled || isRecordingPour"
                :aria-busy="isRecordingPour"
                @click="recordPour()"
              >
                <span
                  v-if="isRecordingPour"
                  class="app-spinner app-spinner--small"
                  role="status"
                  aria-hidden="true"
                ></span>
                Record Pour
              </app-button>
            </div>
          </div>
        </template>

        <template v-if="!isNew() && vessel.vesselType === VESSEL_TYPE_BOTTLE && vessel.isOnTap">
          <div class="row q-col-gutter-sm q-mt-sm">
            <div class="col-md-12"><hr /></div>
            <div class="col-md-12"><p class="text-subtitle2">Record Pour</p></div>
            <div class="col-md-4">
              <AppInputNumber
                v-model="bottleConsumed"
                width="5"
                label="Bottles consumed"
                unit=""
                min="1"
                max="500"
                step="1"
                help=""
                :disabled="global.disabled"
              />
            </div>
            <div class="col-md-12">
              <app-button
                type="button"
                variant="positive"
                :disabled="global.disabled || isRecordingBottlePour"
                :aria-busy="isRecordingBottlePour"
                @click="recordBottlePour()"
              >
                <span
                  v-if="isRecordingBottlePour"
                  class="app-spinner app-spinner--small"
                  role="status"
                  aria-hidden="true"
                ></span>
                Record Pour
              </app-button>
            </div>
          </div>
        </template>

        <!-- Device Setup — pair a pressure/chamber device to this vessel, e.g. -->
        <!-- while it sits in cold storage with no active batch. -->
        <template v-if="!isNew()">
          <div class="row q-col-gutter-sm q-mt-sm">
            <div class="col-md-12"><hr /></div>
            <div class="col-md-12"><p class="text-subtitle2">Device Setup</p></div>
            <div class="col-md-6">
              <AppSelect
                v-model="selectedPressureDeviceId"
                label="Pressure Device"
                :options="pressureDeviceOptions"
                help=""
                :disabled="global.disabled"
              ></AppSelect>
              <div v-if="selectedPressureDevice" class="text-caption text-grey-7 q-mt-xs">
                <DeviceColorSwatch :color="selectedPressureDevice.deviceColor" class="q-mr-xs" />
                {{ selectedPressureDevice.deviceColor }}
              </div>
              <DeviceSetupFragment
                v-if="selectedPressureDevice"
                :key="selectedPressureDevice.id"
                :device-type="selectedPressureDevice.deviceType"
                :token="selectedPressureDevice.token"
                :has-readings="!!selectedPressureDevice.lastSeen"
              />
            </div>
            <div class="col-md-6">
              <AppSelect
                v-model="selectedChamberDeviceId"
                label="Chamber Device"
                :options="tempControlDeviceOptions"
                help=""
                :disabled="global.disabled"
              ></AppSelect>
              <div v-if="selectedChamberDevice" class="text-caption text-grey-7 q-mt-xs">
                <DeviceColorSwatch :color="selectedChamberDevice.deviceColor" class="q-mr-xs" />
                {{ selectedChamberDevice.deviceColor }}
              </div>
              <DeviceSetupFragment
                v-if="selectedChamberDevice"
                :key="selectedChamberDevice.id"
                :device-type="selectedChamberDevice.deviceType"
                :token="selectedChamberDevice.token"
                :has-readings="!!selectedChamberDevice.lastSeen"
              />
            </div>
          </div>
        </template>

        <div class="row q-col-gutter-sm q-mt-sm">
          <div class="col-md-12"><hr /></div>
          <div class="col-md-12 app-button-row">
            <app-button
              type="submit"
              variant="primary" class="app-width-2"
              :disabled="global.disabled || isSaving || !vesselChanged() || !vessel.name"
              :aria-busy="isSaving"
            >
              <span
                v-if="isSaving"
                class="app-spinner app-spinner--small"
                role="status"
                aria-hidden="true"
              ></span>
              <q-icon name="save" /> Save</app-button>
            <router-link :to="{ name: 'vessel-list' }">
              <app-button type="button" variant="secondary" class="app-width-2">
                <q-icon name="cancel" /> Cancel
              </app-button>
            </router-link>
          </div>
        </div>
      </form>
    </template>

    <template v-else>
      <div class="row q-col-gutter-sm">
        <div class="col-md-12">
          <p class="text-subtitle1">Loading...</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { global, vesselStore, batchStore, deviceStore, pourStore } from '@/modules/pinia'
import { storeToRefs } from 'pinia'
import { logDebug } from '@/ui'
import router from '@/modules/router'
import {
  StorageVessel,
  vesselStatusOptions,
  VESSEL_TYPE_KEG,
  VESSEL_TYPE_BOTTLE
} from '@/modules/classes'
import AppPageHeader from '@/components/AppPageHeader.vue'
import DeviceColorSwatch from '@/components/DeviceColorSwatch.vue'
import DeviceSetupFragment from '@/fragments/DeviceSetupFragment.vue'
import { useDeviceOptions } from '@/modules/useDeviceOptions'
import {
  useVolumeConversion,
  usePourVolumeConversion,
  volumeMaxL
} from '@/modules/useUnitConversion'

const vessel = ref(null)
const vesselSaved = ref(null)
const showValidation = ref(false)
const isSaving = ref(false)
const isRecordingPour = ref(false)
const isRecordingBottlePour = ref(false)
const pourAmount = ref(0.5)
const bottleConsumed = ref(1)
const route = useRoute()
const { updatedVesselData } = storeToRefs(global)

const { pressureDeviceOptions, tempControlDeviceOptions, updateDeviceOptions } = useDeviceOptions()
const selectedPressureDeviceId = ref(null)
const selectedChamberDeviceId = ref(null)
const savedPressureDeviceId = ref(null)
const savedChamberDeviceId = ref(null)
const selectedPressureDevice = computed(() =>
  deviceStore.devices.find((device) => device.id === selectedPressureDeviceId.value) ?? null
)
const selectedChamberDevice = computed(() =>
  deviceStore.devices.find((device) => device.id === selectedChamberDeviceId.value) ?? null
)

function loadDeviceAssignments(vesselId) {
  const pressureDev = deviceStore.devices.find(
    (d) => d.vesselId === vesselId && d.deviceType === 'pressuremon'
  )
  const chamberDev = deviceStore.devices.find(
    (d) => d.vesselId === vesselId && d.deviceType === 'chamber_controller'
  )
  selectedPressureDeviceId.value = pressureDev?.id ?? null
  selectedChamberDeviceId.value = chamberDev?.id ?? null
  savedPressureDeviceId.value = selectedPressureDeviceId.value
  savedChamberDeviceId.value = selectedChamberDeviceId.value
}

async function syncDeviceAssignments(vesselId) {
  const roles = [
    { newId: selectedPressureDeviceId.value, oldId: savedPressureDeviceId.value },
    { newId: selectedChamberDeviceId.value, oldId: savedChamberDeviceId.value }
  ]
  for (const { newId, oldId } of roles) {
    if (newId === oldId) continue
    if (oldId) {
      const oldDev = deviceStore.devices.find((d) => d.id === oldId)
      if (oldDev) {
        oldDev.vesselId = null
        await deviceStore.updateDevice(oldDev)
      }
    }
    if (newId) {
      const newDev = deviceStore.devices.find((d) => d.id === newId)
      if (newDev) {
        newDev.vesselId = vesselId
        await deviceStore.updateDevice(newDev)
      }
    }
  }
  savedPressureDeviceId.value = selectedPressureDeviceId.value
  savedChamberDeviceId.value = selectedChamberDeviceId.value
}

watch(updatedVesselData, () => {
  if (!vessel.value?.id || isNew()) return
  const updated = vesselStore.vesselList.find((v) => v.id === vessel.value.id)
  if (updated) vessel.value = updated
})

const {
  displayValue: totalVolumeDisplay,
  unit: volumeUnit,
  step: volumeStep
} = useVolumeConversion(vessel, 'totalVolume')
const { displayValue: volumeRemainingDisplay } = useVolumeConversion(vessel, 'volumeRemaining')
const { displayValue: bottleVolumeDisplay } = useVolumeConversion(vessel, 'bottleVolume')
const {
  displayValue: pourDisplayAmount,
  unit: pourUnit,
  step: pourStep,
  max: pourMax
} = usePourVolumeConversion(pourAmount)

const batchOptions = computed(() => {
  const opts = [{ label: '— no batch (empty vessel) —', value: '' }]
  // Archived batches are read-only server-side (StorageVesselService rejects linking a
  // new vessel to one, 409), so offering them here would be a dead-end selection.
  batchStore.batchList
    .filter((b) => b.status !== 'archived')
    .forEach((b) => {
      opts.push({ label: b.name, value: b.id })
    })
  return opts
})

watch(
  () => vessel.value?.batchId,
  (newBatchId) => {
    if (!vessel.value) return
    // A new vessel is `clean` (empty) until it holds a batch; follow the batch choice unless the
    // user has already picked another status.
    if (isNew()) {
      if (newBatchId && vessel.value.status === 'clean') vessel.value.status = 'filled'
      else if (!newBatchId && vessel.value.status === 'filled') vessel.value.status = 'clean'
    }
    if (!newBatchId) return
    if (!vessel.value.name) {
      const batch = batchStore.batchList.find((b) => b.id === newBatchId)
      if (batch) vessel.value.name = batch.name
    }
  }
)

function vesselChanged() {
  if (vessel.value == null || vesselSaved.value == null) {
    global.vesselChanged = false
    return false
  }
  const assignmentsChanged =
    selectedPressureDeviceId.value !== savedPressureDeviceId.value ||
    selectedChamberDeviceId.value !== savedChamberDeviceId.value
  global.vesselChanged = assignmentsChanged || !StorageVessel.compare(vessel.value, vesselSaved.value)
  return global.vesselChanged
}

function isNew() {
  return route.params.id === 'new'
}

function getVesselIdFromRoute() {
  const raw = route.params.id
  if (raw == null) return null
  const id = String(raw).trim()
  if (!id || id === 'undefined' || id === 'null' || id === 'new') return null
  return id
}

onMounted(async () => {
  logDebug('VesselView.onMounted()')
  showValidation.value = true
  updateDeviceOptions()
  await batchStore.getBatchList()

  if (isNew()) {
    const today = new Date().toISOString().split('T')[0]
    const queryBatchId = Array.isArray(route.query.batchId)
      ? route.query.batchId[0]
      : route.query.batchId
    const defaultBatch = batchStore.batchList.find((b) => b.id === queryBatchId)
    vessel.value = new StorageVessel({
      batchId: queryBatchId || '',
      name: defaultBatch?.name ?? '',
      vesselType: 'keg',
      fillDate: today,
      status: queryBatchId ? 'filled' : 'clean',
      totalVolume: 19.0,
      volumeRemaining: 19.0
    })
    // Treat the defaults shown on first render as the baseline. The old empty
    // baseline made a new vessel look edited before the user touched anything.
    vesselSaved.value = StorageVessel.fromJson(vessel.value.toJson())
  } else {
    const vesselId = getVesselIdFromRoute()
    if (!vesselId) {
      global.messageError = 'Invalid vessel id'
      vessel.value = new StorageVessel({})
      return
    }

    const fromStore = vesselStore.vesselList.find((v) => v.id === vesselId)
    const result = fromStore ?? (await vesselStore.getVessel(vesselId))
    if (result) {
      vessel.value = result
      vesselSaved.value = StorageVessel.fromJson(result.toJson())
      loadDeviceAssignments(result.id)
    } else {
      global.messageError = 'Failed to load vessel'
    }
  }
})

const save = async () => {
  logDebug('VesselView.save()')
  global.clearMessages()

  isSaving.value = true
  try {
    if (isNew()) {
      const result = await vesselStore.addVessel(vessel.value)
      if (result) {
        vessel.value = result
        await syncDeviceAssignments(vessel.value.id)
        vesselSaved.value = StorageVessel.fromJson(vessel.value.toJson())
        global.vesselChanged = false
        router.push({ name: 'vessel', params: { id: vessel.value.id } })
      } else {
        global.messageError = 'Failed to add vessel'
      }
    } else {
      const result = await vesselStore.updateVessel(vessel.value)
      if (result) {
        vessel.value = result
        await syncDeviceAssignments(vessel.value.id)
        vesselSaved.value = StorageVessel.fromJson(vessel.value.toJson())
        global.vesselChanged = false
        global.messageSuccess = 'Vessel saved'
      } else {
        global.messageError = 'Failed to save vessel'
      }
    }
  } finally {
    isSaving.value = false
  }
}

async function recordPour() {
  logDebug('VesselView.recordPour()', vessel.value?.id, pourAmount.value)
  isRecordingPour.value = true
  try {
    const result = await pourStore.recordPour(vessel.value.id, pourAmount.value)
    if (result) {
      global.messageSuccess = 'Pour recorded'
    } else {
      global.messageError = 'Failed to record pour'
    }
  } finally {
    isRecordingPour.value = false
  }
}

async function recordBottlePour() {
  logDebug('VesselView.recordBottlePour()', vessel.value?.id, bottleConsumed.value)
  isRecordingBottlePour.value = true
  try {
    const result = await pourStore.recordBottlePour(vessel.value.id, bottleConsumed.value)
    if (result) {
      global.messageSuccess = 'Pour recorded'
    } else {
      global.messageError = 'Failed to record pour'
    }
  } finally {
    isRecordingBottlePour.value = false
  }
}

defineExpose({
  vessel,
  selectedPressureDeviceId,
  selectedChamberDeviceId,
  loadDeviceAssignments,
  syncDeviceAssignments,
  isNew,
  isSaving,
  save
})
</script>
