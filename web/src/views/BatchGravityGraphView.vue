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
    <div class="row justify-between items-center">
      <p class="text-h6 q-mb-none">Batch Gravity Graph - '{{ batchName }}'</p>
      <app-button
        type="button"
        variant="outline-secondary" dense
        :aria-expanded="showStats"
        aria-controls="gravity-graph-stats-collapse"
        @click="showStats = !showStats"
      >
        {{ showStats ? 'Hide stats' : 'Show stats' }}
      </app-button>
    </div>
    <hr />

    <div class="row">
      <div
        id="gravity-graph-stats-collapse"
        class="app-collapse col-md-12"
        :class="{ show: showStats }"
      >
        <GravityStatsFragment v-model="gravityStats"></GravityStatsFragment>
      </div>

      <div class="row" v-if="gravityList != null">
        <div class="col-md-2">
          <AppInputNumber
            v-model="infoOG"
            label="Filter OG"
            :step="stepFor('gravity')"
            :disabled="global.disabled"
          ></AppInputNumber>
        </div>
        <div class="col-md-2">
          <AppInputNumber
            v-model="infoFG"
            label="Filter FG"
            :step="stepFor('gravity')"
            :disabled="global.disabled"
          ></AppInputNumber>
        </div>

        <div class="col-md-1">
          <AppField label="&nbsp;"
            ><app-button
              @click="apply"
              type="button"
              variant="secondary" dense
              :disabled="global.disabled"
            >
              Apply
            </app-button></AppField
          >
        </div>
      </div>

      <div class="col-md-11">
        <canvas id="gravityChart"></canvas>
      </div>
      <div class="col-md-1" v-if="gravityList != null">
        <!-- Right toolbar for controlling contents -->

        <div class="row q-pa-sm">
          <p class="text-weight-bold">Data</p>
          <div class="app-button-group" role="group" aria-label="Vertical button group">
            <app-button
              @click="filterGravity"
              type="button"
              variant="outline-secondary" dense
              :disabled="global.disabled"
            >
              Gravity
            </app-button>
            <app-button
              @click="filterTemp"
              type="button"
              variant="outline-secondary" dense
              :disabled="global.disabled"
            >
              Temp
            </app-button>
            <app-button
              @click="filterDevice"
              type="button"
              variant="outline-secondary" dense
              :disabled="global.disabled"
            >
              Device
            </app-button>
            <app-button
              @click="filterVelocity"
              type="button"
              variant="outline-secondary" dense
              :disabled="global.disabled"
            >
              Velocity
            </app-button>
          </div>
        </div>

        <div class="row q-pa-sm">
          <p class="text-weight-bold">Time</p>
          <div class="app-button-group" role="group" aria-label="Vertical button group">
            <app-button
              @click="filterAll"
              type="button"
              variant="outline-secondary" dense
              :disabled="global.disabled"
            >
              All
            </app-button>
            <app-button
              @click="filter24h"
              type="button"
              variant="outline-secondary" dense
              :disabled="global.disabled"
            >
              24h
            </app-button>
            <app-button
              @click="filter48h"
              type="button"
              variant="outline-secondary" dense
              :disabled="global.disabled"
            >
              48h
            </app-button>
            <app-button
              @click="filter7d"
              type="button"
              variant="outline-secondary" dense
              :disabled="global.disabled"
            >
              7d
            </app-button>
          </div>
        </div>
        <div class="row q-pa-sm">
          <p class="text-weight-bold">Filters</p>
          <div class="app-button-group" role="group" aria-label="Vertical button group">
            <app-button
              @click="filterAll"
              type="button"
              variant="outline-secondary" dense
              :disabled="global.disabled"
            >
              Clear
            </app-button>

            <input
              v-model="lowpass"
              class="app-native-input app-native-input--dense"
              type="number"
              :disabled="global.disabled"
            />

            <app-button
              @click="filterLowPass"
              type="button"
              variant="outline-secondary" dense
              :disabled="global.disabled"
            >
              Lowpass
            </app-button>
          </div>
        </div>
        <div class="row q-pa-sm">
          <p class="text-weight-bold">Points</p>
          <p>{{ currentDataCount }}</p>
        </div>
      </div>
    </div>

    <template v-if="gravityList != null">
      <div class="row q-col-gutter-sm">
        <div class="col-md-12"></div>
        <router-link :to="{ name: 'batch-list' }">
          <app-button type="button" variant="secondary" class="app-width-2">
            <q-icon name="list" />
            Batch list
          </app-button> </router-link
        >&nbsp;
      </div>
    </template>

    <template v-else>
      <div class="row q-col-gutter-sm">
        <div class="col-md-12"></div>
        <div class="col-md-12">
          <router-link :to="{ name: 'batch-list' }">
            <app-button type="button" variant="secondary" class="app-width-2">Batch list</app-button> </router-link
          >&nbsp;
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { Chart, registerables } from 'chart.js'
import zoomPlugin from 'chartjs-plugin-zoom'
import 'date-fns'
import 'chartjs-adapter-date-fns'
import { config, gravityStore, batchStore, global } from '@/modules/pinia'
import router from '@/modules/router'
import { getGravityDataAnalytics } from '@/modules/utils'
import { stepFor } from '@/modules/useUnitConversion'
import { logDebug, logError } from '@/ui'
import { localDateEnd, localDateStart, localTimestampParts, shiftLocalDate } from '@/core'
import {
  mapGravityData,
  mapBatteryData,
  mapTemperatureData,
  mapAlcoholData,
  mapChamberData,
  mapGravityVelocityData,
  applyLowPass
} from '@/modules/gravityChartData'
import { configureGravityChart } from '@/modules/gravityChartConfig'

let chart = null // Do not use ref for this, will cause stack overflow...

Chart.register(...registerables, zoomPlugin)

const infoFirstDay = ref(null)
const infoLastDay = ref(null)
const infoOG = ref(null)
const infoFG = ref(null)
const currentDataCount = ref(0)
const batchName = ref('')

const lowpass = ref(4)

watch(infoFirstDay, async (selected) => {
  logDebug('BatchGravityGraphView.watch(infoFirstDay)', selected)
  chart.options.scales.x.min = localDateStart(selected)
  chart.update()
})

watch(infoLastDay, async (selected) => {
  logDebug('BatchGravityGraphView.watch(infoLastDay)', selected)
  chart.options.scales.x.max = localDateEnd(selected)
  chart.update()
})

const showStats = ref(true)
const gravityList = ref(null)
const gravityStats = ref(null)

const gravityData = ref([])
const gravityVelocityData = ref([])
const gravityVelocityData1 = ref([])
const alcoholData = ref([])
const batteryData = ref([])
const temperatureData = ref([])
const chamberData = ref([])

const graphOptions = ref({
  gravity: true,
  temperature: true,
  battery: false,
  alcohol: true,
  chamber: false,
  velocity: false
})

function filterGravity() {
  logDebug('BatchGravityGraphView.filterGravity()')
  graphOptions.value = {
    gravity: true,
    temperature: true,
    battery: false,
    alcohol: true,
    chamber: false,
    velocity: false
  }
  apply()
}

function filterTemp() {
  logDebug('BatchGravityGraphView.filterTemp()')
  graphOptions.value = {
    gravity: false,
    temperature: true,
    battery: false,
    alcohol: false,
    chamber: true,
    velocity: false
  }
  apply()
}

function filterDevice() {
  logDebug('BatchGravityGraphView.filterDevice()')
  graphOptions.value = {
    gravity: false,
    temperature: false,
    battery: true,
    alcohol: false,
    chamber: false,
    velocity: false
  }
  apply()
}

function filterVelocity() {
  logDebug('BatchGravityGraphView.filterVelocity()')
  graphOptions.value = {
    gravity: true,
    temperature: false,
    battery: false,
    alcohol: false,
    chamber: false,
    velocity: true
  }
  apply()
}

onMounted(async () => {
  logDebug('BatchGravityGraphView.onMounted()')

  gravityList.value = null
  const batchId = router.currentRoute.value.params.id
  if (typeof batchId !== 'string' || !batchId || batchId === 'undefined' || batchId === 'null') {
    global.messageError = 'A valid batch is required to view gravity readings'
    return
  }

  const b = await batchStore.getBatch(batchId)
  if (b) batchName.value = b.name
  else global.messageError = 'Failed to load batch ' + batchId

  const gl = await gravityStore.getGravityListForBatch(batchId)
  if (gl) {
    gravityList.value = gl

    // Calculate statistics for the full dataset
    gravityStats.value = getGravityDataAnalytics(gravityList.value)
    infoFirstDay.value = gravityStats.value.date.firstDate
    infoLastDay.value = gravityStats.value.date.lastDate
    infoOG.value = Number.parseFloat(
      new Number(gravityStats.value.gravity.max).toFixed(config.isGravitySG ? 3 : 2)
    )
    infoFG.value = Number.parseFloat(
      new Number(gravityStats.value.gravity.min).toFixed(config.isGravitySG ? 3 : 2)
    )

    gravityList.value.sort((a, b) => Date.parse(a.created) - Date.parse(b.created))

    try {
      const chartOptions = {
        type: 'line',
        data: { datasets: [] },
        options: {
          scales: {},
          animation: false,
          plugins: {
            tooltip: {
              enabled: true
            },
            zoom: {
              pan: {
                enabled: true,
                mode: 'xy'
              },
              zoom: {
                wheel: {
                  enabled: true
                },
                pinch: {
                  enabled: true
                },
                zoom: {
                  mode: 'xy'
                }
              }
            }
          }
        }
      }

      logDebug('BatchGravityGraphView.onMounted()', 'Creating chart')

      if (document.getElementById('gravityChart') == null) {
        logError('BatchGravityGraphView.onMounted()', 'Unable to find the chart canvas')
      } else {
        // Create the chart
        chart = new Chart(document.getElementById('gravityChart').getContext('2d'), chartOptions)
        updateDataSet()
        chart.update()
        setTimeout(() => {
          filterAll()
        }, 100) // Quick fix so that data is always shown
      }
    } catch (err) {
      logDebug('BatchGravityGraphView.onMounted()', err)
    }
  }
})

function apply() {
  logDebug('BatchGravityGraphView.apply()')
  updateDataSet()
  chart.update()
}

function updateDataSet() {
  logDebug('BatchGravityGraphView.updateDataSet()')

  const filteredGravityList = gravityList.value.filter(
    (g) => !g.excluded && g.gravity >= infoFG.value && g.gravity <= infoOG.value
  )

  gravityStats.value = getGravityDataAnalytics(filteredGravityList)

  gravityData.value = mapGravityData(filteredGravityList)
  batteryData.value = mapBatteryData(filteredGravityList)
  temperatureData.value = mapTemperatureData(filteredGravityList)
  alcoholData.value = mapAlcoholData(filteredGravityList)
  chamberData.value = mapChamberData(filteredGravityList)

  const { velocity, development } = mapGravityVelocityData(filteredGravityList)
  gravityVelocityData.value = velocity
  gravityVelocityData1.value = development

  currentDataCount.value = gravityData.value.length
  configureGravityChart(
    chart,
    graphOptions.value,
    {
      gravity: gravityData.value,
      temperature: temperatureData.value,
      chamber: chamberData.value,
      battery: batteryData.value,
      alcohol: alcoholData.value,
      velocity: gravityVelocityData.value,
      development: gravityVelocityData1.value
    },
    gravityStats.value
  )
}

function filter24h() {
  logDebug('BatchGravityGraphView.filter24h()')

  infoFirstDay.value = shiftLocalDate(localTimestampParts(gravityStats.value.date.last).date, -1)
  updateDataSet()
  chart.update()
}

function filter48h() {
  logDebug('BatchGravityGraphView.filter48h()')

  infoFirstDay.value = shiftLocalDate(localTimestampParts(gravityStats.value.date.last).date, -2)
  updateDataSet()
  chart.update()
}

function filter7d() {
  logDebug('BatchGravityGraphView.filter7d()')

  const lastDay = localTimestampParts(gravityStats.value.date.last).date
  infoFirstDay.value = shiftLocalDate(lastDay, -7)
  infoLastDay.value = lastDay
  updateDataSet()
  chart.update()
}

function filterAll() {
  logDebug('BatchGravityGraphView.filterAll()')

  infoFirstDay.value = localTimestampParts(gravityStats.value.date.first).date
  infoLastDay.value = localTimestampParts(gravityStats.value.date.last).date
  updateDataSet()
  chart.update()
}

function filterLowPass() {
  logDebug('BatchGravityGraphView.filterLowPass()', chart.data.datasets)

  for (let i = 0; i < chart.data.datasets.length; i++) {
    switch (chart.data.datasets[i].label) {
      case 'Gravity':
      case 'Chamber':
      case 'Temperature':
      case 'Battery':
      case 'Alcohol':
        chart.data.datasets[i].data = applyLowPass(chart.data.datasets[i].data, lowpass.value)
        break
      case 'Velocity':
        // Dont filter this.
        break
    }
  }

  currentDataCount.value = chart.data.datasets[0].data.length
  chart.update()
}
</script>
