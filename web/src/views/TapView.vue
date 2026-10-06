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
    <AppPageHeader title="Tap" />

    <template v-if="tap != null">
      <form
        @submit.prevent="save"
        class="app-validation"
        :class="{ 'was-validated': showValidation }"
        novalidate
      >
        <div class="row q-col-gutter-sm">
          <div class="col-md-4">
            <AppInputNumber
              v-model="tap.tapNumber"
              width="4"
              label="Tap #"
              min="1"
              max="99"
              step="1"
              help=""
              :disabled="global.disabled"
              required
            />
          </div>
          <div class="col-md-4">
            <AppInputNumber
              v-model="glassSizeMl"
              width="4"
              label="Glass Size"
              unit="ml"
              min="1"
              max="10000"
              step="1"
              help=""
              :disabled="global.disabled"
            />
          </div>
          <div class="col-md-4">
            <AppTextInput
              v-model="tap.name"
              label="Name"
              help=""
              :disabled="global.disabled"
              required
            />
          </div>
          <div class="col-md-12">
            <AppTextInput
              v-model="tap.location"
              label="Location"
              help=""
              :disabled="global.disabled"
            />
          </div>
          <div class="col-md-12">
            <AppTextInput v-model="tap.notes" label="Notes" help="" :disabled="global.disabled" />
          </div>
          <div class="col-md-12">
            <AppSelect
              v-model="selectedVesselId"
              :options="vesselOptions"
              label="Vessel on tap"
              help=""
              :disabled="global.disabled || isNew()"
            />
          </div>
        </div>

        <div class="row q-col-gutter-sm tap-action-toolbar">
          <div class="col-md-12">
            <hr />
          </div>
          <div class="col-md-12 app-button-row">
            <app-button
              type="submit"
              variant="primary" class="app-width-2"
              :disabled="global.disabled || isSaving || !tapChanged() || !tap.name"
              :aria-busy="isSaving"
            >
              <span
                v-if="isSaving"
                class="app-spinner app-spinner--small"
                role="status"
                aria-hidden="true"
              ></span>
              <q-icon name="save" /> Save</app-button>
            <router-link :to="{ name: 'tap-list' }">
              <app-button type="button" variant="secondary" class="app-width-2">
                <q-icon name="cancel" /> Cancel
              </app-button>
            </router-link>
            <app-button
              v-if="!isNew() && tap?.token"
              type="button"
              variant="outline-secondary" class="app-width-2"
              :disabled="global.disabled"
              title="Regenerate API token. This immediately rotates the token and invalidates the previous device configuration."
              aria-label="Regenerate API token. This immediately rotates the token and invalidates the previous device configuration."
              @click="regenToken"
            >
              <q-icon name="refresh" /> Regenerate token
            </app-button>
          </div>
        </div>
      </form>

      <div class="row q-col-gutter-sm q-mt-sm" v-if="tap && tap.token">
        <DeviceSetupFragment
          device-type="kegmon"
          :token="tap.token"
          :has-readings="false"
        />
      </div>
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

<script setup lang="ts">
import { onMounted, ref, computed, watch, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { global, tapStore, vesselStore } from '@/modules/pinia'
import { storeToRefs } from 'pinia'
import { logDebug } from '@/ui'
import router from '@/modules/router'
import {
  Tap,
  VESSEL_STATUS_CONDITIONING,
  VESSEL_STATUS_SERVING,
  VESSEL_TYPE_KEG
} from '@/modules/classes'
import { useGlassSizeConversion } from '@/modules/useUnitConversion'
import AppPageHeader from '@/components/AppPageHeader.vue'
import DeviceSetupFragment from '@/fragments/DeviceSetupFragment.vue'

const tap = ref<Tap | null>(null)
const tapSaved = ref<Tap | null>(null)
const { displayValue: glassSizeMl } = useGlassSizeConversion(
  tap as unknown as Ref<Record<string, number | null> | null>,
  'glassSize'
)
const showValidation = ref(false)
const isSaving = ref(false)
const selectedVesselId = ref('')
const originalVesselId = ref('')
const route = useRoute()

function tapChanged() {
  if (tap.value == null || tapSaved.value == null) {
    global.tapChanged = false
    return false
  }
  global.tapChanged =
    !Tap.compare(tap.value as Tap, tapSaved.value as Tap) || selectedVesselId.value !== originalVesselId.value
  return global.tapChanged
}

const vesselOptions = computed(() => {
  const opts = [{ label: '— none —', value: '' }]
  vesselStore.vesselList.forEach((v) => {
    const assignableStatus =
      v.status === VESSEL_STATUS_CONDITIONING || v.status === VESSEL_STATUS_SERVING
    const isCurrent = tap.value?.id && v.tapId === tap.value.id
    if (
      v.vesselType === VESSEL_TYPE_KEG &&
      (assignableStatus || isCurrent) &&
      (!v.tapId || isCurrent)
    ) {
      opts.push({ label: v.name, value: v.id })
    }
  })
  return opts
})

function isNew() {
  return route.params.id === 'new'
}

function getTapIdFromRoute() {
  const raw = route.params.id
  if (raw == null) return null
  const id = String(raw).trim()
  if (!id || id === 'undefined' || id === 'null' || id === 'new') return null
  return id
}

const { updatedTapData } = storeToRefs(global)
watch(updatedTapData, () => {
  const current = tap.value
  if (!current?.id || isNew()) return
  const updated = tapStore.tapList.find((t) => t.id === current.id)
  if (updated) tap.value = updated
})

onMounted(async () => {
  logDebug('TapView.onMounted()')
  showValidation.value = true

  if (isNew()) {
    tap.value = new Tap({})
    tapSaved.value = Tap.fromJson(tap.value.toJson())
  } else {
    const tapId = getTapIdFromRoute()
    if (!tapId) {
      global.messageError = 'Invalid tap id'
      tap.value = new Tap({})
      tapSaved.value = Tap.fromJson(tap.value.toJson())
      return
    }

    const fromStore = tapStore.tapList.find((t) => t.id === tapId)
    const result = fromStore ?? (await tapStore.getTap(tapId))
    if (result) {
      tap.value = result
      tapSaved.value = Tap.fromJson(result.toJson())
      const assigned = vesselStore.vesselList.find((v) => v.tapId === result.id)
      selectedVesselId.value = assigned ? assigned.id : ''
      originalVesselId.value = selectedVesselId.value
    } else {
      global.messageError = 'Failed to load tap'
    }
  }
})

const save = async () => {
  logDebug('TapView.save()')
  if (!tap.value) return
  global.clearMessages()
  const prevVesselId = originalVesselId.value
  isSaving.value = true
  try {
    if (isNew()) {
      const result = await tapStore.addTap(tap.value as Tap)
      if (result) {
        tap.value = result
        tapSaved.value = Tap.fromJson(result.toJson())
        originalVesselId.value = selectedVesselId.value
        global.tapChanged = false
        router.push({ name: 'tap', params: { id: tap.value.id } })
      } else {
        global.messageError = 'Failed to add tap'
      }
    } else {
      const result = await tapStore.updateTap(tap.value as Tap)
      if (!result) {
        global.messageError = 'Failed to save tap'
        return
      }
      tap.value = result

      if (selectedVesselId.value !== prevVesselId) {
        if (prevVesselId) {
          await vesselStore.assignTap(prevVesselId, null)
        }
        if (selectedVesselId.value) {
          await vesselStore.assignTap(selectedVesselId.value, tap.value.id)
        }
      }

      tapSaved.value = Tap.fromJson(result.toJson())
      originalVesselId.value = selectedVesselId.value
      global.tapChanged = false
      global.messageSuccess = 'Tap saved'
    }
  } finally {
    isSaving.value = false
  }
}

async function regenToken() {
  logDebug('TapView.regenToken()')
  if (!tap.value?.id) return
  const newToken = await tapStore.regenerateToken(tap.value.id)
  if (newToken) {
    tap.value.token = newToken
    global.messageSuccess = 'Token regenerated'
  } else {
    global.messageError = 'Failed to regenerate token'
  }
}
</script>
