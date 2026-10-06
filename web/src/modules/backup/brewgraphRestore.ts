/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { logDebug, logError, logInfo } from '@/ui'
import type { BrewGraphTapRecord, BrewGraphVesselRecord } from './types'
import type { ExportDocument } from './exportDocument'
import { validateExportDocument } from './validateDocument'
import { apiPost } from './restoreApiAdapter'
import {
  archiveBatches,
  restoreBatches,
  restoreDeviceAssignments,
  restoreDevices,
  restoreTaps,
  restoreVessels
} from './restoreEntities'
import { deleteAll, emptyRestoreReport } from './restoreSupport'
import type { PendingArchive, RestoreDeps, RestoreReport } from './restoreTypes'

export { rejectionReason, restoreFailureCount } from './restoreSupport'
export type { RestoreDeps, RestoreReport } from './restoreTypes'

/**
 * Restore a validated full backup: collect and purge old rows, coordinate
 * entity writers in dependency order, then refresh the visible stores.
 */
export async function processBrewGraphRestore(
  json: ExportDocument,
  deps: RestoreDeps
): Promise<RestoreReport> {
  const report = emptyRestoreReport()
  logDebug(
    'brewgraphRestore.processBrewGraphRestore()',
    'schemaVersion',
    json?.schemaVersion,
    'mode',
    json?.mode
  )
  const apiURL = deps.baseURL + 'api/'

  if (json?.schemaVersion !== '1') {
    throw new Error(
      'Not a BrewGraph backup file: expected schemaVersion "1", got ' +
        String(json?.schemaVersion)
    )
  }
  if (json.mode !== 'backup') {
    throw new Error(
      'This file is a "' +
        String(json.mode) +
        '" export, which records measurements rather than the full database. ' +
        'Restore needs a backup file.'
    )
  }

  // Validate the complete backup before the first destructive request.
  const problem = validateExportDocument(json)
  if (problem) {
    throw new Error(
      'This backup file does not match the BrewGraph export format, so nothing ' +
        'has been changed: ' +
        problem
    )
  }

  logDebug('brewgraphRestore.processBrewGraphRestore()', 'Deleting existing data')
  const deleteFailures = [
    ...(await deleteAll(apiURL + 'devices', deps)),
    ...(await deleteAll(apiURL + 'vessels', deps)),
    ...(await deleteAll(apiURL + 'taps', deps)),
    ...(await deleteAll(apiURL + 'batches', deps))
  ]
  if (deleteFailures.length > 0) {
    throw new Error(
      'Could not delete existing data before restoring (' +
        deleteFailures.length +
        ' item(s) failed: ' +
        deleteFailures.slice(0, 5).join(', ') +
        (deleteFailures.length > 5 ? ', …' : '') +
        '). Nothing has been recreated yet — fix the issue and try again.'
    )
  }

  // DELETE is soft; purge unique-key occupants only after every delete succeeded.
  logDebug('brewgraphRestore.processBrewGraphRestore()', 'Purging soft-deleted data')
  const purgeRes = await apiPost(apiURL + 'system/purge-deleted', deps.token, {})
  if (!purgeRes.ok) {
    throw new Error(
      'Could not clear existing data before restoring (status ' +
        purgeRes.status +
        '). Nothing has been recreated yet — fix the issue and try again.'
    )
  }

  logDebug('brewgraphRestore.processBrewGraphRestore()', 'Restoring devices')
  const { chipToNew, assignments: deviceAssignments } = await restoreDevices(
    json.devices ?? [],
    deps,
    report
  )

  logDebug('brewgraphRestore.processBrewGraphRestore()', 'Restoring batches')
  const archiveLater: PendingArchive[] = []
  const batchIdMap = await restoreBatches(
    json.batches ?? [],
    chipToNew,
    deps,
    report,
    archiveLater
  )

  logDebug('brewgraphRestore.processBrewGraphRestore()', 'Restoring taps')
  const tapIdMap = await restoreTaps(
    (json.taps ?? []) as BrewGraphTapRecord[],
    apiURL,
    deps,
    report
  )

  logDebug('brewgraphRestore.processBrewGraphRestore()', 'Restoring vessels + pour events')
  const vesselIdMap = await restoreVessels(
    (json.vessels ?? []) as BrewGraphVesselRecord[],
    batchIdMap,
    tapIdMap,
    chipToNew,
    apiURL,
    deps,
    report
  )

  logDebug('brewgraphRestore.processBrewGraphRestore()', 'Restoring device assignments')
  await restoreDeviceAssignments(deviceAssignments, batchIdMap, vesselIdMap, apiURL, deps)

  logDebug('brewgraphRestore.processBrewGraphRestore()', 'Archiving batches')
  await archiveBatches(archiveLater, apiURL, deps, report)
  logInfo('brewgraphRestore.processBrewGraphRestore()', 'Restore complete')

  const [deviceOk, batchOk] = await Promise.all([deps.refreshDevices(), deps.refreshBatches()])
  if (!deviceOk)
    logError('brewgraphRestore.processBrewGraphRestore()', 'Failed to refresh device list')
  if (!batchOk)
    logError('brewgraphRestore.processBrewGraphRestore()', 'Failed to refresh batch list')
  if (deps.refreshTaps) await deps.refreshTaps()
  if (deps.refreshVessels) await deps.refreshVessels()

  return report
}
