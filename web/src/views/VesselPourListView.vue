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
    <p class="text-h6">Pour List - '{{ vesselName }}'</p>
    <hr />

    <template v-if="pourList != null">
      <q-markup-table class="app-table app-table--striped">
        <thead>
          <tr>
            <th scope="col" class="col-sm-3">Date</th>
            <th scope="col" class="col-sm-2">Pour (L)</th>
            <th scope="col" class="col-sm-2">Volume remaining (L)</th>
            <th scope="col" class="col-sm-1">Entry type</th>
            <th scope="col" class="col-sm-1">Excluded</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in paginatedPourList" :key="p.id">
            <td class="text-body1">
              {{ p.createdAt.substring(0, 10) }} {{ p.createdAt.substring(11, 19) }}
            </td>
            <td class="text-body1">{{ Number(p.pourAmount).toFixed(2) }}</td>
            <td class="text-body1">{{ Number(p.volumeRemaining).toFixed(2) }}</td>
            <td class="text-body1">
              <span v-if="p.isManual" class="no-wrap" title="Manual entry">
                <q-icon name="edit" text-warning />
              </span>
              <span v-else class="no-wrap" title="Automatic entry">
                <q-icon name="smart_toy" text-primary />
              </span>
            </td>
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

      <p v-if="pourList.length === 0" class="text-grey-7">No pours recorded yet.</p>

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
        <div
          v-if="totalPages > 1"
          class="col-12 col-md-auto row justify-end"
        >
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
    </template>

    <template v-else>
      <div class="row q-col-gutter-sm">
        <div class="col-md-12">
          <p class="text-subtitle1">Loading...</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { global, pourStore, vesselStore } from '@/modules/pinia'
import { logDebug } from '@/ui'

const route = useRoute()
const pourList = ref(null)
const vesselName = ref('')

const currentPage = ref(1)
const ITEMS_PER_PAGE = 50

const totalPages = computed(() => {
  const count = pourList.value?.length || 0
  return Math.max(1, Math.ceil(count / ITEMS_PER_PAGE))
})

const paginatedPourList = computed(() => {
  if (!pourList.value) return []
  const start = (currentPage.value - 1) * ITEMS_PER_PAGE
  return pourList.value.slice(start, start + ITEMS_PER_PAGE)
})

function goToPage(page) {
  currentPage.value = Math.max(1, Math.min(page, totalPages.value))
}

onMounted(async () => {
  logDebug('VesselPourListView.onMounted()')

  const vessel = vesselStore.vesselList.find((v) => v.id === route.params.id)
  if (vessel) vesselName.value = vessel.name

  const list = await pourStore.listPours(route.params.id)
  // The API returns oldest-first (docs/spec-api-conventions.md: cursor pages are
  // always created_at ASC). This list reads newest-first, so sort for display.
  pourList.value = [...(list ?? [])].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  )
})

async function toggleExcluded(pour) {
  logDebug('VesselPourListView.toggleExcluded()', pour.id)
  // Toggle locally for immediate feedback; no update endpoint yet
  pour.excluded = !pour.excluded
}
</script>
