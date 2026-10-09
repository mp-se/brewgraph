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
  <div class="app-page home-page">
    <header class="home-overview-heading">
      <p class="home-overview-heading__title text-h6">Home - Overview</p>
      <div class="home-dashboard-toggles">
        <div class="home-dashboard-toggles__control">
          <AppToggle v-model="preferences.showChamberTemps" label="Chamber" help="" :disabled="global.disabled"
            title="Show data from chamber controllers on dashboard"
            aria-label="Show data from chamber controllers on dashboard">
          </AppToggle>
        </div>
        <div class="home-dashboard-toggles__control">
          <AppToggle v-model="preferences.showKegmonTaps" label="Kegmon" help="" :disabled="global.disabled"
            title="Show data from Kegmon taps on dashboard"
            aria-label="Show data from Kegmon taps on dashboard">
          </AppToggle>
        </div>
      </div>
    </header>
    <hr class="app-page-divider" />

    <div class="row q-col-gutter-md">
      <div class="col-md-4" v-for="b in activeBatchList" :key="b.id">
        <AppCard :header="'Batch: ' + b.name" color="primary" title="">
          <div class="home-batch-summary">
            <div class="home-batch-summary__meta">
              <div class="home-batch-summary__devices" aria-label="Assigned devices">
                <span
                  v-for="device in getBatchDevices(b.id)"
                  :key="device.id"
                  class="app-badge rounded-borders app-badge app-badge--light app-border vertical-middle"
                  :title="`${deviceRoleLabel(device)}: ${device.name}`"
                  :aria-label="`${deviceRoleLabel(device)} device: ${device.name}`"
                >
                  <DeviceColorSwatch :color="device.deviceColor" size="0.7rem" class="q-mr-xs" />
                  {{ deviceRoleShortLabel(device) }}
                </span>
              </div>
              <div class="home-batch-summary__charts">
                <template v-if="b.gravityCount > 0">
              <app-button
                :to="{ name: 'batch-gravity-graph', params: { id: b.id } }"
                variant="positive" dense
                aria-label="Open chart"
              >
                  <q-icon name="show_chart" />
                </app-button>
                </template>

                <template v-if="b.pressureCount > 0">
              <app-button
                :to="{ name: 'batch-pressure-graph', params: { id: b.id } }"
                variant="warning" dense
                aria-label="Open chart"
              >
                  <q-icon name="show_chart" />
                </app-button>
                </template>
              </div>
              <div class="home-batch-summary__age">Age: {{ getBatchAge(b) }}</div>
            </div>
            <div v-if="getPrediction(b)" class="home-batch-summary__prediction">
              Fermentation prediction:
              <span :class="getPrediction(b) === 'DONE' ? 'text-positive text-weight-bold' : ''">{{
                getPrediction(b)
              }}</span>
            </div>
            <div class="home-batch-summary__metrics">
              <div>Gravity: {{ getGravityOG(b) }} - {{ getLastGravity(b) }}</div>
              <div>Pressure {{ getLastPressure(b) }}</div>
              <div>Temperature {{ getLastTemperature(b) }}</div>
            </div>
          </div>
        </AppCard>
      </div>

      <div class="col-md-4">
        <AppCard header="On tap" color="success" title="">
          <template v-if="readyItems.length === 0">
            <div class="text-center">Nothing ready right now</div>
          </template>
          <template v-else>
            <ul class="app-list-group app-list-group--flush">
              <li v-for="item in readyItems" :key="item.id" class="app-list-group__item">
                <div class="row">
                  <div class="col-md-8 text-weight-bold">{{ item.name }}</div>
                  <div class="col-md-4 text-right text-caption">{{ item.readyDate }}</div>
                </div>
              </li>
            </ul>
          </template>
        </AppCard>
      </div>
    </div>

    <HomeSystemStatusCards
      :chamber-temps="chamberTemps"
      :kegmon-taps="kegmonTaps"
      :fermentation-control-list="fermentationControlList"
      :scheduler-status="schedulerStatus"
      :device-count="deviceCount"
      :batch-count="batchCount"
      :vessel-count="vesselCount"
      :tap-count="tapCount"
      :gravity-count="gravityCount"
      :pour-count="pourCount"
      :pressure-count="pressureCount"
    />

    <section class="home-readings-section">
      <div class="row q-col-gutter-md">
        <LatestReadingsFragment title="Latest Gravity Readings" :readings="latestGravityReadings">
          <template #headers>
            <th>Gravity</th>
            <th>Velocity</th>
            <th>Temp</th>
          </template>
          <template #row="{ reading }">
            <td>{{ Number(reading.gravity).toFixed(4) }}</td>
            <td>
              {{ reading.velocity !== null ? Number(reading.velocity).toFixed(4) : '--' }}
            </td>
            <td>{{ getFormattedTemperature(reading.temperature) }}</td>
          </template>
        </LatestReadingsFragment>

        <LatestReadingsFragment title="Latest Pressure Readings" :readings="latestPressureReadings">
          <template #headers>
            <th>Pressure</th>
            <th>Temp</th>
            <th>Battery</th>
          </template>
          <template #row="{ reading }">
            <td>{{ getFormattedPressure(reading.pressure) }}</td>
            <td>{{ getFormattedTemperature(reading.temperature) }}</td>
            <td>{{ Number(reading.battery).toFixed(2) }}V</td>
          </template>
        </LatestReadingsFragment>

        <LatestReadingsFragment title="Latest Pour Readings" :readings="latestPourReadings">
          <template #headers>
            <th>Volume (L)</th>
            <th>Pour (cl)</th>
            <th></th>
            <th></th>
          </template>
          <template #row="{ reading }">
            <td>{{ getFormattedVolume(reading.volumeRemaining) }}</td>
            <td>{{ getFormattedPourVolume(reading.pourAmount * 100) }}</td>
            <td></td>
            <td></td>
          </template>
        </LatestReadingsFragment>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref, computed } from 'vue'
import {
  config,
  global,
  preferences,
  batchStore,
  dashboardStore,
  deviceStore,
  pourStore,
  tapStore,
  vesselStore
} from '@/modules/pinia'
import { apiFetch } from '@/modules/apiClient'
import {
  gravityToPlato,
  getFormattedTemperature,
  getFormattedPressure,
  getFormattedVolume,
  getFormattedPourVolume
} from '@/modules/utils'
import { logDebug, logError } from '@/ui'
import DeviceColorSwatch from '@/components/DeviceColorSwatch.vue'
import HomeSystemStatusCards from '@/components/HomeSystemStatusCards.vue'
import LatestReadingsFragment from '@/fragments/LatestReadingsFragment.vue'

const ticker = ref(null)
const readingsTicker = ref(null)

const activeBatchList = ref([])

const chamberTemps = ref([])
const kegmonTaps = ref([])

const schedulerStatus = ref(null)
const fermentationControlList = ref([])

const batchDeviceRoleOrder = { gravity: 0, pressure: 1, chamber: 2 }

/** Devices assigned to a batch, ordered consistently with the editor. */
function getBatchDevices(batchId) {
  return deviceStore.deviceList
    .filter((device) => device.batchId === batchId)
    .sort((a, b) =>
      (batchDeviceRoleOrder[a.batchRole] ?? Number.MAX_SAFE_INTEGER) -
      (batchDeviceRoleOrder[b.batchRole] ?? Number.MAX_SAFE_INTEGER)
    )
}

function deviceRoleLabel(device) {
  return {
    gravity: 'Gravity',
    pressure: 'Pressure',
    chamber: 'Chamber'
  }[device.batchRole] ?? 'Device'
}

function deviceRoleShortLabel(device) {
  return {
    gravity: 'G',
    pressure: 'P',
    chamber: 'C'
  }[device.batchRole] ?? 'D'
}

const latestGravityReadings = computed(() =>
  dashboardStore.batches
    .filter((b) => b.currentGravity != null)
    .map((b) => ({
      createdAt: b.lastReadingAt,
      gravity: b.currentGravity,
      temperature: b.currentTemp,
      velocity: null,
      battery: b.battery
    }))
    .slice(0, 5)
)

const latestPressureReadings = computed(() =>
  dashboardStore.batches
    .filter((b) => b.currentPressure != null)
    .map((b) => ({
      createdAt: b.lastReadingAt,
      pressure: b.currentPressure,
      temperature: b.currentTemp,
      battery: b.battery
    }))
    .slice(0, 5)
)

const latestPourReadings = ref([])

async function fetchLatestPourReadings() {
  logDebug('HomeView.fetchLatestPourReadings()')

  const results = await Promise.all(
    dashboardStore.vessels.map((v) => pourStore.listPours(v.id))
  )

  latestPourReadings.value = results
    .flatMap((pours) => pours ?? [])
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    .slice(0, 5)
}


const readyItems = computed(() => {
  const batches = dashboardStore.readyBatches.map((b) => ({
    id: b.id,
    name: b.name,
    kind: b.kind,
    readyDate: b.readyDate
  }))
  const vessels = dashboardStore.readyVessels.map((v) => ({
    id: v.id,
    name: v.name,
    kind: v.kind,
    readyDate: v.readyDate
  }))
  return [...batches, ...vessels]
})

const gravityCount = computed(() => {
  let l = 0

  batchStore.batchList.forEach((b) => {
    l += b.gravityCount
  })

  return l
})

const pourCount = computed(() => {
  let l = 0

  vesselStore.vesselList.forEach((v) => {
    l += v.pourCount ?? 0
  })

  return l
})

const pressureCount = computed(() => {
  let l = 0

  batchStore.batchList.forEach((b) => {
    l += b.pressureCount
  })

  return l
})

const deviceCount = computed(() => {
  return deviceStore.deviceList.length
})

const batchCount = computed(() => {
  return batchStore.batchList.length
})

const tapCount = computed(() => {
  return tapStore.tapList.length
})

const vesselCount = computed(() => {
  return vesselStore.vesselList.length
})

function getBatchAge(batch) {
  logDebug('HomeView.getBatchAge()')

  const firstReadingAt = Date.parse(batch?.firstReadingAt ?? '')
  if (Number.isNaN(firstReadingAt)) return ''

  const elapsedMinutes = Math.max(0, Math.floor((Date.now() - firstReadingAt) / 60000))
  const days = Math.floor(elapsedMinutes / (24 * 60))
  const hours = Math.floor((elapsedMinutes % (24 * 60)) / 60)
  const minutes = elapsedMinutes % 60

  return `${days}d ${hours}h ${minutes}m`
}

function getPrediction(batch) {
  logDebug('HomeView.getPrediction()', batch)

  if (!batch) return null

  const prediction = batch.predictions?.[0]
  if (!prediction || prediction.hoursLeft === null || !prediction.createdAt) return null

  const predictionAt = Date.parse(prediction.createdAt)
  if (isNaN(predictionAt)) {
    logError('HomeView.getPrediction() - Invalid prediction timestamp', prediction.createdAt)
    return null
  }

  const elapsedHours = (new Date() - predictionAt) / (1000 * 60 * 60)
  const remainingHours = prediction.hoursLeft - elapsedHours

  if (remainingHours < 0.5) return 'DONE'

  return remainingHours.toFixed(1) + ' h'
}

function getGravityOG(batch) {
  logDebug('HomeView.getGravityOG()')

  if (batch.og != null) {
    if (config.isGravityP) return new Number(gravityToPlato(batch.og)).toFixed(2)
    return new Number(batch.og).toFixed(4)
  }

  return 0.0
}

function getLastGravity(batch) {
  logDebug('HomeView.getLastGravity()')

  if (batch.currentGravity != null) {
    if (config.isGravityP) return new Number(gravityToPlato(batch.currentGravity)).toFixed(2)
    return new Number(batch.currentGravity).toFixed(4)
  }

  return 'N/A'
}

function getLastTemperature(batch) {
  logDebug('HomeView.getLastTemperature()')

  if (batch.currentTemp != null) {
    return getFormattedTemperature(batch.currentTemp)
  }

  return 'N/A'
}

function getLastPressure(batch) {
  logDebug('HomeView.getLastPressure()')

  if (batch.currentPressure != null) {
    return getFormattedPressure(batch.currentPressure)
  }

  return 'N/A'
}

onUnmounted(() => {
  logDebug('HomeView.onUnmounted()')

  if (ticker.value != null) clearInterval(ticker.value)
  if (readingsTicker.value != null) clearInterval(readingsTicker.value)
})

onMounted(async () => {
  logDebug('HomeView.onMounted()')

  activeBatchList.value = []
  fermentationControlList.value = []

  await dashboardStore.fetch()
  activeBatchList.value = dashboardStore.batches
  await fetchLatestPourReadings()

  for (const device of deviceStore.deviceList) {
    if (device.deviceType == 'chamber_controller' && device.id > 0) {
      const result = await deviceStore.getDevice(device.id)
      if (result && result.stepList && result.stepList.length > 0) {
        result.device.fermentationSteps = result.stepList
        fermentationControlList.value.push(result.device)
      }
    }
  }

  ticker.value = setInterval(async () => {
    await Promise.all([fetchScheduler(), fetchChamber(), fetchKegmon()])
  }, 5000)

  readingsTicker.value = setInterval(async () => {
    logDebug('HomeView.readingsTicker()', 'Refreshing dashboard')
    await dashboardStore.fetch()
    activeBatchList.value = dashboardStore.batches
    await fetchLatestPourReadings()
  }, 300000) // 5 minutes
})

async function fetchChamber() {
  logDebug('HomeView.fetchChamber()')

  if (!preferences.showChamberTemps) {
    chamberTemps.value = []
    return
  }

  const chamberList = deviceStore.deviceList.filter((d) => {
    return d.deviceType == 'chamber_controller'
  })

  try {
    const results = await Promise.allSettled(
      chamberList.map(async (device) => {
        return deviceStore.proxyRequest(
          'GET',
          device.url + 'api/status',
          'Content-Type: application/json',
          '',
          { noErrorNotify: true }
        )
      })
    )

    chamberTemps.value = results.map((result, index) => {
      if (result.status === 'fulfilled' && result.value != null) {
        return result.value
      } else {
        const device = chamberList[index]
        logError(
          'HomeView.fetchChamber()',
          `Failed to fetch chamber data from ${device.mdns} (${device.url})`,
          result.status === 'rejected' ? result.reason : undefined
        )
        return {
          mdns: device.mdns,
          url: device.url,
          error: 'Failed to fetch data'
        }
      }
    })
  } catch (err) {
    logError('HomeView.fetchChamber()', 'Unexpected error fetching chamber data', err)
  }
}

async function fetchKegmon() {
  logDebug('HomeView.fetchKegmon()')

  if (!preferences.showKegmonTaps) {
    kegmonTaps.value = []
    return
  }

  const kegmonList = deviceStore.deviceList.filter((d) => {
    return d.deviceType == 'kegmon'
  })

  try {
    const results = await Promise.allSettled(
      kegmonList.map(async (device) => {
        return deviceStore.proxyRequest(
          'GET',
          device.url + 'api/status',
          'Content-Type: application/json',
          '',
          { noErrorNotify: true }
        )
      })
    )

    kegmonTaps.value = results.map((result, index) => {
      if (result.status === 'fulfilled' && result.value != null) {
        return result.value
      } else {
        const device = kegmonList[index]
        logError(
          'HomeView.fetchKegmon()',
          `Failed to fetch kegmon data from ${device.mdns} (${device.url})`,
          result.status === 'rejected' ? result.reason : undefined
        )
        return {
          mdns: device.mdns,
          url: device.url,
          error: 'Failed to fetch data'
        }
      }
    })
  } catch (err) {
    logError('HomeView.fetchKegmon()', 'Unexpected error fetching kegmon data', err)
  }
}

async function fetchScheduler() {
  logDebug('HomeView.fetchScheduler()')

  apiFetch('GET', 'system/scheduler')
    .then((res) => {
      return res.json()
    })
    .then((json) => {
      logDebug('HomeView.fetchScheduler()', 'Scheduler status:', json)
      schedulerStatus.value = json
    })
    .catch((err) => {
      logError('HomeView.fetchScheduler()', err)
    })
}
</script>

<style scoped>
.home-readings-section {
  margin-top: 16px;
}
</style>
