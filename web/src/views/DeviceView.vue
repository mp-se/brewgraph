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
    <AppPageHeader title="Device" />
    <template v-if="device != null">
      <form
        @submit.prevent="save"
        class="app-validation legacy-device-form"
        :class="{ 'was-validated': showValidation }"
        novalidate
      >
        <div class="row q-col-gutter-md device-form-grid">
          <div class="col-md-6">
            <AppTextInput
              v-model="device.name"
              label="Name"
              width="11"
              help="Name of the device."
              :disabled="global.disabled"
              required
            >
            </AppTextInput>
          </div>
          <div class="col-md-6" v-show="!device.isIspindel">
            <AppTextInput
              v-model="device.chipId"
              label="Chip ID"
              width="10"
              maxlength="6"
              help="This is the 6 character hexadecimal ID that identifies the device"
              :disabled="global.disabled"
              pattern="[0-9a-fA-F]{6}"
              placeholder="ABC123"
            >
            </AppTextInput>
          </div>
          <div class="col-md-4">
            <AppTextInput
              v-model="device.mdns"
              label="mDNS"
              width="11"
              help="This is the mDNS name of the device."
              :disabled="global.disabled"
              placeholder="device.local"
            >
            </AppTextInput>
          </div>
          <div class="col-md-5">
            <AppTextInput
              v-model="device.url"
              type="url"
              label="Device URL"
              width="11"
              help="URL to the device to fetch data and configuration from. E.g. http://"
              :disabled="global.disabled"
              placeholder="http://device.local"
            >
            </AppTextInput>
          </div>

          <div class="col-md-2" v-show="device.canCollectLogs">
            <AppToggle
              v-model="device.collectLogs"
              label="Collect logs"
              help=""
              :disabled="global.disabled"
            >
            </AppToggle>
          </div>

          <div class="col-md-12">
            <AppTextInput
              v-model="device.description"
              label="Description"
              width="11"
              help="Notes and description about the device"
              :disabled="global.disabled"
            >
            </AppTextInput>
          </div>
          <div class="col-12">
            <DeviceClassificationFields
              :device="device"
              :disabled="global.disabled"
              @update:chip-family="device.chipFamily = $event"
              @update:device-type="device.deviceType = $event"
              @update:device-color="device.deviceColor = $event"
              :chip-family-options="chipFamilyOptions"
              :device-type-options="deviceTypeOptions"
              :device-color-options="deviceColorOptions"
            />
          </div>
          <div class="col-md-6" v-show="device.isPressuremon || device.isChamber">
            <AppSelect
              v-model="device.vesselId"
              :options="vesselOptions"
              label="Vessel"
              help="Vessel this device reports pressure/temperature readings for — works whether the vessel is on tap or in storage"
              :disabled="global.disabled"
            ></AppSelect>
          </div>
          <div class="col-md-12" v-show="device.canFetchConfig">
            <AppTextInput
              :model-value="configPayload()"
              readonly
              label="Configuration"
              width="12"
              help="Copy of the device configuration, can be used as backup, use fetch to collect it"
              disabled
            >
            </AppTextInput>
          </div>
        </div>

        <div class="row q-col-gutter-sm" v-if="device.failedIngestCounter > 0">
          <div class="col-md-12">
            <AppMessage
              :dismissable="false"
              :message="
                device.failedIngestCounter +
                ' readings dropped since last successful ingest'
              "
              alert="warning"
            />
          </div>
        </div>

        <div class="row q-col-gutter-sm" v-if="activeFermentationSteps != null">
          <div class="col-md-12">
            <hr />
          </div>
          <div class="row">
            <div class="col-md-12">
              <p class="text-subtitle1">Active Fermentation Steps</p>
              <FermentationStepFragment
                :fermentationSteps="activeFermentationSteps"
                :tempUnit="config.tempUnit"
                :editable="false"
              ></FermentationStepFragment>
            </div>
          </div>
        </div>

        <div class="row q-col-gutter-sm device-action-toolbar">
          <div class="col-md-12">
            <hr />
          </div>
          <div class="col-md-12 app-button-row">
            <app-button
              type="submit"
              variant="primary" class="app-width-2"
              :disabled="global.disabled || isSaving || !deviceChanged() || !device.name"
              :aria-busy="isSaving"
            >
              <span
                v-if="isSaving"
                class="app-spinner app-spinner--small"
                role="status"
                aria-hidden="true"
              ></span>
              <q-icon name="save" /> Save
            </app-button>
            <router-link :to="{ name: 'device-list' }">
              <app-button type="button" variant="secondary" class="app-width-2">
                <q-icon name="cancel" /> Cancel
              </app-button>
            </router-link>
          </div>
          <div class="col-md-12 app-button-row">
            <router-link
              v-if="!isNew() && isGravityDevice"
              :to="{ name: 'device-gravity-formula', params: { id: device.id } }"
            >
              <app-button
                type="button"
                variant="outline-secondary" class="app-width-2"
                data-testid="gravity-formula-link"
              >
                <q-icon name="functions" /> Formula editor
              </app-button>
            </router-link>
            <app-button
              v-if="hasDirectDeviceToken"
              type="button"
              variant="outline-secondary" class="app-width-2"
              :disabled="global.disabled"
              title="Regenerate API token. This immediately rotates the token and invalidates the previous device configuration."
              aria-label="Regenerate API token. This immediately rotates the token and invalidates the previous device configuration."
              @click="regenToken"
            >
              <q-icon name="refresh" /> Regenerate token
            </app-button>

            <app-button
              v-if="device.canFetchConfig"
              type="button"
              variant="outline-secondary" class="app-width-2"
              @click="fetchConfigFromDevice()"
              :disabled="global.disabled || device.url == ''"
            >
              <q-icon name="download" /> Fetch config
            </app-button>

            <a href="https://www.gravitymon.com/flasher/index.html" target="_blank" rel="noopener noreferrer">
              <app-button type="button" variant="outline-secondary" class="app-width-2">
                <q-icon name="bolt" /> Flash Device
              </app-button>
            </a>

            <CodeViewModal
              @click="viewConfig()"
              :model-value="render"
              title="Device configuration"
              button="View config"
              :disabled="global.disabled || !configPayload()"
            />

            <AppConfirmDialog
              :callback="deleteFermentationStepsCallback"
              message="Do you really want to delete the fermentation steps"
              id="deleteFermentationSteps"
              title="Delete"
              :disabled="global.disabled"
            />

            <app-button
              v-if="activeFermentationSteps != null"
              type="button"
              variant="outline-secondary" class="app-width-2"
              @click="deleteFermentationSteps()"
              :disabled="global.disabled"
            >
              Delete steps
            </app-button>
          </div>
        </div>

        <section v-if="device.isKegmon" class="device-kegmon-credentials q-mt-sm">
          <div class="app-legacy-card">
            <div class="app-legacy-card__header">Kegmon credentials</div>
            <div class="app-legacy-card__body">
              <p class="q-mb-sm">
                Kegmon authenticates with the API token owned by its Tap, not this Device record.
              </p>
              <router-link
                :to="kegmonTapId ? { name: 'tap', params: { id: kegmonTapId } } : { name: 'tap-list' }"
              >
                <app-button type="button" variant="secondary">
                  {{ kegmonTapId ? 'Open associated Tap' : 'Open Taps' }}
                </app-button>
              </router-link>
            </div>
          </div>
        </section>

        <div class="row q-col-gutter-sm q-mt-sm device-connection-details" v-if="hasDirectDeviceToken">
          <DeviceSetupFragment
            :device-type="device.deviceType"
            :token="device.token"
            :has-readings="!!device.lastSeen"
          />
        </div>
      </form>
    </template>
    <template v-else>
      <AppMessage
        :dismissable="false"
        :message="'Unable to find device with id ' + $route.params.id"
        alert="danger"
      />
      <div class="row q-col-gutter-sm">
        <div class="col-md-12"></div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { config, global, deviceStore, vesselStore } from '@/modules/pinia'
import { storeToRefs } from 'pinia'
import { validateCurrentForm } from '@/modules/utils'
import {
  Device,
  deviceTypeOptions,
  deviceColorOptions,
  chipFamilyOptions,
  CHIP_FAMILY_ESP8266
} from '@/modules/classes'
import FermentationStepFragment from '@/fragments/FermentationStepFragment.vue'
import DeviceSetupFragment from '@/fragments/DeviceSetupFragment.vue'
import router from '@/modules/router'
import { logDebug, logInfo } from '@/ui'
import AppPageHeader from '@/components/AppPageHeader.vue'
import DeviceClassificationFields from '@/components/DeviceClassificationFields.vue'
import CodeViewModal from '@/components/CodeViewModal.vue'
import { deviceConfigText, fetchDeviceConfigV1 } from '@/modules/deviceConfigFetch'

const render = ref('{}')
const device = ref(null)
const deviceSaved = ref(null)
const activeFermentationSteps = ref(null)
const showValidation = ref(false)
const isSaving = ref(false)
const isGravityDevice = computed(() => ['gravitymon', 'ispindel'].includes(device.value?.deviceType) ||
  (!device.value?.deviceType && !!device.value?.id))

function deviceChanged() {
  logDebug('DeviceView.deviceChanged()')

  if (device.value == null) return false

  global.deviceChanged = !Device.compare(device.value, deviceSaved.value)
  return global.deviceChanged
}

// Show the brewer what the device actually returned, not the storage wrappers around it.
const configPayload = () => deviceConfigText(device.value?.config)

const viewConfig = () => {
  render.value = configPayload()
}

const vesselOptions = computed(() => {
  const opts = [{ label: '-- Disabled --', value: null }]
  vesselStore.vesselList.forEach((v) => {
    opts.push({ label: v.name, value: v.id })
  })
  return opts
})

const hasDirectDeviceToken = computed(
  () => !!device.value?.token && device.value.canIngest && !device.value.isKegmon
)

const kegmonTapId = computed(() => {
  if (!device.value?.isKegmon || !device.value.vesselId) return null
  return vesselStore.vesselList.find((v) => v.id === device.value.vesselId)?.tapId ?? null
})

function isNew() {
  return router.currentRoute.value.params.id == 'new' ? true : false
}

const { updatedDeviceData } = storeToRefs(global)
watch(updatedDeviceData, async () => {
  if (!device.value?.id || isNew()) return
  const updated = deviceStore.deviceList.find((d) => d.id === device.value.id)
  // An SSE refresh may arrive just after create/save. Keep the rendered form and
  // its baseline in step; otherwise a successful save appears dirty again.
  // Preserve in-progress edits when another client changes this device.
  if (updated && Device.compare(device.value, deviceSaved.value)) {
    device.value = updated
    deviceSaved.value = Device.fromJson(updated.toJson())
    global.deviceChanged = false
  }
  const steps = await deviceStore.getFermentationSteps(device.value.id)
  if (steps && steps.length > 0) activeFermentationSteps.value = steps
})

onMounted(async () => {
  logDebug('DeviceView.onMounted()')

  await vesselStore.getVesselList()
  device.value = null
  activeFermentationSteps.value = null
  showValidation.value = true
  if (isNew()) {
    deviceSaved.value = new Device()
    device.value = new Device()
  } else {
    const id = router.currentRoute.value.params.id
    const fromStore = deviceStore.deviceList.find((d) => d.id === id)
    const result = fromStore ?? (await deviceStore.getDevice(id))
    if (result) {
      deviceSaved.value = Device.fromJson(result.toJson())
      device.value = result
      const steps = await deviceStore.getFermentationSteps(result.id)
      if (steps && steps.length > 0) {
        activeFermentationSteps.value = steps
      }
    } else {
      // global.messageError = "Failed to load device " + id
    }
  }
})

watch(
  () => device.value?.deviceType,
  () => {
    if (device.value.isIspindel) {
      device.value.chipFamily = CHIP_FAMILY_ESP8266
    }
  }
)


async function fetchConfigFromDevice() {
  logInfo('DeviceView.fetchConfigFromDevice()')

  global.clearMessages()
  const releaseBusy = global.acquireBusy()
  try {
    validateUrl()
    await fetchConfigEspFwkV1() // Applies to Kegmon 1.x and Gravitymon 2.x
  } finally {
    releaseBusy()
  }
}

async function fetchConfigEspFwkV1() {
  return fetchDeviceConfigV1(device.value, (...args) => deviceStore.proxyRequest(...args), (message) => {
    global.messageError = message
  })
}

function validateUrl() {
  device.value.url =
    device.value.url.endsWith('/') || device.value.url.length < 7
      ? device.value.url
      : device.value.url + '/'
}

const save = async () => {
  logDebug('DeviceView.save()')

  validateUrl()
  if (!validateCurrentForm()) return

  global.clearMessages()
  isSaving.value = true
  try {
    if (isNew()) {
      const result = await deviceStore.addDevice(device.value)
      logDebug('DeviceView.addDevice()', 'Add device', result)
      if (result) {
        device.value = result
        deviceSaved.value = Device.fromJson(result.toJson())
        global.deviceChanged = false
        await router.push({ name: 'device', params: { id: result.id } })
        await nextTick()
        // The route transition can refresh the new device. Capture the final
        // displayed values, not the pre-navigation response, as the baseline.
        deviceSaved.value = Device.fromJson(device.value.toJson())
        global.deviceChanged = false
      } else {
        global.messageError = 'Failed to add device'
      }
    } else {
      const saved = await deviceStore.updateDevice(device.value)
      logDebug('DeviceView.saveDevice()', 'Update device', saved)
      if (saved) {
        // The API can normalise persisted fields. Adopt its response as both the
        // displayed value and save baseline so the button/leave guard cannot stay
        // dirty after a successful request.
        device.value = saved
        deviceSaved.value = Device.fromJson(saved.toJson())
        global.deviceChanged = false
        global.messageSuccess = 'Saved device'
      } else {
        global.messageError = 'Failed to save device'
      }
    }
  } finally {
    isSaving.value = false
  }
}

async function regenToken() {
  logDebug('DeviceView.regenToken()')
  const newToken = await deviceStore.regenerateToken(device.value.id)
  if (newToken) {
    device.value.token = newToken
    global.messageSuccess = 'Token regenerated'
  } else {
    global.messageError = 'Failed to regenerate token'
  }
}

function deleteFermentationSteps() {
  logDebug('DeviceView.deleteFermentationSteps()')
  document.getElementById('deleteFermentationSteps').click()
}

async function deleteFermentationStepsCallback() {
  logDebug('DeviceView.deleteFermentationStepsCallback()')

  const success = await deviceStore.deleteDeviceFermentationSteps(device.value.id)
  logDebug('DeviceView.deleteFermentationSteps()', success)
  if (success) {
    global.messageSuccess = 'Fermentation steps removed'
    activeFermentationSteps.value = null
  } else {
    global.messageError = 'Failed to remove fermentation steps'
  }
}

const chipIdValid = ref(true)

function validateChipId() {
  const id = device.value?.chipId ?? ''
  chipIdValid.value = /^[0-9a-f]{6}$/.test(id)
  return chipIdValid.value
}

defineExpose({
  device,
  chipIdValid,
  validateChipId,
  fetchConfigFromDevice,
  validateUrl,
  deviceChanged,
  isNew,
  isSaving,
  save,
  deleteFermentationSteps
})
</script>
