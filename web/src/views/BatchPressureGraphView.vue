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
      <p class="text-h6 q-mb-none">Batch Pressure Graph - '{{ batchName }}'</p>
      <app-button
        type="button"
        variant="outline-secondary" dense
        :aria-expanded="showStats"
        aria-controls="pressure-graph-stats-collapse"
        @click="showStats = !showStats"
      >
        {{ showStats ? 'Hide stats' : 'Show stats' }}
      </app-button>
    </div>
    <hr />

    <div class="row">
      <div
        id="pressure-graph-stats-collapse"
        class="app-collapse col-md-12"
        :class="{ show: showStats }"
      >
        <PressureStatsFragment v-model="pressureStats"></PressureStatsFragment>
      </div>
      <!-- 

      <div class="row" v-if="gravityList != null">

        <div class="col-md-2" v-if="graphOptions.velocity">
          <AppInputNumber
            v-model="outlierLimit"
            label="Outlier limit"
            step="0.0001"
            :disabled="global.disabled"
          ></AppInputNumber>
        </div>

        <div class="col-md-1">
          <AppField label="&nbsp;"
            ><app-button
              @click="apply()"
              type="button"
              variant="secondary" dense
              :disabled="global.disabled"
            >
              Apply
            </app-button></AppField
          >
        </div>
      </div> -->

      <div class="col-md-11">
        <canvas id="pressureChart"></canvas>
      </div>
      <div class="col-md-1" v-if="pressureList != null">
        <!-- Right toolbar for controlling contents -->

        <div class="row q-pa-sm">
          <p class="text-weight-bold">Data</p>
          <div class="app-button-group" role="group" aria-label="Vertical button group">
            <app-button
              @click="filterPressure()"
              type="button"
              variant="outline-secondary" dense
              :disabled="global.disabled"
            >
              Pressure
            </app-button>
            <app-button
              @click="filterTemp()"
              type="button"
              variant="outline-secondary" dense
              :disabled="global.disabled"
            >
              Temp
            </app-button>
          </div>
        </div>

        <div class="row q-pa-sm">
          <p class="text-weight-bold">Time</p>
          <div class="app-button-group" role="group" aria-label="Vertical button group">
            <app-button
              @click="filterAll()"
              type="button"
              variant="outline-secondary" dense
              :disabled="global.disabled"
            >
              All
            </app-button>
            <app-button
              @click="filter24h()"
              type="button"
              variant="outline-secondary" dense
              :disabled="global.disabled"
            >
              24h
            </app-button>
            <app-button
              @click="filter48h()"
              type="button"
              variant="outline-secondary" dense
              :disabled="global.disabled"
            >
              48h
            </app-button>
            <app-button
              @click="filter7d()"
              type="button"
              variant="outline-secondary" dense
              :disabled="global.disabled"
            >
              7d
            </app-button>
          </div>
        </div>
        <div class="row q-pa-sm">
          <p class="text-weight-bold">Points</p>
          <p>{{ currentDataCount }}</p>
        </div>
      </div>
    </div>

    <template v-if="pressureList != null">
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
import { config, pressureStore, batchStore, global } from '@/modules/pinia'
import { getPressureDataAnalytics, pressureToBAR, pressureToKPA, tempToF } from '@/modules/utils'
import router from '@/modules/router'
import { logDebug, logError } from '@/ui'
import { localDateEnd, localDateStart, localTimestampParts, shiftLocalDate } from '@/core'

let chart = null // Do not use ref for this, will cause stack overflow...

Chart.register(...registerables, zoomPlugin)

const infoFirstDay = ref(null)
const infoLastDay = ref(null)
const currentDataCount = ref(0)
const batchName = ref('')

watch(infoFirstDay, async (selected) => {
  logDebug('BatchPressureGraphView.watch(infoFirstDay)', selected)
  chart.options.scales.x.min = localDateStart(selected)
  chart.update()
})

watch(infoLastDay, async (selected) => {
  logDebug('BatchPressureGraphView.watch(infoLastDay)', selected)
  chart.options.scales.x.max = localDateEnd(selected)
  chart.update()
})

const showStats = ref(true)
const pressureList = ref(null)
const pressureStats = ref(null)

const pressureData = ref([])
const batteryData = ref([])
const temperatureData = ref([])

const graphOptions = ref({
  pressure: true,
  temperature: true,
  battery: false
})

function filterPressure() {
  logDebug('BatchPressureGraphView.filterPressure()')
  graphOptions.value = {
    pressure: true,
    temperature: true,
    battery: false
  }
  apply()
}

function filterTemp() {
  logDebug('BatchPressureGraphView.filterTemp()')
  graphOptions.value = {
    pressure: false,
    temperature: true,
    battery: false
  }
  apply()
}

onMounted(async () => {
  logDebug('BatchPressureGraphView.onMounted()')

  pressureList.value = null

  const batch = await batchStore.getBatch(router.currentRoute.value.params.id)
  if (batch) batchName.value = batch.name
  else global.messageError = 'Failed to load batch ' + router.currentRoute.value.params.id

  const gl = await pressureStore.getPressureListForBatch(router.currentRoute.value.params.id)
  if (gl && gl.length > 0) {
    pressureList.value = gl

    // Calculate statistics for the full dataset
    pressureStats.value = getPressureDataAnalytics(pressureList.value)
    infoFirstDay.value = pressureStats.value.date.firstDate
    infoLastDay.value = pressureStats.value.date.lastDate

    pressureList.value.sort((a, b) => Date.parse(a.created) - Date.parse(b.created))

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
                mode: 'xy'
              }
            }
          }
        }
      }

      logDebug('BatchPressureGraphView.onMounted()', 'Creating chart')

      if (document.getElementById('pressureChart') == null) {
        logError('BatchPressureGraphView.onMounted()', 'Unable to find the chart canvas')
      } else {
        // Create the chart
        chart = new Chart(document.getElementById('pressureChart').getContext('2d'), chartOptions)
        updateDataSet()
        chart.update()
        setTimeout(() => {
          filterAll()
        }, 100) // Quick fix so that data is always shown
      }
    } catch (err) {
      logDebug('BatchPressureGraphView.onMounted()', err)
    }
  }
})

function mapPressureData(pList) {
  const result = []

  pList.forEach((p) => {
    result.push({
      x: p.created,
      y: parseFloat(
        new Number(
          config.isPressurePSI
            ? p.pressure
            : config.isPressureBAR
              ? pressureToBAR(p.pressure)
              : pressureToKPA(p.pressure)
        ).toFixed(2)
      )
    })
  })

  return result
}

function mapBatteryData(pList) {
  const result = []

  pList.forEach((p) => {
    if (p.battery !== null) {
      result.push({
        x: p.created,
        y: parseFloat(new Number(p.battery).toFixed(2))
      })
    }
  })

  return result
}

function mapTemperatureData(pList) {
  const result = []

  pList.forEach((p) => {
    // -273 refers to invalid temperature or missing temperature sensor
    if (p.temperature !== null && p.temperature >= -270) {
      result.push({
        x: p.created,
        y: parseFloat(
          new Number(config.isTempC ? p.temperature : tempToF(p.temperature)).toFixed(2)
        )
      })
    }
  })

  return result
}

function apply() {
  logDebug('BatchPressureGraphView.apply()')
  updateDataSet()
  chart.update()
}

function updateDataSet() {
  logDebug('BatchPressureGraphView.updateDataSet()')

  const filteredPressureList = pressureList.value.filter((p) => !p.excluded)

  pressureStats.value = getPressureDataAnalytics(filteredPressureList)

  pressureData.value = mapPressureData(filteredPressureList)
  batteryData.value = mapBatteryData(filteredPressureList)
  temperatureData.value = mapTemperatureData(filteredPressureList)

  currentDataCount.value = pressureData.value.length
  configureChart(graphOptions.value)
}

function configureChart(config) {
  chart.data.datasets = []

  if (config.pressure) {
    chart.data.datasets.push({
      label: 'Pressure',
      data: pressureData.value,
      borderColor: 'green',
      backgroundColor: 'green',
      yAxisID: 'yPressure',
      pointRadius: 0,
      cubicInterpolationMode: 'monotone',
      tension: 0.4
    })
  }

  if (config.pressure) {
    chart.config.options.scales.yPressure = {
      type: 'linear',
      position: 'left',
      title: {
        display: true,
        text: 'Pressure'
      }
    }
  } else {
    if (chart.config.options.scales.yPressure) {
      delete chart.config.options.scales.yPressure
    }
  }

  if (config.temperature) {
    chart.data.datasets.push({
      label: 'Temperature',
      data: temperatureData.value,
      borderColor: 'blue',
      backgroundColor: 'blue',
      yAxisID: 'yTemp',
      pointRadius: 0,
      cubicInterpolationMode: 'monotone',
      tension: 0.4
    })
  }

  if (config.temperature) {
    chart.config.options.scales.yTemp = {
      type: 'linear',
      position: 'right',
      title: {
        display: true,
        text: 'Temperataure'
      }
    }
  } else {
    if (chart.config.options.scales.yTemp) {
      delete chart.config.options.scales.yTemp
    }
  }

  if (config.battery) {
    chart.data.datasets.push({
      label: 'Battery',
      data: batteryData.value,
      borderColor: 'orange',
      backgroundColor: 'orange',
      yAxisID: 'yVolt',
      pointRadius: 0,
      cubicInterpolationMode: 'monotone',
      tension: 0.4
    })
  }

  if (config.battery) {
    chart.config.options.scales.yVolt = {
      type: 'linear',
      position: 'right',
      title: {
        display: true,
        text: 'Voltage'
      }
    }
  } else {
    if (chart.config.options.scales.yVolt) {
      delete chart.config.options.scales.yVolt
    }
  }

  chart.config.options.scales.x = {
    type: 'time',
    time: {
      unit: 'hour',
      displayFormats: {
        hour: 'E HH:mm',
        day: 'HH:mm',
        week: 'E HH:mm',
        month: 'd HH:mm'
      }
    },
    min: pressureStats.value.date.first,
    max: pressureStats.value.date.last
  }

  logDebug('AAAA:', chart.getInitialScaleBounds())
  logDebug('AAAA:', chart.getZoomedScaleBounds(), chart.isZoomedOrPanned())
}

function filter24h() {
  logDebug('BatchPressureGraphView.filter24h()')

  infoFirstDay.value = shiftLocalDate(localTimestampParts(pressureStats.value.date.last).date, -1)
  updateDataSet()
  chart.update()
}

function filter48h() {
  logDebug('BatchPressureGraphView.filter48h()')

  infoFirstDay.value = shiftLocalDate(localTimestampParts(pressureStats.value.date.last).date, -2)
  updateDataSet()
  chart.update()
}

function filter7d() {
  logDebug('BatchPressureGraphView.filter7d()')

  const lastDay = localTimestampParts(pressureStats.value.date.last).date
  infoFirstDay.value = shiftLocalDate(lastDay, -7)
  infoLastDay.value = lastDay
  updateDataSet()
  chart.update()
}

function filterAll() {
  logDebug('BatchPressureGraphView.filterAll()')

  infoFirstDay.value = localTimestampParts(pressureStats.value.date.first).date
  infoLastDay.value = localTimestampParts(pressureStats.value.date.last).date
  updateDataSet()
  chart.update()
}
</script>
