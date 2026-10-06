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
    <p></p>
    <p class="text-h6">Fermentation Control</p>
    <hr />
    <AppMessage></AppMessage>

    <div class="row" v-if="batch">
      <div class="col-md-6">
        <p class="text-weight-bold q-mb-xs">Batch: {{ batch.name }}</p>
        <p class="text-grey-7 q-mb-none" v-if="device">
          Controller: <DeviceColorSwatch :color="device.deviceColor" class="q-mx-xs" />
          {{ device.name }} &mdash; {{ device.deviceType
          }}<span v-if="device.mdns"> &mdash; {{ device.mdns }}.local</span>
        </p>
        <p class="text-grey-7 q-mb-none" v-else>No fermentation chamber selected for this batch.</p>
      </div>
      <div class="col-md-6 text-right">
        <router-link :to="{ name: 'batch', params: { id: batch.id } }">
          <app-button type="button" variant="secondary" dense>Back to Batch</app-button>
        </router-link>
      </div>
    </div>

    <hr />

    <div v-if="activeSteps.length > 0">
      <p class="text-weight-bold">
        Active Fermentation Steps
        <span class="app-badge app-badge--positive q-ml-sm">{{ activeSteps.length }} steps</span>
        <span class="app-badge q-ml-sm" :class="chamberControlActive ? 'app-badge--positive' : 'app-badge--secondary'">
          Chamber control: {{ chamberControlActive ? 'ON' : 'OFF' }}
        </span>
      </p>
      <p class="text-warning text-caption" v-if="!chamberControlActive">
        Steps are saved but chamber control is off — the controller holds its own setting until
        you activate.
      </p>
      <FermentationStepFragment
        :fermentationSteps="activeSteps"
        :tempUnit="config.tempUnit"
        :editable="false"
      />
      <app-button
        type="button"
        variant="primary" dense class="q-mt-sm"
        v-if="!chamberControlActive"
        @click="activateExistingSteps"
      >
        Activate Chamber Control
      </app-button>
      <app-button
        type="button"
        variant="secondary" dense class="q-mt-sm"
        v-if="chamberControlActive"
        @click="confirmDeactivate"
      >
        Deactivate Chamber Control
      </app-button>
      <app-button
        type="button"
        variant="outline-primary" dense class="q-mt-sm q-ml-sm"
        v-if="chamberControlActive"
        @click="confirmAdvance"
      >
        Advance to Next Step
      </app-button>
      <app-button type="button" variant="negative" dense class="q-mt-sm q-ml-sm" @click="confirmClear">
        Clear Active Steps
      </app-button>
      <hr />
    </div>

    <p v-if="activeSteps.length === 0" class="text-grey-7">
      No fermentation steps defined for this batch. Add them on the batch page first.
    </p>

    <AppConfirmDialog
      :callback="deactivateCallback"
      message="Deactivate chamber control? Re-activating later recomputes all step dates from that day, so this is not silently resumable at the same point."
      id="confirmDeactivate"
      title="Deactivate Chamber Control"
    />

    <AppConfirmDialog
      :callback="advanceCallback"
      message="End the current step early and move to the next one?"
      id="confirmAdvance"
      title="Advance to Next Step"
    />

    <AppConfirmDialog
      :callback="clearStepsCallback"
      message="Are you sure you want to delete all active fermentation steps?"
      id="confirmClearSteps"
      title="Clear Steps"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { global, deviceStore, batchStore, config } from '@/modules/pinia'
import { logDebug } from '@/ui'
import FermentationStepFragment from '@/fragments/FermentationStepFragment.vue'
import DeviceColorSwatch from '@/components/DeviceColorSwatch.vue'
import router from '@/modules/router'

const batch = ref(null)
const device = ref(null)
const activeSteps = ref([])
const chamberControlActive = ref(false)

onMounted(async () => {
  const batchId = router.currentRoute.value.params.id
  logDebug('BatchFermentationControlView.onMounted()', batchId)

  const batchResult = await batchStore.getBatch(batchId)
  if (!batchResult) {
    global.messageError = 'Failed to load batch'
    return
  }
  batch.value = batchResult
  chamberControlActive.value = batchResult.chamberControlActive === true

  const steps = await deviceStore.getFermentationSteps(batchId)
  if (steps) activeSteps.value = steps

  // The controller is whichever device the steps were created against. `Batch` has no
  // chamber field in this app — `fermentationChamber` exists only in the backup format,
  // inherited from BrewLogger, so reading it here always resolved to null.
  const deviceId = activeSteps.value.find((s) => s.deviceId)?.deviceId
  if (deviceId) {
    const deviceResult = await deviceStore.getDevice(deviceId)
    if (deviceResult) device.value = deviceResult
  }
})

async function activateExistingSteps() {
  logDebug('BatchFermentationControlView.activateExistingSteps()')
  const activated = await deviceStore.activateFermentationSteps(batch.value.id)
  if (activated) {
    activeSteps.value = activated
    chamberControlActive.value = true
    global.messageSuccess = 'Chamber control activated'
  } else {
    global.messageError = 'Steps saved, but chamber control could not be activated'
    activeSteps.value = (await deviceStore.getFermentationSteps(batch.value.id)) ?? []
  }
}

function confirmDeactivate() {
  document.getElementById('confirmDeactivate').click()
}

async function deactivateCallback() {
  logDebug('BatchFermentationControlView.deactivateCallback()')
  const success = await deviceStore.deactivateFermentationSteps(batch.value.id)
  if (success) {
    chamberControlActive.value = false
    global.messageSuccess = 'Chamber control deactivated'
  } else {
    global.messageError = 'Failed to deactivate chamber control'
  }
}

function confirmAdvance() {
  document.getElementById('confirmAdvance').click()
}

async function advanceCallback() {
  logDebug('BatchFermentationControlView.advanceCallback()')
  const advanced = await deviceStore.advanceFermentationStep(batch.value.id)
  if (advanced) {
    activeSteps.value = (await deviceStore.getFermentationSteps(batch.value.id)) ?? []
    global.messageSuccess = 'Advanced to next step'
  } else {
    global.messageError = 'Failed to advance to the next step'
  }
}

function confirmClear() {
  document.getElementById('confirmClearSteps').click()
}

async function clearStepsCallback() {
  logDebug('BatchFermentationControlView.clearStepsCallback()')
  const success = await deviceStore.deleteFermentationSteps(batch.value.id)
  if (success) {
    global.messageSuccess = 'Active fermentation steps cleared'
    activeSteps.value = []
  } else {
    global.messageError = 'Failed to clear fermentation steps'
  }
}
</script>
