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
    <AppPageHeader title="Device List">
      <template #action>
        <app-button
          color="primary"
          unelevated
          :to="{ name: 'device', params: { id: 'new' } }"
          :disable="global.disabled"
        >
          Add Device
        </app-button>
      </template>
      <div class="row">
        <div class="col-12 col-sm-6 col-md-4">
          <AppSelect
            v-model="preferences.deviceListFilterDeviceType"
            :options="deviceTypeOptions"
            label="Device Type"
            help=""
            :disabled="global.disabled"
          />
        </div>
      </div>
    </AppPageHeader>

    <template v-if="deviceList != null">
      <q-markup-table class="app-table app-table--striped">
        <thead>
          <tr>
            <th scope="col" class="col-sm-3">
              <div :class="getSortedClass('name')">
                Name&nbsp;
                <a class="icon-link icon-link-hover" @click="sortList(deviceList, 'name', 'str')">
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-1">
              <div :class="getSortedClass('chipId')">
                Chip ID&nbsp;
                <a class="icon-link icon-link-hover" @click="sortList(deviceList, 'chipId', 'str')">
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th v-if="showChipFamily" scope="col" class="col-sm-2">
              <div :class="getSortedClass('chipFamily')">
                Chip Family&nbsp;
                <a
                  class="icon-link icon-link-hover"
                  @click="sortList(deviceList, 'chipFamily', 'str')"
                >
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-2">
              <div :class="getSortedClass('deviceType')">
                Device Type&nbsp;
                <a
                  class="icon-link icon-link-hover"
                  @click="sortList(deviceList, 'deviceType', 'str')"
                >
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-1">Collect logs</th>
            <th scope="col" class="col-sm-2">Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in paginatedDeviceList" :key="d.id">
            <td class="text-body1">
              <DeviceColorSwatch :color="d.deviceColor" class="q-mr-sm" />{{ d.name }}
              <span
                v-if="d.failedIngestCounter > 0"
                class="app-badge app-badge--warning text-dark q-ml-sm"


                title="Readings dropped since last successful ingest"
              >
                {{ d.failedIngestCounter }} readings dropped
              </span>
            </td>
            <td class="text-body1">
              {{ d.chipId }}
            </td>
            <td v-if="showChipFamily" class="text-body1">{{ d.chipFamily }}</td>
            <td class="text-body1">{{ d.deviceType }}</td>
            <td>
              <q-toggle
                dense
                :model-value="d.collectLogs"
                :disable="global.disabled"
                title="Collect logs from device when active"
                aria-label="Collect logs from device when active"
                data-testid="collect-logs-toggle"
                @update:model-value="toggleDeviceLogging(d.id)"
              />
            </td>
            <td>
              <AppRowActions label="Device actions">
                <AppRowAction
                  kind="primary"
                  icon="edit"
                  label="Edit device"
                  :to="{ name: 'device', params: { id: d.id } }"
                  :disable="global.disabled"
                />
                <AppRowAction
                  kind="negative"
                  icon="delete_forever"
                  label="Delete device"
                  :disable="global.disabled"
                  @click.prevent="deleteDevice(d.id, d.mdns)"
                />
                <AppRowAction
                  v-if="batchStore.anyBatchesForDevice(d.chipId)"
                  kind="positive"
                  icon="inventory_2"
                  label="Show batches for this device"
                  :to="{ name: 'batch-list', query: { chipId: d.chipId } }"
                  :disable="global.disabled"
                />
                <AppRowAction
                  v-if="d.url.length > 7"
                  icon="link"
                  label="Open device UI"
                  :disable="global.disabled"
                  @click="openUrl(d.url)"
                />
                <AppRowAction
                  v-if="devicesWithLog.includes(d.chipId, 0)"
                  icon="description"
                  label="Show device log"
                  :to="{ name: 'device-log', params: { id: d.chipId } }"
                  :disable="global.disabled"
                />
              </AppRowActions>
            </td>
          </tr>
        </tbody>
      </q-markup-table>

      <div class="row items-center app-list-actions">
        <div class="col-12 col-md app-list-actions__primary">
          <app-button
            outline
            color="primary"
            :disable="global.disabled"
            @click="search()"
          >
            Search for Devices
          </app-button>
          <app-button
            outline
            color="primary"
            :to="{ name: 'device-log', params: { id: '*' } }"
            :disable="global.disabled"
          >
            Device Logs
          </app-button>
        </div>
        <div
          v-if="totalPages > 1"
          class="col-12 col-md-auto row justify-end"
        >
          <nav aria-label="Device list pagination">
            <ul class="app-pagination q-mb-none">
              <li class="app-pagination__item" :class="{ disabled: currentPage === 1 }">
                <app-button
                  type="button"
                  class="app-pagination__link"
                  aria-label="Previous page"
                  @click="goToPage(currentPage - 1)"
                >
                  Previous
                </app-button>
              </li>
              <li
                v-for="page in totalPages"
                :key="page"
                class="app-pagination__item"
                :class="{ active: currentPage === page }"
              >
                <app-button
                  type="button"
                  class="app-pagination__link"
                  :aria-label="`Page ${page}`"
                  :aria-current="currentPage === page ? 'page' : undefined"
                  @click="goToPage(page)"
                >
                  {{ page }}
                </app-button>
              </li>
              <li class="app-pagination__item" :class="{ disabled: currentPage === totalPages }">
                <app-button
                  type="button"
                  class="app-pagination__link"
                  aria-label="Next page"
                  @click="goToPage(currentPage + 1)"
                >
                  Next
                </app-button>
              </li>
            </ul>
          </nav>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="row q-col-gutter-sm">
        <div class="col-md-12">
          <p class="text-subtitle1">Loading...</p>
        </div>
      </div>
    </template>

    <AppConfirmDialog
      :callback="confirmDeleteCallback"
      :message="confirmDeleteMessage"
      id="deleteDevice"
      title="Delete device"
      :disabled="global.disabled"
    />

    <AppSelectDialog
      v-model="searchSelected"
      :disabled="searchOptions.length === 0"
      :callback="confirmSearchCallback"
      message="Select a device to add"
      id="searchDevice"
      title="Select device"
      :options="searchOptions"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { Device } from '@/modules/classes'
import { global, preferences, deviceStore, batchStore } from '@/modules/pinia'
import { apiFetch } from '@/modules/apiClient'
import { logDebug, logInfo, logError } from '@/ui'
import { useSortableList } from '@/modules/useSortableList'
import AppPageHeader from '@/components/AppPageHeader.vue'
import DeviceColorSwatch from '@/components/DeviceColorSwatch.vue'
import AppRowAction from '@/components/AppRowAction.vue'
import AppRowActions from '@/components/AppRowActions.vue'
import { detectId, detectMdns, detectPlatform, detectDeviceType as detectDeviceTypeFromStatus } from '@/modules/detect'

const confirmDeleteMessage = ref(null)
const confirmDeleteId = ref(null)

const deviceList = ref(null)
const currentPage = ref(1)
const ITEMS_PER_PAGE = 10
const { updatedDeviceData } = storeToRefs(global)
const { deviceListFilterDeviceType } = storeToRefs(preferences)

const { sortedIconClass, getSortedClass, sortList, applySortList } = useSortableList(
  'mdns',
  'str',
  false
)

watch(updatedDeviceData, () => {
  filterDeviceList()
  applySortList(deviceList.value)
  if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
})

const totalPages = computed(() => {
  const count = deviceList.value?.length || 0
  return Math.max(1, Math.ceil(count / ITEMS_PER_PAGE))
})

// The column earns its width: it is shown only while a listed device has a chip family.
const showChipFamily = computed(() => (deviceList.value ?? []).some((d) => Boolean(d.chipFamily)))

const paginatedDeviceList = computed(() => {
  if (!deviceList.value) return []
  const start = (currentPage.value - 1) * ITEMS_PER_PAGE
  return deviceList.value.slice(start, start + ITEMS_PER_PAGE)
})

function goToPage(page) {
  const clamped = Math.max(1, Math.min(page, totalPages.value))
  currentPage.value = clamped
}

const deviceTypeOptions = ref([
  { label: '(All)', value: '*' },
  { label: '(Blank)', value: '' },
  { label: 'Gravitymon', value: 'gravitymon' },
  { label: 'Gravitymon Gateway', value: 'gravitymon_gateway' },
  { label: 'Chamber Controller', value: 'chamber_controller' },
  { label: 'Kegmon', value: 'kegmon' },
  { label: 'Pressuremon', value: 'pressuremon' },
  { label: 'iSpindel', value: 'ispindel' }
])

const searchOptions = ref([])
const searchSelected = ref('')
const devicesWithLog = ref([])
let releaseSearchBusy = null

onUnmounted(() => {
  releaseSearchBusy?.()
})

onMounted(() => {
  logDebug('DeviceListView.onMounted()')
  filterDeviceList()
  fetchDeviceLogList()
  applySortList(deviceList.value)
})

function fetchDeviceLogList() {
  logDebug('DeviceListView.fetchDeviceLogList()')

  devicesWithLog.value = []

  const releaseBusy = global.acquireBusy()
  apiFetch('GET', 'devices/logs')
    .then((res) => {
      logDebug('DeviceListView.fetchDeviceLogList()', res.status)
      if (!res.ok) throw res
      return res.json()
    })
    .then((json) => {
      json.forEach((chipId) => {
        if (!chipId.endsWith('.log.1')) {
          chipId = chipId.replace('.log', '')
          devicesWithLog.value.push(chipId)
        }
      })

      logInfo('DeviceListView.fetchDeviceLogList()', devicesWithLog.value)
    })
    .catch(() => {
      logError('DeviceListView.fetchDeviceLogList()', 'Failed to fetch list of devices with logs')
    })
    .finally(releaseBusy)
}

function filterDeviceList() {
  logDebug('DeviceListView.filterDeviceList', preferences.deviceListFilterDeviceType)

  deviceList.value = []
  deviceStore.deviceList.forEach((d) => {
    if (preferences.deviceListFilterDeviceType == '*') {
      deviceList.value.push(d)
    } else {
      if (d.deviceType == preferences.deviceListFilterDeviceType) deviceList.value.push(d)
    }
  })
}

if (currentPage.value > totalPages.value) {
  currentPage.value = totalPages.value
}

// The switch saves at once. A failed save puts the switch back and says which device it was.
async function toggleDeviceLogging(id) {
  logDebug('DeviceListView.toggleDeviceLogging()', id)

  const d = deviceList.value.find((device) => device.id == id)
  if (!d) return

  const previous = d.collectLogs
  d.collectLogs = !previous
  const success = await deviceStore.updateDevice(d)
  if (success) {
    logDebug('DeviceListView.toggleDeviceLogging()', 'Success')
  } else {
    d.collectLogs = previous
    global.messageError = `Could not save "Collect logs" for device ${d.name || d.mdns || id}; the setting was put back`
  }
}

watch(deviceListFilterDeviceType, async (selected) => {
  logDebug('DeviceListView.watch(filterDeviceType)', selected)
  filterDeviceList()
  applySortList(deviceList.value)
})

const confirmDeleteCallback = async (result) => {
  logDebug('DeviceListView.confirmDeleteCallback()', result)

  if (result) {
    global.clearMessages()
    const releaseBusy = global.acquireBusy()
    try {
      const success = await deviceStore.deleteDevice(confirmDeleteId.value)
      if (success) global.messageSuccess = 'Deleted device'
      else global.messageError = 'Failed to delete device'
    } finally {
      releaseBusy()
    }
  }
}

const deleteDevice = (id, name) => {
  logDebug('DeviceListView.deleteDevice()', id, name)

  confirmDeleteMessage.value = "Do you really want to delete device '" + name + "'"
  confirmDeleteId.value = id
  document.getElementById('deleteDevice').click()
}

function openUrl(url) {
  logDebug('DeviceListView.openUrl()', url)
  window.open(url, '_blank')
}

async function search() {
  logDebug('DeviceListView.search()')

  global.clearMessages()
  searchOptions.value = []
  searchSelected.value = ''
  document.getElementById('searchDevice').click()

  /*
  searchOptions.value = [{ label: "- none -", value: "", host: "", type: "", name: "" }]
  searchOptions.value.push({ label: "Test 1", value: "192.168.1.2", host: "host1", type: "http.local.", name: "name1" })
  searchOptions.value.push({ label: "Test 2", value: "192.168.1.3", host: "host2", type: "http.local.", name: "name2" })
  */

  releaseSearchBusy?.()
  releaseSearchBusy = global.acquireBusy()
  const ml = await deviceStore.searchNetwork()
  if (ml) {
    searchOptions.value = [{ label: '- none -', value: '' }]

    ml.forEach((m) => {
      searchOptions.value.push({
        label: m.name + ',' + m.host + ' (' + m.type + ')',
        value: m.host,
        host: m.host,
        type: m.type,
        name: m.name
      })
    })
  } else {
    global.messageError = 'Failed to search for mDNS devices on the local network'
  }
}

const confirmSearchCallback = (result, value) => {
  logDebug('DeviceListView.confirmSearchCallback()', result, value)
  releaseSearchBusy?.()
  releaseSearchBusy = null

  if (result) {
    global.clearMessages()
    if (value != '') {
      searchOptions.value.forEach((e) => {
        if (e.value == value) {
          logDebug('DeviceListView.confirmSearchCallback()', e)
          detectDeviceType('http://' + e.value)
        }
      })
    }
  }
}

async function detectDeviceType(url) {
  logDebug('DeviceListView.detectDeviceType()', url)
  const releaseBusy = global.acquireBusy()
  try {
    // This should detect the GravityMon, KegMon and PressureMon device type
    const status = await deviceStore.proxyRequest('GET', url + '/api/status', '', '')
    logDebug('DeviceView.fetchConfigEspFwkV1()', status)

    const device = new Device(0, '', '', '', '', '', '', url, '', false)
    device.chipId = detectId(status)
    device.mdns = detectMdns(status)
    device.chipFamily = detectPlatform(status)
    device.deviceType = detectDeviceTypeFromStatus(status)

    if (device.chipId != '') {
      const success = await deviceStore.addDevice(device)
      if (success) {
        global.messageSuccess = 'Saved device ' + device.mdns
      } else {
        global.messageError = 'Failed to save device, it might already exist.'
      }
    } else {
      global.messageError = 'Unable to detect device type for ' + device.mdns
    }
  } catch {
    global.messageError = 'Failed to fetch data from device, is it turned on ?'
  } finally {
    releaseBusy()
  }
}
</script>
