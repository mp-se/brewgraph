/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 *
 * This file is part of BrewGraph. For open source use it is licensed under
 * the GNU General Public License v3.0. For commercial use without source
 * disclosure, a separate Commercial License is required.
 * See LICENSE for details.
 */

import { logDebug, logError } from '@/ui'
import type { BrewGraphTapRecord, BrewGraphVesselRecord } from './types'
import type { ExportDocument } from './exportDocument'
import { apiPost, apiPatch } from './restoreApiAdapter'
import type { DeviceAssignment, PendingArchive, RestoreDeps, RestoreReport } from './restoreTypes'
import {
  mapBatchPayload,
  mapBatchReading,
  mapDeviceAssignment,
  mapDevicePayload,
  mapPourEvent,
  mapTapPayload,
  mapVesselPayload,
  mapVesselReading
} from './restoreMapping'
import {
  errorDetail,
  postChunked,
  recordRejection
} from './restoreSupport'

// ---- restore-plan executor: recreate entities, remap ids, track outcome ----

export async function restoreDevices(
  devices: ExportDocument['devices'],
  deps: RestoreDeps,
  report: RestoreReport
): Promise<{
  oldToNew: Map<string, string>
  chipToNew: Map<string, string>
  assignments: Map<string, DeviceAssignment>
}> {
  const oldToNew = new Map<string, string>()
  // chipId -> new device id. Readings reference devices by chipId in the export
  // format, and chipId is the one identifier that survives a restore unchanged,
  // so it is what relinks them.
  const chipToNew = new Map<string, string>()
  const assignments = new Map<string, DeviceAssignment>()
  for (const d of devices) {
    const { payload, assignment } = mapDevicePayload(d)

    const res = await apiPost(deps.baseURL + 'api/devices', deps.token, payload)
    if (res.ok) {
      const json = await res.json()
      logDebug(
        'brewgraphRestore.restoreDevices()',
        `device oldId=${d.id} chipId=${d.chipId} → newId=${json.id}`
      )
      report.devices.restored++
      if (d.id) oldToNew.set(d.id, json.id as string)
      if (d.chipId) chipToNew.set(d.chipId, json.id as string)
      assignments.set(json.id as string, assignment)
    } else {
      report.devices.failed++
      recordRejection(report, `device "${d.name || d.chipId}"`, res.status)
      logError(
        'brewgraphRestore.restoreDevices()',
        `POST failed for device id=${d.id} chipId=${d.chipId} status=${res.status}`
      )
    }
    deps.onProgress()
  }
  return { oldToNew, chipToNew, assignments }
}

export async function restoreDeviceAssignments(
  assignments: Map<string, DeviceAssignment>,
  batchIdMap: Map<string, string>,
  vesselIdMap: Map<string, string>,
  apiURL: string,
  deps: RestoreDeps
): Promise<void> {
  for (const [newDeviceId, asgn] of assignments) {
    const payload = mapDeviceAssignment(asgn, batchIdMap, vesselIdMap)
    if (!payload) continue
    const res = await apiPatch(apiURL + 'devices/' + newDeviceId, deps.token, payload)
    if (!res.ok) {
      logError(
        'brewgraphRestore.restoreDeviceAssignments()',
        `PATCH failed for device ${newDeviceId} status=${res.status}`
      )
    }
  }
}

export async function restoreBatches(
  batches: ExportDocument['batches'],
  chipToNew: Map<string, string>,
  deps: RestoreDeps,
  report: RestoreReport,
  archiveLater: PendingArchive[]
): Promise<Map<string, string>> {
  const oldToNew = new Map<string, string>()
  for (const b of batches) {
    const { payload, archived } = mapBatchPayload(b)
    /*
     * An archived batch is read-only: the API refuses its readings, notes, vessel
     * links and device assignments. Create it as fermenting so everything can be
     * attached, and archive it once the whole restore is done (`archiveBatches`).
     */
    // `dryHops` is kept — `BatchCreate.dryHops` bulk-creates them alongside the
    // batch itself. Deleting it, as this used to, meant an exported batch's
    // dry hops were never restored at all.
    //
    // og/fg are left as `null` when the export carries `null` (not yet
    // measured) — coercing to `0` would silently turn "not measured" into "a
    // real, wrong measurement of zero. Preserve nulls unchanged.
    logDebug('brewgraphRestore.restoreBatches()', `batch "${b.name}")`)

    const res = await apiPost(deps.baseURL + 'api/batches', deps.token, payload)
    deps.onProgress()

    /*
     * Check the status before reading the id.
     *
     * On a rejected batch, `json.id` is `undefined` — posting that batch's readings
     * against `/api/batches/undefined/gravity/bulk` would be a second guaranteed
     * failure that only masks the first. Skip the batch's readings instead —
     * without a batch there is nothing to attach them to — but count them as
     * failed: they are lost with the batch, and the report must say so.
     */
    if (!res.ok) {
      report.batches.failed++
      recordRejection(report, `batch "${b.name}"`, res.status)
      report.readings.failed +=
        (b.gravityReadings?.length ?? 0) +
        (b.pressureReadings?.length ?? 0) +
        (b.temperatureReadings?.length ?? 0)
      logError(
        'brewgraphRestore.restoreBatches()',
        `POST failed for batch "${b.name}" status=${res.status}`,
        await errorDetail(res)
      )
      continue
    }
    const json = await res.json()
    report.batches.restored++

    const newId = json.id as string
    if (b.id) oldToNew.set(b.id, newId)
    if (archived) archiveLater.push({ id: newId, name: b.name ?? '' })

    // Readings carry `deviceChipId`, not a device id. That is what makes the
    // relink correct: the old `deviceId` in a 2.0 backup pointed at a row that
    // no longer exists after restore recreates devices, so readings came back
    // attached to nothing. chipId is stable across the restore.
    const gravity = (b.gravityReadings ?? []).map((reading) =>
      mapBatchReading(reading, newId, chipToNew)
    )
    const pressure = (b.pressureReadings ?? []).map((reading) =>
      mapBatchReading(reading, newId, chipToNew)
    )
    const temperature = (b.temperatureReadings ?? []).map((reading) =>
      mapBatchReading(reading, newId, chipToNew)
    )

    // Each array is posted in ≤1,000-item chunks — the API's own
    // `bulk_insert_*` cap — with every chunk's status checked and counted, so
    // a rejected chunk is visible in the report instead of silently dropped.
    await postChunked(
      deps.baseURL + 'api/batches/' + newId + '/gravity/bulk',
      deps.token,
      gravity,
      report.readings,
      deps.onProgress,
      report,
      `gravity readings of batch "${b.name}"`
    )
    await postChunked(
      deps.baseURL + 'api/batches/' + newId + '/pressure/bulk',
      deps.token,
      pressure,
      report.readings,
      deps.onProgress,
      report,
      `pressure readings of batch "${b.name}"`
    )
    await postChunked(
      deps.baseURL + 'api/batches/' + newId + '/temp/bulk',
      deps.token,
      temperature,
      report.readings,
      deps.onProgress,
      report,
      `temperature readings of batch "${b.name}"`
    )

    // Notes have no bulk endpoint, so they go one at a time. `createdAt` is sent
    // explicitly: `BatchNoteCreate` accepts it, and without it every restored note
    // would carry the restore's timestamp instead of when it was written — which
    // would destroy the ordering that makes a note log readable.
    for (const n of b.batchNotes ?? []) {
      if (!n.content) continue
      await apiPost(deps.baseURL + 'api/batches/' + newId + '/notes', deps.token, {
        content: n.content,
        createdAt: n.createdAt ?? undefined,
        noteType: n.noteType ?? undefined,
        testResult: n.testResult ?? undefined
      })
    }
  }
  return oldToNew
}

/**
 * Return batches that were archived in the backup to that state. Runs last:
 * archiving makes a batch read-only, so it has to wait until readings, notes,
 * vessels and device assignments are attached.
 */
export async function archiveBatches(
  pending: PendingArchive[],
  apiURL: string,
  deps: RestoreDeps,
  report: RestoreReport
): Promise<void> {
  for (const p of pending) {
    const res = await apiPatch(apiURL + 'batches/' + p.id, deps.token, { status: 'archived' })
    if (!res.ok) {
      recordRejection(report, `archiving batch "${p.name}" (it was restored as fermenting)`, res.status)
      logError(
        'brewgraphRestore.archiveBatches()',
        `PATCH failed for batch ${p.id} status=${res.status}`,
        await errorDetail(res)
      )
    }
  }
}

export async function restoreTaps(
  taps: BrewGraphTapRecord[],
  apiURL: string,
  deps: RestoreDeps,
  report: RestoreReport
): Promise<Map<string, string>> {
  const oldToNew = new Map<string, string>()
  for (const t of taps) {
    const payload = mapTapPayload(t)
    const res = await apiPost(apiURL + 'taps', deps.token, payload)
    if (res.ok) {
      const json = await res.json()
      report.taps.restored++
      oldToNew.set(t.id, json.id as string)
    } else {
      report.taps.failed++
      recordRejection(report, `tap "${t.name}"`, res.status)
      logError('brewgraphRestore.restoreTaps()', `POST failed for tap "${t.name}" status=${res.status}`)
    }
    deps.onProgress()
  }
  return oldToNew
}

/**
 * Recreate vessels and their pour events, returning the old->new id map.
 *
 * **The map is the point.** This function must return the old->new vessel id map —
 * returning `void` would leave the caller's `vesselIdMap` empty, so
 * `restoreDeviceAssignments` would resolve every `vesselId` to `null`, silently
 * losing every device-to-vessel link on restore.
 */
export async function restoreVessels(
  vessels: BrewGraphVesselRecord[],
  batchIdMap: Map<string, string>,
  tapIdMap: Map<string, string>,
  chipToNew: Map<string, string>,
  apiURL: string,
  deps: RestoreDeps,
  report: RestoreReport
): Promise<Map<string, string>> {
  const oldToNew = new Map<string, string>()
  for (const v of vessels) {
    const payload = mapVesselPayload(v, batchIdMap, tapIdMap)
    const res = await apiPost(apiURL + 'vessels', deps.token, payload)
    if (!res.ok) {
      // Its pours and readings have nothing to attach to; they are lost with it.
      report.vessels.failed++
      recordRejection(report, `vessel "${v.name}"`, res.status)
      report.pours.failed += v.pourEvents?.length ?? 0
      report.readings.failed +=
        (v.temperatureReadings?.length ?? 0) + (v.pressureReadings?.length ?? 0)
      logError(
        'brewgraphRestore.restoreVessels()',
        'Failed to create vessel',
        res.status,
        await errorDetail(res)
      )
      continue
    }
    const newVessel = await res.json()
    report.vessels.restored++
    const newId = newVessel.id as string
    if (v.id) oldToNew.set(v.id, newId)

    // No vessel token is generated here: vessels have none. Integration and QR flows use the
    // *tap* token, which survives keg swaps — see spec-data-model.md §5.11.

    const pourRows = (v.pourEvents ?? []).map(mapPourEvent)
    await postChunked(
      apiURL + 'vessels/' + newId + '/pours/bulk',
      deps.token,
      pourRows,
      report.pours,
      deps.onProgress,
      report,
      `pours of vessel "${v.name}"`
    )

    const vesselTemperature = (v.temperatureReadings ?? []).map((reading) =>
      mapVesselReading(reading, newId, chipToNew)
    )
    const vesselPressure = (v.pressureReadings ?? []).map((reading) =>
      mapVesselReading(reading, newId, chipToNew)
    )
    await postChunked(
      apiURL + 'vessels/' + newId + '/temp/bulk',
      deps.token,
      vesselTemperature,
      report.readings,
      deps.onProgress,
      report,
      `temperature readings of vessel "${v.name}"`
    )
    await postChunked(
      apiURL + 'vessels/' + newId + '/pressure/bulk',
      deps.token,
      vesselPressure,
      report.readings,
      deps.onProgress,
      report,
      `pressure readings of vessel "${v.name}"`
    )
    deps.onProgress()
  }
  return oldToNew
}
