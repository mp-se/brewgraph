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
    <AppPageHeader title="Batch List">
      <template #action>
        <app-button
          color="primary"
          unelevated
          :to="{ name: 'batch', params: { id: 'new' } }"
          :disable="global.disabled"
        >
          Add Batch
        </app-button>
      </template>
      <div class="row">
        <div class="col-12 col-md-6">
          <AppSelect
            v-model="preferences.batchListFilterDevice"
            :options="deviceList"
            label="Device filter"
            help=""
            :disabled="global.disabled"
          />
        </div>
        <div class="col-12 col-sm-6 col-md-3">
          <AppToggle
            v-model="preferences.batchListFilterData"
            label="Data"
            help=""
            :disabled="global.disabled"


            title="Show only batches with data"
            aria-label="Show only batches with data"
          />
        </div>
        <div class="col-12 col-sm-6 col-md-3">
          <AppSelect
            v-model="statusFilter"
            :options="statusFilterOptions"
            label="Status filter"
            help=""
            :disabled="global.disabled"
          />
        </div>
      </div>
    </AppPageHeader>

    <template v-if="batchList != null">
      <q-markup-table class="app-table app-table--striped">
        <thead>
          <tr>
            <th scope="col" class="col-sm-3">
              <div :class="getSortedClass('name')">
                Name&nbsp;
                <a class="icon-link icon-link-hover" @click="sortList(batchList, 'name', 'str')">
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-2">
              <div :class="getSortedClass('brewDate')">
                Brewdate&nbsp;
                <a
                  class="icon-link icon-link-hover"
                  @click="sortList(batchList, 'brewDate', 'date')"
                >
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-1">Accepting</th>
            <th scope="col" class="col-sm-1">Status</th>
            <th scope="col" class="col-sm-2"># Grav / Press / Temp</th>
            <th scope="col" class="col-sm-4">Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in paginatedBatchList" :key="b.id">
            <td class="text-body1">{{ b.name }}</td>
            <td class="text-body1">{{ b.brewDate }}</td>
            <td>
              <q-toggle
                dense
                :model-value="b.acceptIngest"
                title="Accept ingest data from devices"
                aria-label="Accept ingest data from devices"
                data-testid="accept-ingest-toggle"
                @update:model-value="toggleAcceptIngest(b.id)"
              />
            </td>
            <td><span :class="statusBadgeClass(b.status)">{{ b.status }}</span></td>
            <td class="text-body1">{{ b.gravityCount }} / {{ b.pressureCount }} / {{ b.temperatureCount }}</td>
            <td>
              <AppRowActions label="Batch actions">
                <AppRowAction
                  kind="primary"
                  icon="edit"
                  label="Edit batch"
                  :to="{ name: 'batch', params: { id: b.id } }"
                  data-testid="batch-edit-action"
                />
                <AppRowAction
                  kind="negative"
                  icon="delete_forever"
                  label="Delete batch"
                  data-testid="batch-delete-action"
                  @click.prevent="deleteBatch(b.id, b.name)"
                />
                <AppRowAction
                  v-if="b.gravityCount > 0"
                  kind="positive"
                  icon="show_chart"
                  label="View gravity graph"
                  :to="{ name: 'batch-gravity-graph', params: { id: b.id } }"
                  data-testid="gravity-graph-action"
                />
                <AppRowAction
                  v-if="b.pressureCount > 0"
                  kind="warning"
                  icon="show_chart"
                  label="View pressure graph"
                  :to="{ name: 'batch-pressure-graph', params: { id: b.id } }"
                  data-testid="pressure-graph-action"
                />
                <AppRowAction
                  v-if="b.temperatureCount > 0"
                  kind="info"
                  icon="show_chart"
                  label="View temperature graph"
                  :to="{ name: 'batch-temp-chart', params: { id: b.id } }"
                  data-testid="temperature-graph-action"
                />
                <AppRowAction
                  icon="more_horiz"
                  label="More batch actions"
                  data-testid="batch-data-overflow-menu"
                >
                  <q-menu>
                  <q-list dense data-testid="batch-data-menu-content">
                    <template v-if="b.status !== 'archived'">
                      <q-item v-close-popup clickable :disable="global.disabled" @click="archiveBatch(b.id, b.name)" data-testid="batch-archive-menu-action"><q-item-section avatar><q-icon name="archive" /></q-item-section><q-item-section>Archive batch</q-item-section></q-item>
                    </template>
                    <template v-else>
                      <q-item v-close-popup clickable :disable="global.disabled" @click="unarchiveBatch(b.id)" data-testid="batch-unarchive-menu-action"><q-item-section avatar><q-icon name="unarchive" /></q-item-section><q-item-section>Unarchive batch</q-item-section></q-item>
                    </template>
                    <div v-if="b.gravityCount > 0 || b.pressureCount > 0 || b.temperatureCount > 0 || vesselCountForBatch(b.id) > 0" class="batch-list-actions__menu-separator" />
                    <template v-if="b.gravityCount > 0">
                      <div class="batch-list-actions__menu-heading">Gravity</div>
                      <q-item v-close-popup clickable :to="{ name: 'batch-gravity-list', params: { id: b.id } }"><q-item-section avatar><q-icon name="list" /></q-item-section><q-item-section>View readings</q-item-section></q-item>
                      <q-item v-close-popup clickable @click="exportBatchGravityCSV(b.id)"><q-item-section avatar><q-icon name="download" /></q-item-section><q-item-section>Export gravity CSV</q-item-section></q-item>
                    </template>
                    <div v-if="b.gravityCount > 0 && (b.pressureCount > 0 || b.temperatureCount > 0 || vesselCountForBatch(b.id) > 0)" class="batch-list-actions__menu-separator" />
                    <template v-if="b.pressureCount > 0">
                      <div class="batch-list-actions__menu-heading">Pressure</div>
                      <q-item v-close-popup clickable :to="{ name: 'batch-pressure-list', params: { id: b.id } }"><q-item-section avatar><q-icon name="list" /></q-item-section><q-item-section>View readings</q-item-section></q-item>
                      <q-item v-close-popup clickable @click="exportBatchPressureCSV(b.id)"><q-item-section avatar><q-icon name="download" /></q-item-section><q-item-section>Export pressure CSV</q-item-section></q-item>
                    </template>
                    <div v-if="b.pressureCount > 0 && (b.temperatureCount > 0 || vesselCountForBatch(b.id) > 0)" class="batch-list-actions__menu-separator" />
                    <template v-if="b.temperatureCount > 0">
                      <div class="batch-list-actions__menu-heading">Temperature</div>
                      <q-item v-close-popup clickable :to="{ name: 'batch-temp-list', params: { id: b.id } }"><q-item-section avatar><q-icon name="list" /></q-item-section><q-item-section>View readings</q-item-section></q-item>
                      <q-item v-close-popup clickable @click="exportBatchTemperatureCSV(b.id)"><q-item-section avatar><q-icon name="download" /></q-item-section><q-item-section>Export temperature CSV</q-item-section></q-item>
                    </template>
                    <div v-if="b.temperatureCount > 0 && vesselCountForBatch(b.id) > 0" class="batch-list-actions__menu-separator" />
                    <q-item v-if="vesselCountForBatch(b.id) > 0" v-close-popup clickable :to="{ name: 'vessel-list', query: { batchId: b.id } }"><q-item-section avatar><q-icon name="liquor" /></q-item-section><q-item-section>View vessels</q-item-section></q-item>
                  </q-list>
                  </q-menu>
                </AppRowAction>
              </AppRowActions>
            </td>
          </tr>
        </tbody>
      </q-markup-table>

      <div v-if="totalPages > 1" class="row items-center app-list-actions">
        <div class="col-12 col-md row justify-end">
          <nav aria-label="Batch list pagination">
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
      id="deleteBatch"
      title="Delete batch"
      :disabled="global.disabled"
    />
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import {
  global,
  preferences,
  batchStore,
  deviceStore,
  vesselStore,
  gravityStore,
  pressureStore,
  tempReadingStore
} from '@/modules/pinia'
import { storeToRefs } from 'pinia'
import router from '@/modules/router'
import { download } from '@/modules/utils'
import { logDebug, logError } from '@/ui'
import { apiFetch } from '@/modules/apiClient'
import { createBatchCsvExports } from '@/modules/batchCsvExport'
import { useSortableList } from '@/modules/useSortableList'
import { usePagination } from '@/modules/usePagination'
import AppPageHeader from '@/components/AppPageHeader.vue'
import AppRowAction from '@/components/AppRowAction.vue'
import AppRowActions from '@/components/AppRowActions.vue'

const { sortedIconClass, getSortedClass, sortList, applySortList } = useSortableList(
  'brewDate',
  'date',
  false
)

const confirmDeleteMessage = ref(null)
const confirmDeleteId = ref(null)

// Local, unpersisted — matches VesselListView's statusFilter pattern rather than the
// persisted global.batchListFilter* fields, since there is no cross-session reason to
// remember "I was looking at archived batches."
const statusFilter = ref('active')
const statusFilterOptions = [
  { label: 'Active (fermenting/packaged)', value: 'active' },
  { label: 'Archived', value: 'archived' },
  { label: 'All', value: 'all' }
]

function statusBadgeClass(status) {
  const map = {
    fermenting: 'app-badge app-badge--warning',
    packaged: 'app-badge app-badge--positive',
    archived: 'app-badge app-badge--secondary'
  }
  return map[status] ?? 'app-badge app-badge--secondary'
}

const batchList = ref(null)
const deviceList = ref([])
const { batchListFilterDevice, batchListFilterData } = storeToRefs(preferences)

const { updatedBatchData } = storeToRefs(global)

watch(updatedBatchData, () => {
  filterBatchList()
  applySortList(batchList.value)
  if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
})

const {
  currentPage,
  totalPages,
  pagedItems: paginatedBatchList,
  goToPage,
  resetPage
} = usePagination(batchList, 10)

onMounted(async () => {
  logDebug('BatchListView.onMounted()')

  const query = router.currentRoute.value.query

  if (Object.prototype.hasOwnProperty.call(query, 'deviceId')) {
    logDebug('BatchListView.onMounted()', 'Filter by deviceId', query.deviceId)
    preferences.batchListFilterDevice = query.deviceId
  }

  filterBatchList()
  applySortList(batchList.value)

  await vesselStore.getVesselList()

  deviceList.value.push({ label: 'All', value: '*' })
  deviceStore.deviceList.forEach((d) => {
    deviceList.value.push({ label: d.chipId + ' (' + d.mdns + ')', value: d.id })
  })
})

function vesselCountForBatch(batchId) {
  return vesselStore.vesselList.filter((v) => v.batchId === batchId).length
}

async function toggleAcceptIngest(id) {
  logDebug('BatchListView.toggleAcceptIngest()', id)
  for (const b of batchList.value) {
    if (b.id == id) {
      b.acceptIngest = !b.acceptIngest
      const success = await batchStore.updateBatch(b)
      if (!success) {
        global.messageError = 'Failed to update batch ' + id
        b.acceptIngest = !b.acceptIngest
      }
      break
    }
  }
}

function filterBatchList() {
  logDebug(
    'BatchListView.filterBatchList()',
    preferences.batchListFilterDevice,
    preferences.batchListFilterData
  )

  batchList.value = []
  batchStore.batchList.forEach((b) => {
    let include = true

    if (
      preferences.batchListFilterDevice != '*' &&
      preferences.batchListFilterDevice != b.gravityDeviceId &&
      preferences.batchListFilterDevice != b.pressureDeviceId
    ) {
      logDebug(
        'BatchListView.filterBatchList()',
        'exclude device: ',
        b.id,
        b.gravityDeviceId,
        b.pressureDeviceId
      )
      include = false
    }

    if (preferences.batchListFilterData) {
      if (!b.gravityCount) {
        logDebug('BatchListView.filterBatchList()', 'exclude data: ', b.id, b.gravityCount)
        include = false
      }
    }

    if (statusFilter.value === 'active' && b.status === 'archived') {
      include = false
    } else if (statusFilter.value === 'archived' && b.status !== 'archived') {
      include = false
    }

    if (include) batchList.value.push(b)
  })
}

watch(batchListFilterDevice, async (selected) => {
  logDebug('BatchListView.watch(filterDevice)', selected)
  resetPage()
  filterBatchList()
  applySortList(batchList.value)
})

watch(batchListFilterData, async (selected) => {
  logDebug('BatchListView.watch(filterData)', selected)
  resetPage()
  filterBatchList()
  applySortList(batchList.value)
})

watch(statusFilter, () => {
  logDebug('BatchListView.watch(statusFilter)', statusFilter.value)
  resetPage()
  filterBatchList()
  applySortList(batchList.value)
})

async function archiveBatch(id, name) {
  logDebug('BatchListView.archiveBatch()', id, name)
  const result = await batchStore.archiveBatch(id)
  if (result) {
    global.messageSuccess = 'Archived batch'
    await batchStore.processEvent('update', id)
    filterBatchList()
    applySortList(batchList.value)
  } else {
    global.messageError = 'Failed to archive batch'
  }
}

async function unarchiveBatch(id) {
  logDebug('BatchListView.unarchiveBatch()', id)
  const result = await batchStore.unarchiveBatch(id)
  if (result) {
    global.messageSuccess = 'Un-archived batch'
    await batchStore.processEvent('update', id)
    filterBatchList()
    applySortList(batchList.value)
  } else {
    global.messageError = 'Failed to un-archive batch'
  }
}

const confirmDeleteCallback = async (result) => {
  logDebug('BatchListView.confirmDeleteCallback()', result)

  if (result) {
    global.clearMessages()
    const releaseBusy = global.acquireBusy()
    try {
      const success = await batchStore.deleteBatch(confirmDeleteId.value)
      if (success) global.messageSuccess = 'Deleted batch'
      else global.messageError = 'Failed to batch device'
    } finally {
      releaseBusy()
    }
  }
}

const deleteBatch = (id, name) => {
  logDebug('BatchListView.deleteBatch()', id, name)

  confirmDeleteMessage.value = "Do you really want to delete batch '" + name + "'"
  confirmDeleteId.value = id
  document.getElementById('deleteBatch').click()
}

// Per-batch CSV preparation is kept outside the view; the rows/menu still own
// the user interaction and delegate each format to this focused exporter.
const { exportBatchGravityCSV, exportBatchPressureCSV, exportBatchTemperatureCSV } =
  createBatchCsvExports({
    apiFetch,
    gravityStore,
    pressureStore,
    tempReadingStore,
    download,
    global,
    logDebug,
    logError
  })
</script>

<style scoped>
.batch-list-actions__menu-heading {
  padding: 0.5rem 1rem 0.25rem;
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1.2;
}

.batch-list-actions__menu-separator {
  height: 1px;
  margin: 0.25rem 0;
  background: var(--border);
}
</style>
