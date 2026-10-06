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
  <dialog id="spinner" class="loading">
    <div class="app-page text-center q-py-md">
      <div v-if="!loadingError">
        <div class="app-spinner q-mb-md" role="status" style="width: 3rem; height: 3rem">
          <span class="sr-only">Loading...</span>
        </div>
        <p class="q-mb-sm text-weight-medium">{{ loadingStep }}</p>
        <div class="app-progress" style="height: 6px">
          <div
            class="app-progress__bar"
            role="progressbar"
            :style="{ width: (loadingStepIndex / loadingTotalSteps) * 100 + '%' }"
          ></div>
        </div>
        <p class="text-grey-7 q-mt-xs" style="font-size: 0.75rem">
          Step {{ loadingStepIndex }} of {{ loadingTotalSteps }}
        </p>
      </div>
      <div v-else>
        <q-icon name="warning" class="text-negative" size="2.5rem" />
        <p class="text-weight-bold text-negative q-mt-sm q-mb-xs">Startup failed</p>
        <p class="q-mb-md" style="font-size: 0.85rem">{{ loadingError }}</p>
        <app-button variant="outline-secondary" dense @click="hideSpinner()">Dismiss</app-button>
      </div>
    </div>
  </dialog>

  <div v-if="!global.initialized" class="app-page text-center">
    <AppMessage
      message="Initializing BrewGraph interface"
      class="text-h5"
      :dismissable="false"
      alert="info"
    ></AppMessage>
  </div>

  <AppMenuBar v-if="showChrome" :disabled="global.disabled" brand="BrewGraph" />

  <div v-if="showChrome" class="app-page">
    <div><p></p></div>
    <AppMessage v-if="global.isError" :close="close" :dismissable="true" :message="global.messageError" alert="danger" />
    <AppMessage v-if="global.isWarning" :close="close" :dismissable="true" :message="global.messageWarning" alert="warning" />
    <AppMessage v-if="global.isSuccess" :close="close" :dismissable="true" :message="global.messageSuccess" alert="success" />
    <AppMessage v-if="global.isInfo" :close="close" :dismissable="true" :message="global.messageInfo" alert="info" />
  </div>

  <router-view v-if="global.initialized" />
  <AppFooter v-if="showChrome" :text="'(c) 2024-2026 Magnus Persson, ui version ' + global.uiVersion + ' (' + global.uiBuild + ')'" />
</template>

<script setup>
import AppMenuBar from '@/components/AppMenuBar.vue'
import AppFooter from '@/components/AppFooter.vue'
import { onMounted, onUnmounted, watch, ref, computed } from 'vue'
import {
  global,
  preferences,
  config,
  batchStore,
  deviceStore,
  tapStore,
  vesselStore,
  yeastStrainStore,
  saveConfigState
} from '@/modules/pinia'
import { logDebug } from '@/ui'
import { useEventStream } from '@/modules/useEventStream'

const eventStream = useEventStream()
const loadingStep = ref('Starting up…')
const loadingStepIndex = ref(0)
const loadingTotalSteps = 5
const loadingError = ref('')

const showChrome = computed(() => global.initialized)

const disabled = computed(() => global.disabled)

const close = (alert) => {
  logDebug('App.close()', alert)

  if (alert == 'danger') global.messageError = ''
  else if (alert == 'warning') global.messageWarning = ''
  else if (alert == 'success') global.messageSuccess = ''
  else if (alert == 'info') global.messageInfo = ''
}

watch(disabled, () => {
  logDebug('App.watch(disabled)')

  if (global.disabled) document.body.style.cursor = 'wait'
  else document.body.style.cursor = 'default'
})

function connect() {
  eventStream.connect()
}

onUnmounted(() => {
  eventStream.disconnect()
})

onMounted(async () => {
  logDebug('App.onMounted()')

  logDebug(
    'App.onMounted()',
    preferences.batchListFilterDevice,
    preferences.batchListFilterActive,
    preferences.batchListFilterData,
    preferences.deviceListFilterDeviceType,
    preferences.showChamberTemps,
    preferences.showKegmonTaps
  )

  // Load from API's
  if (!global.initialized) {
    logDebug('App.onMounted()', 'Initializing')
    showSpinner()

    const steps = [
      {
        label: 'Loading configuration…',
        run: async () => {
          const ok = await config.load()
          if (ok) saveConfigState()
          return ok
        }
      },
      { label: 'Loading devices…', run: () => deviceStore.getDeviceList() },
      { label: 'Loading batches…', run: () => batchStore.getBatchList() },
      { label: 'Loading taps…', run: () => tapStore.getTapList() },
      { label: 'Loading vessels…', run: () => vesselStore.getVesselList() },
      { label: 'Loading yeast strains…', run: () => yeastStrainStore.load() }
    ]

    for (const [i, step] of steps.entries()) {
      loadingStep.value = step.label
      loadingStepIndex.value = i + 1
      const ok = await step.run()
      logDebug('App.onMounted()', step.label, ok)
      if (!ok) {
        loadingError.value = `${step.label.replace('…', '')} failed. Check your connection and API key, then reload the page.`
        return
      }
    }

    global.initialized = true
    hideSpinner()
    connect()
  } else {
    connect()
  }
})

function showSpinner() {
  logDebug('App.showSpinner()')
  document.querySelector('#spinner').showModal()
}

function hideSpinner() {
  logDebug('App.hideSpinner()')
  document.querySelector('#spinner').close()
}
</script>

<style>
.loading {
  position: fixed;
  width: 320px;
  padding: 20px;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  border: 0;
  border-radius: 8px;
}

dialog::backdrop {
  background-color: black;
  opacity: 60%;
}
</style>
