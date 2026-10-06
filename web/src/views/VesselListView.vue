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
    <AppPageHeader title="Vessels">
      <template #action>
        <app-button
          color="primary"
          unelevated
          :to="{ name: 'vessel', params: { id: 'new' } }"
          :disable="global.disabled"
        >
          Add Vessel
        </app-button>
      </template>
      <div class="row q-col-gutter-md">
        <div class="col-12 col-sm-4">
          <AppSelect
            v-model="statusFilter"
            :options="statusFilterOptions"
            label="Status filter"
            help=""
            :disabled="global.disabled"
          />
        </div>
        <div class="col-12 col-sm-8">
          <AppSelect
            v-model="batchFilter"
            :options="batchFilterOptions"
            label="Batch filter"
            help=""
            :disabled="global.disabled"
          />
        </div>
      </div>
    </AppPageHeader>

    <template v-if="vesselList != null">
      <q-markup-table class="app-table app-table--striped">
        <thead>
          <tr>
            <th scope="col" class="col-sm-1">
              <div :class="getSortedClass('vesselNumber')">
                #&nbsp;
                <a
                  class="icon-link icon-link-hover"
                  @click="sortList(vesselList, 'vesselNumber', 'num')"
                >
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-3">
              <div :class="getSortedClass('name')">
                Name&nbsp;
                <a class="icon-link icon-link-hover" @click="sortList(vesselList, 'name', 'str')">
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-1">Type</th>
            <th scope="col" class="col-sm-1">Status</th>
            <th scope="col" class="col-sm-3">Volume remaining</th>
            <th scope="col" class="col-sm-1">Pours</th>
            <th scope="col" class="col-sm-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="v in paginatedFilteredVesselList" :key="v.id">
            <td class="text-body1">{{ v.vesselNumber ?? '—' }}</td>
            <td class="text-body1">{{ v.name }}</td>
            <td>
              <span
                :class="v.vesselType === VESSEL_TYPE_KEG ? 'app-badge app-badge--positive' : 'app-badge app-badge--info'"
              >
                {{ v.vesselType }}
              </span>
            </td>
            <td>
              <span :class="statusBadgeClass(v.status)">{{ v.status }}</span>
            </td>
            <td>
              <template v-if="v.vesselType === VESSEL_TYPE_KEG">
                <AppProgress :progress="volumeProgress(v)" style="height: 22px" />
                <small class="text-grey-7"
                  >{{ Number(v.volumeRemaining).toFixed(1) }} /
                  {{ Number(v.totalVolume).toFixed(1) }} L</small
                >
              </template>
              <template v-else>
                <span v-if="v.bottlesRemaining != null"
                  >{{ v.bottlesRemaining }} / {{ v.bottleCount }} bottles</span
                >
                <span v-else>—</span>
              </template>
            </td>
            <td class="text-body1">{{ v.pourCount }}</td>
            <td>
              <AppRowActions label="Vessel actions">
                <AppRowAction
                  kind="primary"
                  icon="edit"
                  label="Edit vessel"
                  :to="{ name: 'vessel', params: { id: v.id } }"
                />
                <AppRowAction
                  kind="negative"
                  icon="delete_forever"
                  label="Delete vessel"
                  @click.prevent="deleteVessel(v.id, v.name)"
                />
                <AppRowAction
                  v-if="getBatchIdForRoute(v.batchId)"
                  kind="positive"
                  icon="inventory_2"
                  label="Open batch"
                  :to="{ name: 'batch', params: { id: getBatchIdForRoute(v.batchId) } }"
                />
                <AppRowAction
                  v-if="v.pourCount > 0"
                  kind="positive"
                  icon="list"
                  label="Show pour list"
                  :to="{ name: 'vessel-pour-list', params: { id: v.id } }"
                />
              </AppRowActions>
            </td>
          </tr>
        </tbody>
      </q-markup-table>

      <div v-if="totalPages > 1" class="row items-center app-list-actions">
        <div class="col-12 col-md row justify-end">
          <nav aria-label="Vessel list pagination">
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
      id="deleteVessel"
      title="Delete vessel"
      :disabled="global.disabled"
    />
  </div>
</template>

<script setup>
import { onMounted, ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { global, vesselStore, batchStore } from '@/modules/pinia'
import {
  VESSEL_TYPE_KEG,
  VESSEL_STATUS_CLEAN,
  VESSEL_STATUS_CONDITIONING,
  VESSEL_STATUS_SERVING
} from '@/modules/classes'
import { logDebug } from '@/ui'
import { useSortableList } from '@/modules/useSortableList'
import { storeToRefs } from 'pinia'
import AppPageHeader from '@/components/AppPageHeader.vue'
import AppRowAction from '@/components/AppRowAction.vue'
import AppRowActions from '@/components/AppRowActions.vue'

const { sortedIconClass, getSortedClass, sortList, applySortList } = useSortableList(
  'vesselNumber',
  'num',
  true
)

const vesselList = ref(null)
const statusFilter = ref('all')
const batchFilter = ref('all')
const currentPage = ref(1)
const ITEMS_PER_PAGE = 10
const confirmDeleteMessage = ref(null)
const confirmDeleteId = ref(null)
const route = useRoute()
const { updatedVesselData } = storeToRefs(global)

const statusFilterOptions = [
  { label: 'All', value: 'all' },
  { label: 'Clean', value: VESSEL_STATUS_CLEAN },
  { label: 'Conditioning', value: VESSEL_STATUS_CONDITIONING },
  { label: 'Serving', value: VESSEL_STATUS_SERVING }
]

const batchFilterOptions = computed(() => {
  const opts = [{ label: 'All batches', value: 'all' }]
  batchStore.batchList.forEach((b) => {
    opts.push({ label: b.name, value: b.id })
  })
  return opts
})

const filteredVesselList = computed(() => {
  if (!vesselList.value) return []
  return vesselList.value.filter((v) => {
    const statusOk = statusFilter.value === 'all' || v.status === statusFilter.value
    const batchOk = batchFilter.value === 'all' || v.batchId === batchFilter.value
    return statusOk && batchOk
  })
})

const totalPages = computed(() => {
  const count = filteredVesselList.value?.length || 0
  return Math.max(1, Math.ceil(count / ITEMS_PER_PAGE))
})

const paginatedFilteredVesselList = computed(() => {
  const list = filteredVesselList.value || []
  const start = (currentPage.value - 1) * ITEMS_PER_PAGE
  return list.slice(start, start + ITEMS_PER_PAGE)
})

function goToPage(page) {
  const clamped = Math.max(1, Math.min(page, totalPages.value))
  currentPage.value = clamped
}

function volumeProgress(v) {
  if (!v.totalVolume || v.totalVolume === 0) return 0
  return Math.max(0, Math.min(100, Number((v.volumeRemaining / v.totalVolume) * 100).toFixed(0)))
}

function statusBadgeClass(status) {
  const map = {
    clean: 'app-badge app-badge--secondary',
    filled: 'app-badge app-badge--warning',
    serving: 'app-badge app-badge--positive'
  }
  return map[status] ?? 'app-badge app-badge--secondary'
}

function getBatchIdForRoute(batchId) {
  if (batchId == null) return null
  const id = String(batchId).trim()
  if (!id || id === 'undefined' || id === 'null') return null
  return id
}

function syncVesselsFromStore() {
  vesselList.value = [...vesselStore.vesselList]
  applySortList(vesselList.value)
  if (currentPage.value > totalPages.value) {
    currentPage.value = totalPages.value
  }
}

onMounted(async () => {
  logDebug('VesselListView.onMounted()')

  const queryBatchId = Array.isArray(route.query.batchId)
    ? route.query.batchId[0]
    : route.query.batchId
  const queryStatus = Array.isArray(route.query.status) ? route.query.status[0] : route.query.status
  if (queryBatchId) batchFilter.value = queryBatchId
  if (queryStatus) statusFilter.value = queryStatus

  syncVesselsFromStore()
})

watch(updatedVesselData, () => {
  syncVesselsFromStore()
})

watch([statusFilter, batchFilter], () => {
  currentPage.value = 1
})

function deleteVessel(id, name) {
  logDebug('VesselListView.deleteVessel()', id)
  confirmDeleteId.value = id
  confirmDeleteMessage.value = `Do you want to delete vessel "${name}"? This cannot be undone.`
  document.getElementById('deleteVessel').click()
}

const confirmDeleteCallback = async (result) => {
  logDebug('VesselListView.confirmDeleteCallback()', result)
  if (result) {
    global.clearMessages()
    const success = await vesselStore.deleteVessel(confirmDeleteId.value)
    if (success) {
      global.messageSuccess = 'Vessel deleted'
      await vesselStore.processEvent('delete', confirmDeleteId.value)
      syncVesselsFromStore()
    } else {
      global.messageError = 'Failed to delete vessel'
    }
  }
}
</script>
