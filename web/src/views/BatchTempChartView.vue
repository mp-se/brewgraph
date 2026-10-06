<!--
  Copyright (c) 2024-2026 Magnus Persson
  SPDX-License-Identifier: GPL-3.0-only
  BrewGraph — https://github.com/mp-se/brewgraph
-->

<template>
  <div class="app-page">
    <p></p>
    <p class="text-h6 q-mb-none">Batch Temperature Chart - '{{ batchName }}'</p>
    <hr />

    <div class="row" v-if="tempData.length > 0">
      <div class="col-md-11">
        <canvas id="tempChart"></canvas>
      </div>
      <div class="col-md-1">
        <div class="row q-pa-sm">
          <p class="text-weight-bold">Time</p>
          <div class="app-button-group" role="group">
            <app-button @click="filterAll()" type="button" variant="outline-secondary" dense :disabled="global.disabled">All</app-button>
            <app-button @click="filter24h()" type="button" variant="outline-secondary" dense :disabled="global.disabled">24h</app-button>
            <app-button @click="filter48h()" type="button" variant="outline-secondary" dense :disabled="global.disabled">48h</app-button>
            <app-button @click="filter7d()"  type="button" variant="outline-secondary" dense :disabled="global.disabled">7d</app-button>
          </div>
        </div>
        <div class="row q-pa-sm">
          <p class="text-weight-bold">Points</p>
          <p>{{ tempData.length }}</p>
        </div>
      </div>
    </div>

    <div v-else-if="loaded" class="app-alert app-alert--info">No temperature readings found for this batch.</div>

    <div class="row q-col-gutter-sm q-mt-sm">
      <div class="col-md-12">
        <router-link :to="{ name: 'batch-list' }">
          <app-button type="button" variant="secondary">
            <q-icon name="list" /> Batch list
          </app-button>
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { Chart, registerables } from 'chart.js'
import zoomPlugin from 'chartjs-plugin-zoom'
import 'date-fns'
import 'chartjs-adapter-date-fns'
import { batchStore, global, config } from '@/modules/pinia'
import { apiJson } from '@/modules/apiClient'
import router from '@/modules/router'
import { tempToF } from '@/modules/utils'
import { logDebug, logError } from '@/ui'

Chart.register(...registerables, zoomPlugin)

let chart = null // Do not use ref for this, will cause stack overflow...

const batchName = ref('')
const tempData = ref([])
const loaded = ref(false)

let firstDate = null
let lastDate = null

onMounted(async () => {
  logDebug('BatchTempChartView.onMounted()')

  const batchId = router.currentRoute.value.params.id
  const b = await batchStore.getBatch(batchId)
  if (b) batchName.value = b.name
  else global.messageError = 'Failed to load batch ' + batchId

  const rows = await apiJson('GET', `batches/${batchId}/temp/chart`, undefined, { busy: false })
  loaded.value = true

  if (!rows || rows.length === 0) return

  tempData.value = rows.map((r) => ({
    x: r.t,
    y: parseFloat(new Number(config.isTempC ? r.temp : tempToF(r.temp)).toFixed(2))
  }))

  rows.sort((a, b) => Date.parse(a.t) - Date.parse(b.t))
  firstDate = rows[0].t
  lastDate = rows[rows.length - 1].t

  // The canvas only exists once the v-if above has re-rendered.
  await nextTick()
  if (document.getElementById('tempChart') == null) {
    logError('BatchTempChartView.onMounted()', 'Unable to find chart canvas')
    return
  }

  try {
    chart = new Chart(document.getElementById('tempChart').getContext('2d'), {
      type: 'line',
      data: {
        datasets: [
          {
            label: `Temperature (°${config.isTempC ? 'C' : 'F'})`,
            data: tempData.value,
            borderColor: 'steelblue',
            backgroundColor: 'steelblue',
            pointRadius: 3,
            cubicInterpolationMode: 'monotone',
            tension: 0.4
          }
        ]
      },
      options: {
        animation: false,
        scales: {
          x: {
            type: 'time',
            time: {
              unit: 'hour',
              displayFormats: { hour: 'E HH:mm', day: 'HH:mm' }
            },
            min: firstDate,
            max: lastDate
          },
          y: {
            title: { display: true, text: `Temperature (°${config.isTempC ? 'C' : 'F'})` }
          }
        },
        plugins: {
          tooltip: { enabled: true },
          zoom: {
            pan: { enabled: true, mode: 'xy' },
            zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'xy' }
          }
        }
      }
    })
  } catch (err) {
    logDebug('BatchTempChartView.onMounted()', err)
  }
})

function setRange(from, to) {
  if (!chart) return
  chart.options.scales.x.min = from
  chart.options.scales.x.max = to
  chart.update()
}

function filterAll()  { setRange(firstDate, lastDate) }
function filter24h()  { setRange(new Date(Date.parse(lastDate) - 86400000 * 1).toISOString(), lastDate) }
function filter48h()  { setRange(new Date(Date.parse(lastDate) - 86400000 * 2).toISOString(), lastDate) }
function filter7d()   { setRange(new Date(Date.parse(lastDate) - 86400000 * 7).toISOString(), lastDate) }
</script>
