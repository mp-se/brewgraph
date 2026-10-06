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
      <p class="text-h6 q-mb-none">Batch Pressure List - '{{ batchName }}'</p>
      <app-button
        type="button"
        variant="outline-secondary" dense
        :aria-expanded="showStats"
        aria-controls="pressure-stats-collapse"
        @click="showStats = !showStats"
      >
        {{ showStats ? 'Hide stats' : 'Show stats' }}
      </app-button>
    </div>
    <hr />

    <div class="row q-col-gutter-sm">
      <div id="pressure-stats-collapse" class="app-collapse col-md-12" :class="{ show: showStats }">
        <PressureStatsFragment :model-value="pressureStats"></PressureStatsFragment>
      </div>

      <div class="row q-col-gutter-sm">
        <div class="col-md-2">
          <AppInputDate
            v-model="infoFirstDay"
            label="Filter first"
            :disabled="global.disabled"
          ></AppInputDate>
        </div>
        <div class="col-md-2">
          <AppInputDate
            v-model="infoLastDay"
            label="Filter last"
            :disabled="global.disabled"
          ></AppInputDate>
        </div>
        <div class="col-md-2">
          <AppField label="&nbsp;"
            ><app-button
              @click="apply()"
              type="button"
              variant="secondary" dense
              :disabled="global.disabled"
            >
              Apply Filter
            </app-button></AppField
          >&nbsp;
        </div>
        <div class="col-md-2">
          <AppField label="&nbsp;"
            ><app-button
              @click="activateAll()"
              type="button"
              variant="secondary" dense
              :disabled="global.disabled"
            >
              Clear excluded
            </app-button></AppField
          >
        </div>
      </div>

      <q-markup-table class="app-table app-table--striped">
        <thead>
          <tr>
            <th scope="col" class="col-sm-2">
              <div :class="sortedClass('created')">
                Date&nbsp;
                <a
                  class="icon-link icon-link-hover"
                  @click="doSort(pressureList, 'created', 'date')"
                >
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-1">Excluded</th>
            <th scope="col" class="col-sm-2">
              <div :class="sortedClass('pressure')">
                Pressure ({{
                  config.isPressurePSI ? 'PSI' : config.isPressureBAR ? 'Bar' : 'kPa'
                }})&nbsp;
                <a
                  class="icon-link icon-link-hover"
                  @click="doSort(pressureList, 'pressure', 'num')"
                >
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-1">Temp ({{ config.isTempC ? 'C' : 'F' }})</th>
            <th scope="col" class="col-sm-1">
              <div :class="sortedClass('battery')">
                Battery&nbsp;
                <a
                  class="icon-link icon-link-hover"
                  @click="doSort(pressureList, 'battery', 'num')"
                >
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-1">RSSI</th>
            <th scope="col" class="col-sm-1">Run time (s)</th>
          </tr>
        </thead>

        <tbody :key="forceRender">
          <tr v-for="p in paginatedPressureList" :key="p.id">
            <td class="text-body1">
              {{ formatLocalTimestamp(p.createdAt) }}
            </td>
            <td>
              <q-toggle
                dense
                :model-value="p.excluded"
                title="Exclude this reading"
                aria-label="Exclude this reading"
                @update:model-value="updatePressure(p.id)"
              />
            </td>
            <td class="text-body1">{{ getFormattedPressure(p.pressure) }}</td>
            <td class="text-body1">{{ getFormattedTemperature(p.temperature) }}</td>
            <td class="text-body1">{{ p.battery !== null ? new Number(p.battery).toFixed(2) : '--' }}</td>
            <td class="text-body1">{{ p.rssi }}</td>
            <td class="text-body1">{{ p.runTime !== null ? new Number(p.runTime).toFixed(2) : '--' }}</td>
          </tr>
        </tbody>
      </q-markup-table>

      <div class="col-12 row items-center app-list-actions">
        <div class="col-12 col-md app-list-actions__primary">
          <app-button
            outline
            color="primary"
            :to="{ name: 'batch-list' }"
          >
            <q-icon name="list" class="q-mr-xs" />
            Batch list
          </app-button>
        </div>
        <div
          v-if="totalPages > 1"
          class="col-12 col-md-auto row justify-end"
        >
          <nav aria-label="Pressure list pagination">
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
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { config, pressureStore, batchStore, global } from '@/modules/pinia'
import router from '@/modules/router'
import {
  getPressureDataAnalytics,
  getFormattedTemperature,
  getFormattedPressure
} from '@/modules/utils'
import { logDebug, logError } from '@/ui'
import { formatLocalTimestamp, localDateEnd, localDateStart } from '@/core'
import { usePagination } from '@/modules/usePagination'
import {
  sortedIconClass,
  setSortingDefault,
  sortedClass,
  sortList,
  applySortList
} from '@/modules/ui'

const pressureList = ref(null)
const pressureStats = ref(null)
const forceRender = ref(0)
const showStats = ref(true)
const {
  currentPage,
  totalPages,
  pagedItems: paginatedPressureList,
  goToPage,
  resetPage
} = usePagination(pressureList, 100)

function doSort(list, field, type) {
  sortList(list, field, type)
  resetPage()
}

const infoFirstDay = ref(null)
const infoLastDay = ref(null)

const batchName = ref('')

async function updatePressure(id) {
  logDebug('BatchPressureListView.updatePressure()', id)

  for (const p of pressureList.value) {
    if (p.id == id) {
      logDebug('BatchPressureListView.updatePressure()', 'Found Record', p)

      const previous = p.excluded
      p.excluded = !previous
      const success = await pressureStore.updatePressure(p)
      if (success) {
        logDebug('BatchPressureListView.updatePressure()', 'Success')
        pressureStats.value = getPressureDataAnalytics(pressureList.value)
      } else {
        // A failed save puts the switch back.
        p.excluded = previous
        global.messageError = 'Failed to save the excluded setting for pressure reading ' + id + '; it was put back'
      }
      break
    }
  }
}

async function apply() {
  const last = localDateEnd(infoLastDay.value)
  const first = localDateStart(infoFirstDay.value)

  // logDebug('BatchPressureListView.apply()', first, last, infoOG.value, infoFG.value)
  logDebug('BatchPressureListView.apply()', first, last)

  const releaseBusy = global.acquireBusy()
  try {
    for (const p of pressureList.value) {
      const date = Date.parse(p.createdAt)
      let excluded = true

      if (date <= last && date >= first) excluded = false

      if (p.excluded != excluded) {
        p.excluded = excluded

        const success = await pressureStore.updatePressure(p)
        if (success) {
          logDebug('BatchPressureListView.apply()', 'Success')
        } else {
          logError('BatchPressureListView.apply()', 'Failed to update pressure', p)
        }
      }
    }
    logDebug('BatchPressureListView.apply()', 'Completed')
    forceRender.value++
    pressureStats.value = getPressureDataAnalytics(pressureList.value)
  } finally {
    releaseBusy()
  }
}

async function activateAll() {
  logDebug('BatchPressureListView.activateAll()')

  const releaseBusy = global.acquireBusy()
  try {
    for (const p of pressureList.value) {
      if (p.excluded) {
        p.excluded = false
        const success = await pressureStore.updatePressure(p)
        if (success) {
          logDebug('BatchPressureListView.activateAll()', 'Success')
        } else {
          logError('BatchPressureListView.activateAll()', 'Failed to update pressure', p)
        }
      }
    }
    logDebug('BatchPressureListView.activateAll()', 'Completed')
    forceRender.value++
    pressureStats.value = getPressureDataAnalytics(pressureList.value)
  } finally {
    releaseBusy()
  }
}

onMounted(async () => {
  logDebug('BatchPressureListView.onMounted()')
  setSortingDefault('created', 'date', false)

  pressureList.value = null

  const b = await batchStore.getBatch(router.currentRoute.value.params.id)
  if (b) batchName.value = b.name

  const pl = await pressureStore.getPressureListForBatch(router.currentRoute.value.params.id)
  if (pl) {
    pressureList.value = pl
    applySortList(pressureList.value)
    logDebug('BatchPressureListView.onMounted()', pressureList.value)

    pressureStats.value = getPressureDataAnalytics(pressureList.value)

    infoFirstDay.value = pressureStats.value.date.firstDate
    infoLastDay.value = pressureStats.value.date.lastDate
  } else {
    logError(
      'BatchPressureListView.onMounted()',
      'Failed to load pressure',
      router.currentRoute.value.params.id
    )
  }
})
</script>
