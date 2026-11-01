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
  <div class="app-page pour-history">
    <p></p>
    <p class="text-h6">Pour List - '{{ vesselName }}'</p>
    <hr />

    <div v-if="status === 'error'" class="app-alert pour-history__error" role="alert">
      <span>Failed to load the pours.</span>
      <app-button type="button" variant="outline-secondary" dense @click="load()">Retry</app-button>
    </div>

    <div v-else-if="status === 'loading'" aria-busy="true" aria-label="Loading pour history">
      <div class="pour-history__skeleton" data-test="chart-skeleton"></div>
    </div>

    <template v-else>
      <p v-if="records.length === 0" class="text-grey-7">No pours recorded yet.</p>

      <template v-else>
        <div class="pour-history__charts">
          <p id="pour-summary" class="pour-history__summary" data-test="summary">
            {{ summaryText }}
          </p>
          <p v-if="truncated" class="text-grey-7" data-test="truncated">
            Showing the latest {{ POUR_CHART_LIMIT }} pours
          </p>

          <div class="app-button-group q-mb-md" role="group" aria-label="Chart views" data-test="chart-views">
            <app-button
              v-for="view in CHART_VIEWS"
              :key="view.value"
              type="button"
              :variant="chartView === view.value ? 'primary' : 'outline-secondary'"
              :aria-pressed="chartView === view.value"
              :data-test="`view-${view.value}`"
              @click="chartView = view.value"
            >
              {{ view.label }}
            </app-button>
          </div>

          <div class="pour-history__ranges q-mb-sm" role="group" aria-label="Time range" data-test="ranges">
            <app-button
              v-for="range in POUR_RANGES"
              :key="range.label"
              type="button"
              dense
              :variant="rangeHours === range.hours ? 'primary' : 'outline-secondary'"
              :aria-pressed="rangeHours === range.hours"
              :data-test="`range-${range.label}`"
              @click="selectRange(range.hours)"
            >
              {{ range.label }}
            </app-button>
            <app-button
              v-if="chartView === 'level' && hasChartData"
              type="button"
              dense
              variant="outline-secondary"
              data-test="reset-zoom"
              @click="resetZoom"
            >
              Reset zoom
            </app-button>
          </div>

          <p v-if="!hasChartData" class="text-grey-7" data-test="range-empty">No pours in this range</p>
          <div v-else class="pour-history__chart">
            <canvas
              :key="chartView"
              ref="chartCanvas"
              role="img"
              :aria-label="chartView === 'level' ? 'Remaining volume after each pour' : 'Volume poured per day'"
              aria-describedby="pour-summary"
            ></canvas>
          </div>
        </div>

        <section
          v-for="group in pagedGroups"
          :key="group.day"
          class="pour-history__day"
          data-test="day-group"
        >
          <h3 class="text-subtitle1 text-weight-medium q-mb-xs">
            {{ dayLabel(group.day) }} — {{ group.count }} {{ group.count === 1 ? 'pour' : 'pours' }},
            {{ formatVolume(group.litres) }}
          </h3>
          <q-markup-table class="app-table app-table--striped">
            <thead>
              <tr>
                <th scope="col">Time</th>
                <th scope="col">Pour</th>
                <th scope="col">Level after</th>
                <th scope="col">Source</th>
                <th scope="col">Excluded</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="p in group.pours"
                :key="p.id"
                :class="{ 'pour-history__row--excluded': p.excluded }"
              >
                <td class="text-body1">{{ formatTime(p.createdAt) }}</td>
                <td class="text-body1">{{ formatVolume(p.pourAmount) }}</td>
                <td class="text-body1">{{ formatVolume(p.volumeRemaining) }}</td>
                <td class="text-body1">{{ p.isManual ? 'Manual' : 'Auto-detected' }}</td>
                <td>
                  <q-toggle
                    dense
                    :model-value="p.excluded"
                    :disable="global.disabled"
                    title="Exclude this pour"
                    aria-label="Exclude this pour"
                    @update:model-value="toggleExcluded(p)"
                  />
                </td>
              </tr>
            </tbody>
          </q-markup-table>
        </section>
      </template>
    </template>

    <div class="row items-center app-list-actions">
      <div class="col-12 col-md app-list-actions__primary">
        <app-button
          outline
          color="primary"
          :to="{ name: 'vessel', params: { id: route.params.id } }"
        >
          <q-icon name="arrow_back" class="q-mr-xs" />
          Back
        </app-button>
      </div>
      <div v-if="totalPages > 1" class="col-12 col-md-auto row justify-end">
        <nav aria-label="Pour list pagination">
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
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Chart, registerables } from 'chart.js'
import zoomPlugin from 'chartjs-plugin-zoom'
import 'date-fns'
import 'chartjs-adapter-date-fns'
import {
  POUR_CHART_LIMIT,
  POUR_RANGES,
  dailyTotals,
  groupPoursByDay,
  levelSeries,
  poursInRange,
  summarizePours,
  volumeLtoUKGallon,
  volumeLtoUSGallon
} from '@brewgraph/core'
import { config, global, pourStore, preferences, vesselStore } from '@/modules/pinia'
import { logDebug } from '@/ui'

Chart.register(...registerables, zoomPlugin)

const route = useRoute()
const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
const GROUPS_PER_PAGE = 10

const vessel = ref(null)
const vesselName = computed(() => vessel.value?.name ?? '')

const CHART_VIEWS = [
  { label: 'Level', value: 'level' },
  { label: 'Per day', value: 'daily' }
]
const chartView = ref('level')
const rangeHours = ref(null)

const status = ref('loading')
const records = ref([])
const currentPage = ref(1)
const chartCanvas = ref(null)

// The chart instance stays outside Vue reactivity.
let chart = null
let loadId = 0

// The API serialises UTC timestamps without an offset.
function utcIso(createdAt) {
  const text = String(createdAt ?? '')
  return text.includes('T') && !/(Z|[+-]\d{2}:?\d{2})$/i.test(text) ? text + 'Z' : text
}

function toRecord(p) {
  return {
    id: p.id,
    createdAt: utcIso(p.createdAt),
    pourAmount: p.pourAmount,
    volumeRemaining: p.volumeRemaining,
    isManual: p.isManual,
    excluded: p.excluded
  }
}

const sortedRecords = computed(() =>
  [...records.value].sort((a, b) => Date.parse(a.createdAt) - Date.parse(b.createdAt))
)
const chartRecords = computed(() => sortedRecords.value.slice(-POUR_CHART_LIMIT))
const truncated = computed(() => records.value.length > POUR_CHART_LIMIT)
// The range narrows the charts only; the summary and the list keep every pour.
const rangedRecords = computed(() => poursInRange(chartRecords.value, rangeHours.value))
const series = computed(() => levelSeries(rangedRecords.value))
const totals = computed(() => dailyTotals(rangedRecords.value, timeZone))
const hasChartData = computed(() => (chartView.value === 'level' ? series : totals).value.length > 0)
const summary = computed(() => summarizePours(chartRecords.value, timeZone))
const groups = computed(() => groupPoursByDay(records.value, timeZone))

const totalPages = computed(() => Math.max(1, Math.ceil(groups.value.length / GROUPS_PER_PAGE)))
const pagedGroups = computed(() => {
  const start = (currentPage.value - 1) * GROUPS_PER_PAGE
  return groups.value.slice(start, start + GROUPS_PER_PAGE)
})

function goToPage(page) {
  currentPage.value = Math.max(1, Math.min(page, totalPages.value))
}

const unit = computed(() => (config.isVolumeMetric ? 'L' : 'gal'))

function toUnit(litres) {
  if (config.isVolumeUs) return volumeLtoUSGallon(litres)
  if (config.isVolumeUk) return volumeLtoUKGallon(litres)
  return litres
}

function formatVolume(litres) {
  return `${Number(toUnit(Number(litres) || 0).toFixed(2))} ${unit.value}`
}

function dayParts(day) {
  const [y, m, d] = day.split('-').map(Number)
  const parts = new Intl.DateTimeFormat('en-US', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC'
  }).formatToParts(new Date(Date.UTC(y, m - 1, d)))
  const part = (type) => parts.find((p) => p.type === type)?.value ?? ''
  return { weekday: part('weekday'), day: part('day'), month: part('month') }
}

function dayLabel(day) {
  const { weekday, day: d, month } = dayParts(day)
  return `${weekday} ${d} ${month}`
}

function shortDay(day) {
  const { day: d, month } = dayParts(day)
  return `${d} ${month}`
}

const timeFormat = new Intl.DateTimeFormat('en-GB', {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone
})
const dateTimeFormat = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone
})

function formatTime(createdAt) {
  return timeFormat.format(new Date(createdAt))
}

const summaryText = computed(() => {
  const { latestLevel, totalPoured, busiestDay } = summary.value
  const level = latestLevel === null ? 'unknown' : formatVolume(latestLevel)
  const busiest = busiestDay
    ? `${dayLabel(busiestDay.day)}, ${formatVolume(busiestDay.litres)}`
    : 'none'
  return `Latest level ${level}. Total poured ${formatVolume(totalPoured)}. Busiest day ${busiest}.`
})

// Every calendar day from the first to the last, so a day without pours is a gap.
function daysBetween(first, last) {
  const days = []
  const end = Date.parse(last + 'T00:00:00Z')
  for (let t = Date.parse(first + 'T00:00:00Z'); t <= end; t += 86400000) {
    days.push(new Date(t).toISOString().substring(0, 10))
  }
  return days
}

function themeColors() {
  const style = getComputedStyle(document.body)
  const token = (name, fallback) => style.getPropertyValue(name).trim() || fallback
  return {
    text: token('--text-secondary', '#6c757d'),
    grid: token('--border', '#dee2e6'),
    line: token('--brand', '#0d6efd'),
    bar: token('--success', '#198754')
  }
}

function destroyChart() {
  chart?.destroy()
  chart = null
}

function drawChart() {
  destroyChart()
  if (status.value !== 'ready' || !hasChartData.value || !chartCanvas.value) return

  const colors = themeColors()
  const axis = (title) => ({
    ticks: { color: colors.text },
    grid: { color: colors.grid },
    border: { color: colors.grid },
    title: { display: !!title, text: title, color: colors.text }
  })
  if (chartView.value === 'level') drawLevel(colors, axis)
  else drawDaily(colors, axis)
}

function drawLevel(colors, axis) {
  const points = series.value
  const maxLevel = Math.max(...points.map((p) => p.level))
  const capacity = Math.max(Number(vessel.value?.totalVolume) || 0, maxLevel)

  chart = new Chart(chartCanvas.value, {
    type: 'line',
    data: {
      datasets: [
        {
          label: `Level (${unit.value})`,
          data: points.map((p) => ({ x: p.time, y: toUnit(p.level) })),
          stepped: 'after',
          borderColor: colors.line,
          backgroundColor: colors.line,
          pointRadius: points.length > 100 ? 0 : 3,
          pointHoverRadius: 5
        }
      ]
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'nearest', intersect: false, axis: 'x' },
      scales: {
        x: { ...axis(), type: 'time' },
        y: { ...axis(`Level (${unit.value})`), min: 0, max: toUnit(capacity) }
      },
      plugins: {
        legend: { display: false },
        zoom: {
          limits: { x: { min: 'original', max: 'original' } },
          pan: { enabled: true, mode: 'x' },
          zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' }
        },
        tooltip: {
          callbacks: {
            title: (items) => dateTimeFormat.format(new Date(points[items[0].dataIndex].time)),
            label: (item) => {
              const point = points[item.dataIndex]
              return [
                `Poured: ${formatVolume(point.pour)}`,
                `Level after: ${formatVolume(point.level)}`
              ]
            }
          }
        }
      }
    }
  })
}

function drawDaily(colors, axis) {
  const days = daysBetween(totals.value[0].day, totals.value[totals.value.length - 1].day)
  const byDay = new Map(totals.value.map((t) => [t.day, t]))
  chart = new Chart(chartCanvas.value, {
    type: 'bar',
    data: {
      labels: days,
      datasets: [
        {
          label: `Poured (${unit.value})`,
          data: days.map((d) => (byDay.has(d) ? toUnit(byDay.get(d).litres) : null)),
          backgroundColor: colors.bar,
          maxBarThickness: 40
        }
      ]
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          ...axis(),
          ticks: {
            color: colors.text,
            autoSkip: true,
            maxRotation: 0,
            callback(value) {
              return shortDay(this.getLabelForValue(value))
            }
          }
        },
        y: { ...axis(`Poured (${unit.value})`), beginAtZero: true }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => dayLabel(days[items[0].dataIndex]),
            label: (item) => {
              const total = byDay.get(days[item.dataIndex])
              const count = total.count === 1 ? '1 pour' : `${total.count} pours`
              return `${formatVolume(total.litres)} in ${count}`
            }
          }
        }
      }
    }
  })
}

watch(
  [
    status,
    chartView,
    series,
    totals,
    () => config.isVolumeUs,
    () => config.isVolumeUk,
    () => preferences.dark_mode
  ],
  drawChart,
  { flush: 'post' }
)
onBeforeUnmount(destroyChart)

// A chip also resets the zoom: a new range redraws the chart, the same range restores it.
function selectRange(hours) {
  rangeHours.value = hours
  chart?.resetZoom?.()
}

function resetZoom() {
  chart?.resetZoom?.()
}

async function load() {
  logDebug('VesselPourListView.load()')
  const id = ++loadId
  status.value = 'loading'
  const list = await pourStore.listPours(route.params.id)
  if (id !== loadId) return
  if (list === null) {
    status.value = 'error'
    return
  }
  records.value = list.map(toRecord)
  currentPage.value = 1
  status.value = 'ready'
}

onMounted(async () => {
  logDebug('VesselPourListView.onMounted()')

  vessel.value =
    vesselStore.vesselList.find((v) => v.id === route.params.id) ??
    (await vesselStore.getVessel(route.params.id))
  await load()
})

async function toggleExcluded(pour) {
  logDebug('VesselPourListView.toggleExcluded()', pour.id)
  // Toggle locally for immediate feedback; no update endpoint yet
  pour.excluded = !pour.excluded
}
</script>

<style scoped>
.pour-history__skeleton {
  height: 240px;
  margin-bottom: 16px;
  border-radius: var(--app-radius);
  background: linear-gradient(90deg, var(--bg-elevated), var(--border), var(--bg-elevated));
  background-size: 200% 100%;
  animation: pour-history-pulse 1.4s ease-in-out infinite;
}

.pour-history__ranges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pour-history__chart {
  position: relative;
  width: 100%;
  height: 240px;
}

.pour-history__summary {
  color: var(--text-secondary);
}

.pour-history__error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-color: var(--danger);
}

.pour-history__day {
  margin-top: 16px;
}

.pour-history__row--excluded td {
  opacity: 0.55;
  text-decoration: line-through;
}

.pour-history__row--excluded td:last-child {
  opacity: 1;
  text-decoration: none;
}

@media (prefers-reduced-motion: reduce) {
  .pour-history__skeleton {
    animation: none;
  }
}

@keyframes pour-history-pulse {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}
</style>
