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
    <div class="row items-center">
      <div class="col-md-10">
        <p></p>
        <p class="text-h6">Ingestion errors</p>
      </div>
    </div>
    <hr />

    <div class="row items-center ingestion-error-summary">
      <div class="col-12 col-md">
        <p>
          Showing {{ logList ? logList.length : 0 }} error entries{{ hasMore ? ' (more available)' : '' }}.
          Use download to fetch all entries.
        </p>
      </div>
      <div class="col-12 col-md-auto ingestion-error-summary__actions">
        <app-button
          type="button"
          variant="secondary"
          @click.prevent="updateLogList()"
          :disabled="global.disabled"
        >
          Refresh
        </app-button>
        <app-button
          type="button"
          variant="primary"
          @click.prevent="downloadAllRecords()"
          :disabled="global.disabled"
        >
          Download
        </app-button>
      </div>
    </div>

    <div class="row" v-if="logList != null">
      <q-markup-table class="app-table app-table--striped">
        <thead>
          <tr>
            <th scope="col" class="col-sm-2">Created</th>
            <th scope="col" class="col-sm-1">Device</th>
            <th scope="col" class="col-sm-1">Source</th>
            <th scope="col" class="col-sm-1">Reason</th>
            <th scope="col" class="col-sm-2">IP</th>
            <th scope="col" class="col-sm-3">Error Detail</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in logList" :key="l.id">
            <td scope="row">
              {{ formatLocalTimestamp(l.createdAt) }}
            </td>
            <td>{{ l.deviceType }}</td>
            <td>{{ l.sourceType }}</td>
            <td>{{ l.reason }}</td>
            <td>{{ l.ipAddress }}</td>
            <td>{{ l.errorDetail }}</td>
          </tr>
        </tbody>
      </q-markup-table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { global } from '@/modules/pinia'
import { apiFetch } from '@/modules/apiClient'
import { logDebug } from '@/ui'
import { formatLocalTimestamp } from '@/core'

const logList = ref(null)
const hasMore = ref(false)
const nextCursor = ref(null)

onMounted(() => {
  logDebug('IngestionErrorView.onMounted()')
  updateLogList()
})

async function updateLogList() {
  logDebug('IngestionErrorView.updateLogList()')

  logList.value = null

  const releaseBusy = global.acquireBusy()
  try {
    const res = await apiFetch('GET', 'system/ingestion?limit=50')
    logDebug('IngestionErrorView.updateLogList()', res.status)
    if (!res.ok) throw res
    const json = await res.json()
    logDebug('IngestionErrorView.updateLogList()', json)
    logList.value = json.items
    hasMore.value = json.hasMore
    nextCursor.value = json.nextCursor
  } catch {
    global.messageError = 'Failed to retrieve list of ingestion error entries'
  } finally {
    releaseBusy()
  }
}

async function downloadAllRecords() {
  logDebug('IngestionErrorView.downloadAllRecords()')

  const releaseBusy = global.acquireBusy()
  const allRecords = []
  let cursor = null
  const limit = 50

  try {
    while (true) {
      const res = await apiFetch(
        'GET',
        `system/ingestion?limit=${limit}` + (cursor ? `&cursor=${encodeURIComponent(cursor)}` : '')
      )

      logDebug('IngestionErrorView.downloadAllRecords()', res.status)
      if (!res.ok) throw res

      const json = await res.json()
      logDebug('IngestionErrorView.downloadAllRecords()', json)

      allRecords.push(...json.items)

      if (!json.hasMore) {
        break
      }

      cursor = json.nextCursor
    }

    // Create JSON and trigger download
    const jsonString = JSON.stringify(allRecords, null, 2)
    const blob = new Blob([jsonString], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `ingestion-errors-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)

    logDebug('IngestionErrorView.downloadAllRecords()', 'Download complete')
  } catch (error) {
    logDebug('IngestionErrorView.downloadAllRecords()', error)
    global.messageError = 'Failed to download records'
  } finally {
    releaseBusy()
  }
}
</script>

<style scoped>
/* Room between the summary and action buttons and the table below them. */
.ingestion-error-summary {
  margin-bottom: 16px;
}

.ingestion-error-summary__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 599px) {
  .ingestion-error-summary__actions {
    justify-content: flex-start;
    margin-top: 8px;
  }
}
</style>
