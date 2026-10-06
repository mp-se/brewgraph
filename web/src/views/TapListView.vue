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
    <AppPageHeader title="Taps">
      <template #action>
        <app-button
          color="primary"
          unelevated
          :to="{ name: 'tap', params: { id: 'new' } }"
          :disable="global.disabled"
        >
          Add Tap
        </app-button>
      </template>
    </AppPageHeader>

    <template v-if="tapList.length > 0">
      <q-markup-table class="app-table app-table--striped">
        <thead>
          <tr>
            <th scope="col" class="col-sm-1">#</th>
            <th scope="col" class="col-sm-2">
              <div :class="getSortedClass('name')">
                Name&nbsp;
                <a class="icon-link icon-link-hover" @click="sortList(tapList, 'name', 'str')">
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-2">Location</th>
            <th scope="col" class="col-sm-2">Batch</th>
            <th scope="col" class="col-sm-2">Volume remaining</th>
            <th scope="col" class="col-sm-1">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in paginatedTapList" :key="t.id">
            <td class="text-body1">{{ t.tapNumber ?? '—' }}</td>
            <td class="text-body1">
              {{ t.name }}
              <span
                v-if="cleaningDue(t)"
                class="app-badge app-badge--warning text-dark q-ml-sm"


                title="Tap line hasn't been cleaned in over 14 days"
              >
                Cleaning due
              </span>
            </td>
            <td class="text-body1">{{ t.location || '—' }}</td>
            <td class="text-body1">{{ getBatchName(getTappedVessel(t.id)) ?? '—' }}</td>
            <td>
              <template v-if="getTappedVessel(t.id)?.volumeRemaining != null">
                <AppProgress
                  :progress="tapVolumeProgress(getTappedVessel(t.id))"
                  style="height: 22px"
                />
                <small class="text-grey-7"
                  >{{ Number(getTappedVessel(t.id).volumeRemaining).toFixed(1) }} /
                  {{ Number(getTappedVessel(t.id).totalVolume).toFixed(1) }} L</small
                >
              </template>
              <template v-else>
                <span class="text-grey-7">—</span>
              </template>
            </td>
            <td>
              <AppRowActions label="Tap actions">
                <AppRowAction
                  v-if="getTapIdForRoute(t.id)"
                  kind="primary"
                  icon="edit"
                  label="Edit tap"
                  :to="{ name: 'tap', params: { id: getTapIdForRoute(t.id) } }"
                  :disable="global.disabled"
                />
                <AppRowAction v-else icon="edit" label="Tap id missing" disable />
                <AppRowAction
                  kind="negative"
                  icon="delete_forever"
                  label="Delete tap"
                  @click.prevent="deleteTap(t.id, t.name)"
                />
              </AppRowActions>
            </td>
          </tr>
        </tbody>
      </q-markup-table>

      <div v-if="totalPages > 1" class="row items-center app-list-actions">
        <div class="col-12 col-md row justify-end">
          <nav aria-label="Tap list pagination">
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
          <p class="text-subtitle1">No taps configured.</p>
        </div>
      </div>
    </template>

    <AppConfirmDialog
      :callback="confirmDeleteCallback"
      :message="confirmDeleteMessage"
      id="deleteTap"
      title="Delete tap"
      :disabled="global.disabled"
    />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { global, tapStore, vesselStore, batchStore } from '@/modules/pinia'
import { logDebug } from '@/ui'
import { useSortableList } from '@/modules/useSortableList'
import AppPageHeader from '@/components/AppPageHeader.vue'
import AppRowAction from '@/components/AppRowAction.vue'
import AppRowActions from '@/components/AppRowActions.vue'

const { sortedIconClass, getSortedClass, sortList, applySortList } = useSortableList(
  'tapNumber',
  'num',
  true
)

const confirmDeleteMessage = ref(null)
const confirmDeleteId = ref(null)
const currentPage = ref(1)
const ITEMS_PER_PAGE = 10

const tapList = computed(() => tapStore.tapList)
const totalPages = computed(() => {
  const count = tapList.value?.length || 0
  return Math.max(1, Math.ceil(count / ITEMS_PER_PAGE))
})

const paginatedTapList = computed(() => {
  const list = tapList.value || []
  const start = (currentPage.value - 1) * ITEMS_PER_PAGE
  return list.slice(start, start + ITEMS_PER_PAGE)
})

function goToPage(page) {
  const clamped = Math.max(1, Math.min(page, totalPages.value))
  currentPage.value = clamped
}

watch(
  tapList,
  (list) => {
    if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
    if (list?.length) applySortList(list)
  },
  { immediate: true }
)

function getTappedVessel(tapId) {
  return vesselStore.vesselList.find((v) => v.tapId === tapId) ?? null
}

const TAP_LINE_INTERVAL_DAYS = 14

function cleaningDue(tap) {
  const lastCleaned = tap.lastCleanedAt || tap.createdAt
  if (!lastCleaned) return false
  const days = (Date.now() - new Date(lastCleaned).getTime()) / 86_400_000
  return days > TAP_LINE_INTERVAL_DAYS
}

function getBatchName(vessel) {
  if (!vessel?.batchId) return null
  return batchStore.batchList.find((b) => b.id === vessel.batchId)?.name ?? null
}

function tapVolumeProgress(vessel) {
  if (!vessel || vessel.volumeRemaining == null || !vessel.totalVolume) return 0
  return Math.max(
    0,
    Math.min(100, Number((vessel.volumeRemaining / vessel.totalVolume) * 100).toFixed(0))
  )
}

function getTapIdForRoute(id) {
  if (id == null) return null
  const tapId = String(id).trim()
  if (!tapId || tapId === 'undefined' || tapId === 'null') return null
  return tapId
}

function deleteTap(id, name) {
  logDebug('TapListView.deleteTap()', id)
  confirmDeleteId.value = id
  confirmDeleteMessage.value = `Do you want to delete tap "${name}"?`
  document.getElementById('deleteTap').click()
}

const confirmDeleteCallback = async (result) => {
  logDebug('TapListView.confirmDeleteCallback()', result)
  if (result) {
    global.clearMessages()
    const success = await tapStore.deleteTap(confirmDeleteId.value)
    if (success) {
      global.messageSuccess = 'Tap deleted'
    } else {
      global.messageError = 'Failed to delete tap'
    }
  }
}
</script>
