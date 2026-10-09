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
      <p class="text-h6 q-mb-none">Batch Gravity List - '{{ batchName }}'</p>
      <app-button
        type="button"
        variant="outline-secondary" dense
        :aria-expanded="showStats"
        aria-controls="gravity-stats-collapse"
        @click="showStats = !showStats"
      >
        {{ showStats ? 'Hide stats' : 'Show stats' }}
      </app-button>
    </div>
    <hr />

    <div class="row q-col-gutter-sm">
      <div id="gravity-stats-collapse" class="app-collapse col-md-12" :class="{ show: showStats }">
        <GravityStatsFragment :model-value="gravityStats"></GravityStatsFragment>
        <LifeEstimates :model-value="gravityStats"></LifeEstimates>
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
          <AppInputNumber
            v-model="infoOG"
            :label="`Filter OG (${config.isGravitySG ? 'SG' : 'P'})`"
            :step="stepFor('gravity')"
            :disabled="global.disabled"
          ></AppInputNumber>
        </div>
        <div class="col-md-2">
          <AppInputNumber
            v-model="infoFG"
            :label="`Filter FG (${config.isGravitySG ? 'SG' : 'P'})`"
            :step="stepFor('gravity')"
            :disabled="global.disabled"
          ></AppInputNumber>
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
                  @click="doSort(gravityList, 'created', 'date')"
                >
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-1">Excluded</th>
            <th scope="col" class="col-sm-1">
              <div :class="sortedClass('gravity')">
                Gravity ({{ config.isGravitySG ? 'SG' : 'P' }})&nbsp;
                <a class="icon-link icon-link-hover" @click="doSort(gravityList, 'gravity', 'num')">
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-1">
              <div :class="sortedClass('angle')">
                Angle&nbsp;
                <a class="icon-link icon-link-hover" @click="doSort(gravityList, 'angle', 'num')">
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-1">Velocity</th>
            <th scope="col" class="col-sm-1">Temp ({{ config.isTempC ? 'C' : 'F' }})</th>
            <th scope="col" class="col-sm-1">
              <div :class="sortedClass('battery')">
                Battery&nbsp;
                <a class="icon-link icon-link-hover" @click="doSort(gravityList, 'battery', 'num')">
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-1">RSSI</th>
            <th scope="col" class="col-sm-1">Run time (s)</th>
          </tr>
        </thead>

        <tbody :key="forceRender">
          <tr v-for="g in paginatedGravityList" :key="g.id">
            <td class="text-body1">{{ formatLocalTimestamp(g.created) }}</td>
            <td>
              <q-toggle
                dense
                :model-value="g.excluded"
                title="Exclude this reading"
                aria-label="Exclude this reading"
                @update:model-value="updateGravity(g.id)"
              />
            </td>
            <td class="text-body1">
              {{
                config.isGravitySG
                  ? new Number(g.gravity).toFixed(3)
                  : new Number(gravityToPlato(g.gravity)).toFixed(2)
              }}
            </td>
            <td class="text-body1">{{ new Number(g.angle).toFixed(2) }}</td>
            <td class="text-body1">{{ new Number(g.velocity).toFixed(3) }}</td>
            <td class="text-body1">{{ getFormattedTemperature(g.temperature) }}</td>
            <td class="text-body1">{{ new Number(g.battery).toFixed(2) }}</td>
            <td class="text-body1">{{ g.rssi }}</td>
            <td class="text-body1">{{ g.runTime !== null ? new Number(g.runTime).toFixed(2) : '--' }}</td>
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
          <nav aria-label="Gravity list pagination">
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
import { config, gravityStore, batchStore, global } from '@/modules/pinia'
import router from '@/modules/router'
import { gravityToPlato, platoToGravity, getGravityDataAnalytics, getFormattedTemperature } from '@/modules/utils'
import { stepFor } from '@/modules/useUnitConversion'
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

const gravityList = ref(null)
const gravityStats = ref(null)
const forceRender = ref(0)
const showStats = ref(true)
const {
  currentPage,
  totalPages,
  pagedItems: paginatedGravityList,
  goToPage,
  resetPage
} = usePagination(gravityList, 100)

function doSort(list, field, type) {
  sortList(list, field, type)
  resetPage()
}

const infoFirstDay = ref(null)
const infoLastDay = ref(null)
const infoOG = ref(null)
const infoFG = ref(null)

const batchName = ref('')

async function updateGravity(id) {
  logDebug('BatchGravityListView.updateGravity()', id)

  for (const g of gravityList.value) {
    if (g.id == id) {
      logDebug('BatchGravityListView.updateGravity()', 'Found Record', g)

      const previous = g.excluded
      g.excluded = !previous
      const success = await gravityStore.updateGravity(g)
      if (success) {
        logDebug('BatchGravityListView.updateGravity()', 'Success')
        gravityStats.value = getGravityDataAnalytics(gravityList.value)
      } else {
        // A failed save puts the switch back.
        g.excluded = previous
        global.messageError = 'Failed to save the excluded setting for gravity reading ' + id + '; it was put back'
      }
      break
    }
  }
}

async function apply() {
  const last = localDateEnd(infoLastDay.value)
  const first = localDateStart(infoFirstDay.value)
  const og = config.isGravitySG || infoOG.value == null ? infoOG.value : platoToGravity(infoOG.value)
  const fg = config.isGravitySG || infoFG.value == null ? infoFG.value : platoToGravity(infoFG.value)

  logDebug('BatchGravityListView.apply()', first, last, infoOG.value, infoFG.value)

  const releaseBusy = global.acquireBusy()
  try {
    for (const g of gravityList.value) {
      const date = Date.parse(g.created)
      let excluded = true

      if (date <= last && date >= first && g.gravity <= og && g.gravity >= fg)
        excluded = false

      if (g.excluded != excluded) {
        g.excluded = excluded

        const success = await gravityStore.updateGravity(g)
        if (success) {
          logDebug('BatchGravityListView.apply()', 'Success')
        } else {
          logError('BatchGravityListView.apply()', 'Failed to update gravity', g)
        }
      }
    }
    logDebug('BatchGravityListView.apply()', 'Completed')
    forceRender.value++
    gravityStats.value = getGravityDataAnalytics(gravityList.value)
  } finally {
    releaseBusy()
  }
}

async function activateAll() {
  logDebug('BatchGravityListView.activateAll()')

  const releaseBusy = global.acquireBusy()
  try {
    for (const g of gravityList.value) {
      if (g.excluded) {
        g.excluded = false
        const success = await gravityStore.updateGravity(g)
        if (success) {
          logDebug('BatchGravityListView.activateAll()', 'Success')
        } else {
          logError('BatchGravityListView.activateAll()', 'Failed to update gravity', g)
        }
      }
    }
    logDebug('BatchGravityListView.activateAll()', 'Completed')
    forceRender.value++
    gravityStats.value = getGravityDataAnalytics(gravityList.value)
  } finally {
    releaseBusy()
  }
}

onMounted(async () => {
  logDebug('BatchGravityListView.onMounted()')
  setSortingDefault('created', 'date', false)

  gravityList.value = null
  const batchId = router.currentRoute.value.params.id
  if (typeof batchId !== 'string' || !batchId || batchId === 'undefined' || batchId === 'null') {
    global.messageError = 'A valid batch is required to view gravity readings'
    return
  }

  const batch = await batchStore.getBatch(batchId)
  if (batch) batchName.value = batch.name

  const gl = await gravityStore.getGravityListForBatch(batchId)
  if (gl) {
    gravityList.value = gl
    applySortList(gravityList.value)
    logDebug('BatchGravityListView.onMounted()', gravityList.value)

    gravityStats.value = getGravityDataAnalytics(gravityList.value)

    infoFirstDay.value = gravityStats.value.date.firstDate
    infoLastDay.value = gravityStats.value.date.lastDate
    infoOG.value = Number.parseFloat(
      new Number(gravityStats.value.gravity.max).toFixed(config.isGravitySG ? 3 : 2)
    )
    infoFG.value = Number.parseFloat(
      new Number(gravityStats.value.gravity.min).toFixed(config.isGravitySG ? 3 : 2)
    )
  } else {
    logError(
      'BatchGravityListView.onMounted()',
      'Failed to load gravity',
      batchId
    )
  }
})
</script>
