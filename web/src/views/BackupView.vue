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
    <p class="text-h6">Backup & Restore</p>
    <hr />

    <div class="row q-col-gutter-md">
      <div class="col-md-12">
        <p>Create a complete backup of the database and store it in a text file</p>
      </div>

      <div class="col-md-12">
        <app-button
          @click="createBackup()"
          type="button"
          variant="primary" class="app-width-2"

          :disabled="global.disabled"
        >
          Create backup
        </app-button>
      </div>

      <div v-if="backupProgress > -1" class="col-md-12">
        <p></p>
        <AppProgress :progress="backupProgress"></AppProgress>
      </div>

      <div class="col-md-12">
        <hr />
      </div>

      <div class="col-md-12">
        <p>Restore a previous backup of the database by uploading it.</p>
        <p v-if="detectedFormat" class="text-grey-7 text-caption">
          Detected format:
          <span
            :class="detectedFormat.startsWith('BrewLogger') ? 'app-badge app-badge--warning text-dark' : 'app-badge app-badge--positive'"
            >{{ detectedFormat }}</span
          >
          <span v-if="detectedFormat.startsWith('BrewLogger')" class="q-ml-sm">
            pour events will be connected to auto-created vessels (one per batch)
          </span>
        </p>
      </div>
    </div>

    <div class="row">
      <form class="col-12 backup-restore-form" @submit.prevent="restore()">
        <div class="row q-col-gutter-md">
        <div class="col-md-12">
          <div class="backup-file-picker">
            <label class="app-field-label" for="restore-file">Backup file</label>
            <div class="backup-file-picker__control">
              <q-icon name="attach_file" aria-hidden="true" />
              <input
              id="restore-file"
              class="backup-file-picker__input"
              type="file"
              accept=".txt,.json"
              :disabled="global.disabled"
              aria-label="Select backup file to restore"
              aria-describedby="restore-file-hint"
              @change="selectRestoreFile"
              />
              <q-icon name="folder_open" aria-hidden="true" />
            </div>
            <div id="restore-file-hint" class="text-caption text-grey-7 q-mt-xs">
              Choose a .txt or .json backup file
            </div>
          </div>
        </div>

        <div class="col-md-3">
          <p></p>
          <app-button
            type="submit"
            variant="primary"
            value="upload"
            :disabled="global.disabled || !fileSelected"
            :aria-busy="restoreInProgress"
            :aria-label="restoreInProgress ? 'Restoring backup' : 'Restore selected backup'"
          >
            <span
              v-if="restoreInProgress"
              class="app-spinner app-spinner--small"
              role="status"
              aria-hidden="true"
            ></span>
            <span v-if="restoreInProgress">&nbsp;</span>Restore
          </app-button>
        </div>

        <div v-if="restoreProgress > 0" class="col-md-12">
          <p></p>
          <AppProgress :progress="restoreProgress"></AppProgress>
        </div>
        </div>
      </form>
    </div>

    <AppConfirmDialog
      :callback="confirmRestoreCallback"
      :message="confirmRestoreMessage"
      id="confirmRestore"
      title="Restore backup"
      :disabled="global.disabled"
    />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { batchStore, deviceStore, tapStore, vesselStore, global } from '@/modules/pinia'
import { apiFetch } from '@/modules/apiClient'
import { download } from '@/modules/utils'
import { describeBackupFormat } from '@/modules/backup/detectFormat'
import { logDebug, logError, logInfo } from '@/ui'
import {
  createBrewGraphBackup,
  processBrewGraphRestore,
  processBrewLoggerRestore
} from '@/modules/backup'

const restoreProgress = ref(0)
const backupProgress = ref(-1)
const restoreFile = ref(null)
const restoreInProgress = ref(false)
const detectedFormat = ref('')
const confirmRestoreMessage = ref(
  'Restoring will permanently delete all current devices, batches, taps and ' +
    'vessels before loading the backup. This cannot be undone. Continue?'
)

const fileSelected = computed(() => {
  return restoreFile.value instanceof File && /\.(txt|json)$/i.test(restoreFile.value.name)
})

watch(restoreFile, (file) => {
  detectedFormat.value = ''
  if (fileSelected.value) peekFormat(file)
})

function peekFormat(file) {
  const reader = new FileReader()
  reader.addEventListener('load', (e) => {
    try {
      const data = JSON.parse(e.target.result)
      detectedFormat.value = describeBackupFormat(data)
    } catch {
      detectedFormat.value = 'Unknown (parse error)'
    }
  })
  reader.readAsText(file)
}

function selectRestoreFile(event) {
  restoreFile.value = event.target?.files?.[0] ?? null
}

async function fetchBatchList() {
  try {
    const res = await apiFetch('GET', 'batches?pageSize=200')
    if (!res.ok) return null
    const json = await res.json()
    return json.items ?? json
  } catch {
    return null
  }
}

async function createBackup() {
  logDebug('BackupView.createBackup()')
  const releaseBusy = global.acquireBusy()
  backupProgress.value = 0

  try {
    const batchList = await fetchBatchList()
    if (batchList === null) {
      global.messageError = 'Failed to fetch batches'
      return
    }

    const backup = await createBrewGraphBackup({
      baseURL: global.baseURL,
      token: global.token,
      onProgress: () => {
        backupProgress.value =
          batchList.length > 0 ? Math.min(backupProgress.value + 100 / batchList.length, 100) : 100
      }
    })

    if (!backup) {
      global.messageError = 'Failed to create backup'
    } else {
      download(JSON.stringify(backup, null, 2), 'text/plain', 'brewgraph_backup.txt')
    }
  } catch (error) {
    logError('BackupView.createBackup()', 'Exception:', error)
    global.messageError = error instanceof Error && error.message
      ? `Failed to create backup: ${error.message}`
      : 'Failed to create backup'
  }

  finally {
    backupProgress.value = -1
    releaseBusy()
  }
}

function buildRestoreDeps(data) {
  let totalSteps = 50
  if (data?.meta?.software === 'BrewGraph') {
    totalSteps =
      (data.devices?.length ?? 0) +
      (data.batches?.length ?? 0) * 3 +
      (data.taps?.length ?? 0) +
      (data.vessels?.length ?? 0)
  } else if (data?.meta?.software === 'BrewLogger') {
    const batchesWithPours = (data.batches ?? []).filter((b) => (b.pour?.length ?? 0) > 0).length
    totalSteps = (data.devices?.length ?? 0) + (data.batches?.length ?? 0) * 3 + batchesWithPours
  }
  const increment = 100 / Math.max(totalSteps, 1)
  return {
    baseURL: global.baseURL,
    token: global.token,
    onProgress: () => {
      restoreProgress.value = Math.min(restoreProgress.value + increment, 99)
    },
    refreshDevices: async () => {
      return deviceStore.getDeviceList()
    },
    refreshBatches: async () => {
      return batchStore.getBatchList()
    },
    refreshTaps: async () => {
      return tapStore.getTapList()
    },
    refreshVessels: async () => {
      return vesselStore.getVesselList()
    }
  }
}

/**
 * Describe a partly-successful restore.
 *
 * Returns '' when everything landed. Otherwise names what did not, per category,
 * because "some items failed" gives no idea whether to retry, edit the file, or
 * accept the result.
 */
function describeRestoreFailures(report) {
  if (!report) return ''
  const parts = []
  // Singular and plural are both spelled out: appending "s" turns "batch" into
  // "batchs".
  for (const [one, many, counts] of [
    ['device', 'devices', report.devices],
    ['batch', 'batches', report.batches],
    ['tap', 'taps', report.taps],
    ['vessel', 'vessels', report.vessels],
    ['reading', 'readings', report.readings],
    ['pour', 'pours', report.pours]
  ]) {
    if (!counts?.failed) continue
    const total = counts.failed + counts.restored
    // The noun agrees with the total, not the failure count: "1 of 17 devices",
    // not "1 of 17 device".
    parts.push(`${counts.failed} of ${total} ${total === 1 ? one : many}`)
  }
  return parts.join(', ')
}

const MAX_PROBLEMS_SHOWN = 5

/**
 * Name what was rejected and why, capped so a file with hundreds of bad batches
 * still gives a readable message. Returns '' when the report carries no detail.
 */
function describeProblems(report) {
  const problems = report?.problems ?? []
  if (!problems.length) return ''
  const shown = problems.slice(0, MAX_PROBLEMS_SHOWN)
  const more = problems.length - shown.length
  let text = ' ' + shown.map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join('. ') + '.'
  if (more > 0) text += ` …and ${more} more.`
  // The API keeps field-level validation detail out of its responses and in its log.
  if (problems.some((p) => p.includes('invalid'))) {
    text += ' The API server log names the rejected field.'
  }
  return text
}

async function runRestore(fn, releaseBusy = global.acquireBusy()) {
  global.clearMessages()
  restoreProgress.value = 0
  try {
    const report = await fn()
    restoreProgress.value = 100

    /*
     * A restore that skipped entities is not a success.
     *
     * Individual POSTs failing does not throw — the restore continues so one bad
     * batch cannot cost you the other 37 — so reaching this line only means nothing
     * fatal happened. Printing "Restore successful" regardless would let a
     * BrewLogger backup that restores 0 of 17 devices look like a clean run.
     * Data from the file is missing from the database, so it is an error, not a
     * warning.
     */
    // A problem can exist without a lost item (a batch restored but not re-archived).
    const failed = describeRestoreFailures(report)
    const problems = describeProblems(report)
    if (failed || problems) {
      global.messageError =
        'Restore incomplete' + (failed ? ` — could not restore ${failed}.` : '.') + problems
    } else {
      global.messageSuccess = 'Restore successful'
    }
  } catch (error) {
    logError('BackupView.runRestore()', error)
    // Restore throws messages written for the brewer (wrong file type, nothing
    // changed, ...); show them rather than a bare "failed".
    global.messageError = error?.message ? `Restore failed: ${error.message}` : 'Restore failed'
  }
  finishRestore(releaseBusy)
}

function finishRestore(releaseBusy) {
  global.restoreInProgress = false
  releaseBusy()
  restoreInProgress.value = false
  restoreFile.value = null
  detectedFormat.value = ''
  setTimeout(() => {
    restoreProgress.value = 0
  }, 2000)
}

function restore() {
  logDebug('BackupView.restore()')

  if (!fileSelected.value) {
    global.messageError = 'You need to select a file to restore data from'
    return
  }

  // Restore deletes every existing device, batch, tap and vessel before loading
  // the file — confirm before that step, not after, same as any other
  // destructive action in this app.
  document.getElementById('confirmRestore').click()
}

const confirmRestoreCallback = (result) => {
  logDebug('BackupView.confirmRestoreCallback()', result)
  if (result) performRestore()
}

function performRestore() {
  if (!fileSelected.value) {
    global.messageError = 'You need to select a file to restore data from'
    return
  }

  const releaseBusy = global.acquireBusy()
  global.restoreInProgress = true
  restoreInProgress.value = true
  logInfo('BackupView.performRestore()', 'Selected file: ' + restoreFile.value.name)

  const reader = new FileReader()
  reader.addEventListener('load', async (e) => {
    try {
      const data = JSON.parse(e.target.result)
      const { software } = data?.meta ?? {}

      // A BrewGraph backup is a brewgraph-batch-export-v1 document and carries
      // no `meta` block.
      // BrewLogger files keep their own `meta`, because that is their format.
      if (data?.schemaVersion === '1') {
        if (data.mode === 'backup') {
          await runRestore(() => processBrewGraphRestore(data, buildRestoreDeps(data)), releaseBusy)
        } else {
          // An ml/archive export records what was measured, not what was
          // stored: no ids, no device configuration, no vessels or taps.
          // Restoring from one would leave every device unconfigured and
          // unlinked, so say why rather than half-succeed.
          global.messageError =
            `This is a "${data.mode ?? 'unknown'}" export, not a backup. ` +
            'Exports contain measurements; a restore needs a backup file.'
          finishRestore(releaseBusy)
        }
      } else if (software === 'BrewGraph') {
        global.messageError =
          'This is an old BrewGraph backup format that is no longer supported. ' +
          'Create a new backup from the current version.'
        finishRestore(releaseBusy)
      } else if (software === 'BrewLogger') {
        await runRestore(() => processBrewLoggerRestore(data, buildRestoreDeps(data)), releaseBusy)
      } else {
        global.messageError = 'Unknown format, unable to process'
        finishRestore(releaseBusy)
      }
    } catch (error) {
      logError('BackupView.performRestore()', error)
      global.messageError = 'Unable to parse backup file.'
      finishRestore(releaseBusy)
    }
  })
  reader.readAsText(restoreFile.value)
}
</script>

<style scoped>
.backup-file-picker {
  width: min(420px, 100%);
  max-width: 100%;
}

.backup-file-picker__control {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 48px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--app-radius);
  background: var(--bg-surface);
}

.backup-file-picker__input {
  flex: 1 1 auto;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  color: var(--text-primary);
}
</style>
