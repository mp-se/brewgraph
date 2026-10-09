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
    <AppPageHeader :title="device ? `Gravity formula · ${device.name}` : 'Gravity formula'" />
    <template v-if="device != null">
      <form class="legacy-device-form" novalidate @submit.prevent="save">
        <GravityFormulaEditor
          ref="editor"
          :formula="device.gravityFormula"
          :unit="device.gravityFormulaUnit"
          :points="device.gravityCalibrationData"
          :device-name="device.name"
          :device-type="device.deviceType"
          :display-unit="config.gravityFormat === 'P' ? 'plato' : 'sg'"
          :temperature-unit="config.temperatureFormat === 'F' ? 'f' : 'c'"
          :disabled="global.disabled"
          @update:formula="device.gravityFormula = $event"
          @update:unit="device.gravityFormulaUnit = $event"
          @update:points="device.gravityCalibrationData = $event"
          @valid="formulaValid = $event"
          @copied="global.messageSuccess = 'Formula copied'"
          @editing="pointsEditing = $event"
        />
        <div class="app-button-row">
          <app-button
            type="submit"
            variant="primary"
            class="app-width-2"
            :disabled="global.disabled || isSaving || !changed || !formulaValid || pointsEditing"
            :aria-busy="isSaving"
          >
            <span v-if="isSaving" class="app-spinner app-spinner--small" role="status" aria-hidden="true"></span>
            <q-icon name="save" /> Save
          </app-button>
          <router-link :to="{ name: 'device', params: { id: device.id } }">
            <app-button type="button" variant="secondary" class="app-width-2">
              <q-icon name="cancel" /> Cancel
            </app-button>
          </router-link>
        </div>
        <div class="app-button-row q-mt-sm">
          <app-button
            type="button"
            variant="outline-secondary"
            class="app-width-2"
            :disabled="global.disabled"
            data-testid="gravity-formula-import"
            @click="editor?.openImport()"
          >
            <q-icon name="upload_file" /> Import profile
          </app-button>
          <app-button
            type="button"
            variant="outline-secondary"
            class="app-width-2"
            data-testid="gravity-formula-export"
            @click="editor?.exportProfile()"
          >
            <q-icon name="download" /> Export profile
          </app-button>
        </div>
      </form>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import AppPageHeader from '@/components/AppPageHeader.vue'
import GravityFormulaEditor from '@/components/device/GravityFormulaEditor.vue'
import { Device } from '@/modules/classes'
import { config, deviceStore, global } from '@/modules/pinia'
import router from '@/modules/router'

const GRAVITY_DEVICE_TYPES = ['gravitymon', 'ispindel']

const device = ref<Device | null>(null)
const saved = ref<Device | null>(null)
const isSaving = ref(false)
const formulaValid = ref(true)
const pointsEditing = ref(false)
const editor = ref<InstanceType<typeof GravityFormulaEditor> | null>(null)

const deviceId = () => String(router.currentRoute.value.params.id)
const changed = computed(() => !!device.value && !!saved.value && !Device.compare(device.value as Device, saved.value as Device))

// A page with unsaved edits asks before it is left, like every other editor.
watch(changed, (value) => { global.deviceChanged = value })
onUnmounted(() => { global.deviceChanged = false })

onMounted(async () => {
  const id = deviceId()
  const loaded = deviceStore.deviceList.find((d) => d.id === id) ?? (await deviceStore.getDevice(id))
  const canCarry = !!loaded && (GRAVITY_DEVICE_TYPES.includes(loaded.deviceType) || !loaded.deviceType)
  if (!loaded || !canCarry) {
    await router.replace(loaded ? { name: 'device', params: { id } } : { name: 'device-list' })
    return
  }
  saved.value = Device.fromJson(loaded.toJson())
  device.value = loaded
})

async function save() {
  if (!device.value || !formulaValid.value || pointsEditing.value) return
  global.clearMessages()
  isSaving.value = true
  try {
    const result = await deviceStore.updateDevice(device.value as Device)
    if (result) {
      device.value = result
      saved.value = Device.fromJson(result.toJson())
      global.deviceChanged = false
      global.messageSuccess = 'Gravity formula saved'
    } else {
      global.messageError = 'Failed to save the gravity formula'
    }
  } finally {
    isSaving.value = false
  }
}
</script>
