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
    <div class="device-log-toolbar">
      <div class="device-log-toolbar__title">
        <p class="text-h6 q-mb-none">Device Logs</p>
      </div>
      <div class="device-log-toolbar__selector">
        <AppSelect
          v-model="deviceSelected"
          :options="deviceOptions"
          label="Device Logs"
          help=""
          :disabled="global.disabled"
        >
        </AppSelect>
      </div>

      <div class="device-log-toolbar__actions" aria-label="Device log actions">
        <app-button
          @click="fetchLogs()"
          type="button"
          variant="primary"
          :disabled="deviceSelected == ''"


          title="Fetch latest logs"
          aria-label="Fetch latest logs"
        >
          Refresh
        </app-button>
        &nbsp;
        <app-button
          @click="deleteLogs()"
          type="button"
          variant="negative"
          :disabled="deviceSelected == ''"


          title="Delete logs"
          aria-label="Delete logs"
        >
          <q-icon name="delete_forever" />
        </app-button>
        &nbsp;
        <app-button
          @click="hideInfo()"
          type="button"
          variant="secondary"
          :disabled="deviceSelected == ''"


          title="Hide info level logs"
          aria-label="Hide info level logs"
        >
          - Info
        </app-button>
        &nbsp;
        <app-button
          @click="hideWarn()"
          type="button"
          variant="secondary"
          :disabled="deviceSelected == ''"


          title="Hide warning level logs"
          aria-label="Hide warning level logs"
        >
          - Warn
        </app-button>
        &nbsp;
        <app-button
          @click="goToBottom()"
          type="button"
          variant="primary"
          :disabled="deviceSelected == ''"


          title="Go to the end of the log window"
          aria-label="Go to the end of the log window"
        >
          <q-icon name="subdirectory_arrow_right" />
        </app-button>
      </div>
    </div>
    <hr />

    <div class="row" v-if="deviceSelected != ''">
      <div class="col-md-12">
        <p>
          Displaying {{ deviceLog.length }} lines, Size:
          {{ Number(deviceLogSize / 1024).toFixed(0) }} kb, Last log date: {{ logStatusLast }},
          Collected: {{ Number(logStatusSize / 1024).toFixed(0) }} kb
        </p>
      </div>
      <hr />
    </div>

    <div class="row" v-if="deviceLog.length">
      <div class="col-md-12">
        <div class="device-log-lines text-mono" aria-label="Device log entries">
          <div v-for="(line, index) in deviceLog" :key="index">{{ line }}</div>
        </div>

        <hr />
      </div>
    </div>
  </div>
  <div id="pageBottom"></div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { global, deviceStore } from '@/modules/pinia'
import { apiFetch } from '@/modules/apiClient'
import { logDebug, logError } from '@/ui'
import router from '@/modules/router'

const deviceSelected = ref('')
const deviceOptions = ref([])
const deviceLog = ref([])
const logStatusData = ref({})

const logStatusLast = computed(() => {
  if (deviceSelected.value in logStatusData.value)
    return logStatusData.value[deviceSelected.value].last || 'No date'
  return 'No date'
})

const logStatusSize = computed(() => {
  if (deviceSelected.value in logStatusData.value)
    return logStatusData.value[deviceSelected.value].size || 0
  return 0
})

const deviceLogSize = computed(() => {
  let l = 0

  deviceLog.value.forEach((e) => {
    l += e.length
  })

  return l
})

function goToBottom() {
  document.getElementById('pageBottom').scrollIntoView({ behavior: 'smooth' })
}

function hideInfo() {
  const l = []

  deviceLog.value.forEach((e) => {
    if (e.search(' I: ') == -1) l.push(e)
  })

  deviceLog.value = l
}

function hideWarn() {
  const l = []

  deviceLog.value.forEach((e) => {
    if (e.search(' W: ') == -1) l.push(e)
  })

  deviceLog.value = l
}

watch(deviceSelected, () => {
  fetchLogs()
})

async function deleteLogs() {
  const releaseBusy = global.acquireBusy()
  try {
    const res = await apiFetch('DELETE', 'devices/logs/' + deviceSelected.value)
    logDebug('DeviceLogView.deleteLogs()', res.status)
    if (!res.ok) throw res
    await updateDeviceLogList()
  } catch {
    global.messageError = 'Failed to delete logfile for device'
  } finally {
    releaseBusy()
  }
}

async function fetchLogs() {
  if (deviceSelected.value == '') {
    deviceLog.value = []
    return
  }

  const releaseBusy = global.acquireBusy()
  try {
    const res = await apiFetch('GET', 'devices/logs/' + deviceSelected.value)
    logDebug('DeviceLogView.fetchLogs()', res.status)
    if (!res.ok) throw res
    deviceLog.value = (await res.text()).split('\n')

    // Try to load the .1 file if this exists; the active log still renders if it does not.
    try {
      const rotated = await apiFetch('GET', 'devices/logs/' + deviceSelected.value + '?rotated=true')
      logDebug('DeviceLogView.fetchLogs()', rotated.status)
      if (!rotated.ok) throw rotated
      deviceLog.value = (await rotated.text()).split('\n').concat(deviceLog.value)
    } catch {
      logDebug('DeviceLogView.fetchLogs()', 'Failed to retrieve second log file')
    }
  } catch {
    global.messageError = 'Failed to load logfile for device'
  } finally {
    releaseBusy()
  }
}

onMounted(() => {
  logDebug('DeviceLogView.onMounted()')
  updateDeviceLogList()

  if (router.currentRoute.value.params.id != '*')
    deviceSelected.value = router.currentRoute.value.params.id

  apiFetch('GET', 'system/self-test')
    .then((res) => {
      return res.json()
    })
    .then((json) => {
      json.log.forEach((entry) => {
        const [, deviceid, attribute] = entry.name.split('_')
        if (!logStatusData.value[deviceid]) logStatusData.value[deviceid] = {}
        let value = entry.value
        if (attribute === 'start' || attribute === 'last') {
          const date = new Date(value * 1000)
          const pad = (n) => n.toString().padStart(2, '0')
          value = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
        }
        logStatusData.value[deviceid][attribute] = value
      })

      logDebug('DeviceLogView.onMounted()', json)
    })
    .catch((err) => {
      logError('DeviceLogView.onMounted()', err)
    })
})

async function updateDeviceLogList() {
  logDebug('DeviceLogView.updateDeviceLogList()')

  deviceOptions.value = [{ label: '-- none --', value: '' }]
  deviceLog.value = []
  deviceSelected.value = ''

  const releaseBusy = global.acquireBusy()
  try {
    const res = await apiFetch('GET', 'devices/logs')
    logDebug('DeviceLogView.updateDeviceLogList()', res.status)
    if (!res.ok) throw res
    const json = await res.json()
    json.forEach((chipId) => {
      if (!chipId.endsWith('.log.1')) {
        chipId = chipId.replace('.log', '')
        deviceStore.deviceList.forEach((device) => {
          if (device.chipId == chipId) {
            deviceOptions.value.push({
              label: device.mdns + ' - ' + device.chipId + ' - ' + device.deviceType,
              value: chipId
            })
          }
        })
      }
    })
  } catch {
    global.messageError = 'Failed to retrive list of system log enties'
  } finally {
    releaseBusy()
  }
}

defineExpose({ deviceSelected, deviceOptions })
</script>

<style scoped>
.device-log-toolbar {
  display: grid;
  grid-template-columns: minmax(9rem, 1fr) minmax(16rem, 22rem) auto;
  align-items: end;
  gap: 12px;
}

.device-log-toolbar__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-height: 40px;
}

.device-log-toolbar__actions :deep(.app-button) {
  margin: 0;
}

.device-log-lines {
  max-width: 100%;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

@media (max-width: 767px) {
  .device-log-toolbar {
    grid-template-columns: 1fr;
  }

  .device-log-toolbar__actions {
    justify-content: flex-start;
  }
}
</style>
