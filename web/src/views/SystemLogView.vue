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
        <p class="text-h6">System log - Latest system events</p>
      </div>
    </div>
    <hr />

    <div class="row items-center system-log-summary">
      <div class="col-12 col-md">
        <p>
          Showing {{ logList ? logList.length : 0 }} log entries{{ hasMore ? ' (more available)' : '' }}. Use
          download to fetch all entires.
        </p>
      </div>
      <div class="col-12 col-md-auto system-log-summary__actions">
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
            <th scope="col" class="col-sm-2">
              <div :class="sortedClass('timestamp')">
                Date&nbsp;
                <a
                  class="icon-link icon-link-hover"
                  @click="sortList(logList, 'createdAt', 'date')"
                >
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-2">
              <div :class="sortedClass('event')">
                Event&nbsp;
                <a class="icon-link icon-link-hover" @click="sortList(logList, 'event', 'str')">
                  <q-icon :name="sortedIconClass" />
                </a>
              </div>
            </th>
            <th scope="col" class="col-sm-6">Message</th>
            <th scope="col" class="col-sm-1">Level</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in logList" :key="l.id">
            <td scope="row">
              <span v-if="l.createdAt"
        >{{ formatLocalTimestamp(l.createdAt) }}</span
              >
            </td>
            <td>{{ l.event }}</td>
            <td>{{ l.message }}</td>
            <td>
              <span :class="['app-badge', levelBadgeClass(l.level)]" data-testid="log-level">{{ l.level }}</span>
            </td>
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
import {
  sortedIconClass,
  setSortingDefault,
  sortedClass,
  sortList,
  applySortList
} from '@/modules/ui'

// Severity badge colour: errors red, warnings yellow, info cyan, everything else (debug, unknown) grey.
function levelBadgeClass(level) {
  switch (String(level || '').toUpperCase()) {
    case 'CRITICAL':
    case 'FATAL':
    case 'ERROR':
      return 'app-badge--negative'
    case 'WARNING':
    case 'WARN':
      return 'app-badge--warning'
    case 'INFO':
      return 'app-badge--info'
    default:
      return 'app-badge--light'
  }
}

const logList = ref(null)
const hasMore = ref(false)
const nextCursor = ref(null)

onMounted(() => {
  logDebug('LogListView.onMounted()')
  setSortingDefault('createdAt', 'date', false)
  updateLogList()
})

async function updateLogList() {
  logDebug('LogListView.updateLogList()')

  logList.value = null

  const releaseBusy = global.acquireBusy()
  try {
    const res = await apiFetch('GET', 'system/logs?limit=50')
    logDebug('LogListView.updateLogList()', res.status)
    if (!res.ok) throw res
    const json = await res.json()
    logList.value = json.items
    hasMore.value = json.hasMore
    nextCursor.value = json.nextCursor
    applySortList(logList.value)
  } catch {
    global.messageError = 'Failed to retrive list of system log enties'
  } finally {
    releaseBusy()
  }
}

async function downloadAllRecords() {
  logDebug('SystemLogView.downloadAllRecords()')

  const releaseBusy = global.acquireBusy()
  const allRecords = []
  let cursor = null
  const limit = 50

  try {
    while (true) {
      const path =
        `system/logs?limit=${limit}` + (cursor ? `&cursor=${encodeURIComponent(cursor)}` : '')
      const res = await apiFetch('GET', path)

      logDebug('SystemLogView.downloadAllRecords()', res.status)
      if (!res.ok) throw res

      const json = await res.json()
      logDebug('SystemLogView.downloadAllRecords()', json)

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
    link.download = `system-logs-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)

    logDebug('SystemLogView.downloadAllRecords()', 'Download complete')
  } catch (error) {
    logDebug('SystemLogView.downloadAllRecords()', error)
    global.messageError = 'Failed to download records'
  } finally {
    releaseBusy()
  }
}
</script>

<style scoped>
/* Room between the summary and action buttons and the table below them. */
.system-log-summary {
  margin-bottom: 16px;
}

.system-log-summary__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 599px) {
  .system-log-summary__actions {
    justify-content: flex-start;
    margin-top: 8px;
  }
}
</style>
