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

import { logInfo, logDebug } from '@/ui'
import { VESSEL_STATUS_CLEAN, VESSEL_STATUS_SERVING } from '@/modules/classes'
import { buildExportDocument } from './exportDocument'
import type { ExportDocument, SourceBatch, SourceDevice } from './exportDocument'
import type {
  BrewLoggerBackup,
  BrewLoggerBatchRecord,
  BrewLoggerDeviceRecord,
  BrewLoggerGravityRecord,
  BrewLoggerPressureRecord,
  BrewGraphBatchRecord,
  BrewGraphDeviceRecord,
  BrewGraphGravityRecord,
  BrewGraphPourEventRecord,
  BrewGraphPressureRecord,
  BrewGraphTapRecord,
  BrewGraphVesselRecord
} from './types'
import {
  processBrewGraphRestore,
  type RestoreDeps,
  type RestoreReport
} from './brewgraphRestore'
import { validateBrewloggerDocument } from './validateDocument'

// -273 is the hardware "no sensor" sentinel from the pressure device firmware
const PRESSURE_TEMP_NO_SENSOR = -273

/*
 * BrewLogger stores the device kind as free text in `software`, capitalised and
 * hyphenated the way the firmware presents it: "Gravitymon", "Chamber-Controller",
 * "Gravitymon-Gateway". BrewGraph's DeviceType enum is lowercase with underscores
 * ("gravitymon", "chamber_controller"), and the API validates against a registry
 * built from it — so passing `software` through unchanged made every device POST
 * fail with `unregistered device_type: 'Gravitymon'`.
 *
 * Seen in a real 17-device export: every one was rejected, and the restore reported
 * success anyway. Lowercasing and swapping "-" for "_" maps all five known kinds.
 *
 * An empty or unknown `software` maps to null, not '': the API rejects '' as an
 * unregistered type but accepts no type, so the device is kept and the brewer can
 * set its type afterwards.
 */
const KNOWN_DEVICE_TYPES = new Set([
  'ispindel',
  'gravitymon',
  'gravitymon_gateway',
  'pressuremon',
  'chamber_controller',
  'kegmon'
])

export function mapDeviceType(software: string | null | undefined): string | null {
  const normalised = (software ?? '').trim().toLowerCase().replace(/-/g, '_')
  return KNOWN_DEVICE_TYPES.has(normalised) ? normalised : null
}

export function mapBrewLoggerDevice(d: BrewLoggerDeviceRecord): BrewGraphDeviceRecord {
  return {
    id: String(d.id),
    name: d.mdns ?? '',
    chipId: d.chipId ?? '',
    chipFamily: d.chipFamily ?? '',
    deviceType: mapDeviceType(d.software),
    mdns: d.mdns ?? '',
    config: d.config ?? '',
    // `||`, not `??`: BrewLogger writes bleColor as an empty string when unset (all
    // 17 devices in the reference export), and '' is not a valid DeviceColor.
    deviceColor: d.bleColor || 'white',
    url: d.url ?? '',
    description: d.description ?? '',
    collectLogs: d.collectLogs ?? false,
    token: '',
    fermentationStep: d.fermentationStep ?? [],
    batchId: null,
    batchRole: null,
    vesselId: null
  }
}

export function mapBrewLoggerGravity(
  g: BrewLoggerGravityRecord,
  batchId: string
): BrewGraphGravityRecord {
  return {
    id: g.id,
    batchId,
    temperature: g.temperature ?? null,
    gravity: g.gravity,
    velocity: g.velocity ?? null,
    angle: g.angle ?? null,
    battery: g.battery ?? null,
    rssi: g.rssi ?? null,
    runTime: g.runTime ?? null,
    excluded: !g.active,
    createdAt: g.created,
    deviceId: null
  }
}

export function mapBrewLoggerPressure(
  p: BrewLoggerPressureRecord,
  batchId: string
): BrewGraphPressureRecord {
  return {
    id: p.id,
    batchId,
    temperature: p.temperature === PRESSURE_TEMP_NO_SENSOR ? null : (p.temperature ?? null),
    pressure: p.pressure,
    battery: p.battery ?? null,
    rssi: p.rssi ?? null,
    runTime: p.runTime ?? null,
    excluded: !p.active,
    createdAt: p.created,
    deviceId: null
  }
}

export function mapBrewLoggerBatchToVessel(b: BrewLoggerBatchRecord): BrewGraphVesselRecord | null {
  if (!b.pour?.length) return null

  const vesselId = `vessel_batch_${b.id}`
  const batchId = String(b.id)

  // Sort pours chronologically to derive fill date and final remaining volume
  const sorted = [...b.pour].sort((a, z) => a.created.localeCompare(z.created))
  const fillDate = b.brewDate || sorted[0].created.slice(0, 10)
  const totalVolume = sorted[0].maxVolume
  const volumeRemaining = sorted[sorted.length - 1].volume

  const pourEvents: BrewGraphPourEventRecord[] = sorted.map((p) => ({
    id: String(p.id),
    vesselId,
    pourAmount: p.pour,
    volumeRemaining: p.volume,
    isManual: false,
    excluded: false,
    createdAt: p.created
  }))

  return {
    id: vesselId,
    batchId,
    tapId: null,
    vesselNumber: null,
    vesselType: 'keg',
    name: `${b.name ?? batchId} Keg`,
    fillDate,
    totalVolume,
    volumeRemaining,
    bottleVolume: null,
    bottleCount: null,
    bottlesRemaining: null,
    status: volumeRemaining > 0 ? VESSEL_STATUS_SERVING : VESSEL_STATUS_CLEAN,
    location: '',
    notes: 'Auto-created from BrewLogger import',
    pourEvents
  }
}

/*
 * BrewLogger has no batch lifecycle, but BrewGraph requires one. A batch still
 * accepting readings is fermenting; one with pour history sits in a keg; anything
 * else is finished.
 */
export function mapBrewLoggerStatus(b: BrewLoggerBatchRecord): string {
  if (b.active) return 'fermenting'
  if (b.pour?.length) return 'packaged'
  return 'archived'
}

export function mapBrewLoggerBatch(b: BrewLoggerBatchRecord): BrewGraphBatchRecord {
  const batchId = String(b.id)
  return {
    id: batchId,
    name: b.name ?? '',
    description: b.description ?? '',
    acceptIngest: b.active ?? false,
    status: mapBrewLoggerStatus(b),
    // An empty string is not a date; the API rejects it where it accepts null.
    brewDate: b.brewDate || null,
    style: b.style ?? '',
    brewer: b.brewer ?? '',
    abv: b.abv ?? 0,
    ebc: b.ebc ?? 0,
    ibu: b.ibu ?? 0,
    fg: b.fg ?? 0,
    og: b.og ?? 0,
    carbonationVolumes: null,
    brewfatherBatchId: b.brewfatherId ?? '',
    notes: '',
    fermentationChamber: null,
    fermentationSteps: b.fermentationSteps ?? '',
    gravity: (b.gravity ?? []).map((g) => mapBrewLoggerGravity(g, batchId)),
    pressure: (b.pressure ?? []).map((p) => mapBrewLoggerPressure(p, batchId))
  }
}

export function mapBrewLoggerToBrewGraph(source: BrewLoggerBackup): ExportDocument {
  logInfo(
    'brewloggerRestore.mapBrewLoggerToBrewGraph()',
    'Mapping BrewLogger backup to BrewGraph format'
  )

  // Build chipId → string device ID map for resolving batch→device links
  const chipIdToDeviceId = new Map<string, string>()
  for (const d of source.devices ?? []) {
    if (d.chipId) chipIdToDeviceId.set(d.chipId, String(d.id))
  }
  logDebug(
    'brewloggerRestore.mapBrewLoggerToBrewGraph()',
    'chipIdToDeviceId',
    Object.fromEntries(chipIdToDeviceId)
  )

  const vessels: BrewGraphVesselRecord[] = (source.batches ?? [])
    .map(mapBrewLoggerBatchToVessel)
    .filter((v): v is BrewGraphVesselRecord => v !== null)
  const vesselIdByBatchId = new Map(vessels.map((v) => [v.batchId, v.id]))

  const taps: BrewGraphTapRecord[] = []
  let tapNumber = 1

  for (const b of source.batches ?? []) {
    if (!b.tapList) continue
    const vessel = vessels.find((v) => v.id === `vessel_batch_${b.id}`)
    if (!vessel) continue
    const tapId = `tap_batch_${b.id}`
    taps.push({
      id: tapId,
      name: b.name ?? String(b.id),
      tapNumber: tapNumber++,
      location: '',
      notes: 'Auto-created from BrewLogger import'
    })
    vessel.tapId = tapId
  }

  if (source.pour?.length) {
    logInfo(
      'brewloggerRestore.mapBrewLoggerToBrewGraph()',
      'Skipping top-level pour records (not supported in BrewGraph format)'
    )
  }

  if (vessels.length > 0) {
    logInfo(
      'brewloggerRestore.mapBrewLoggerToBrewGraph()',
      `Auto-created ${vessels.length} vessel(s) and ${taps.length} tap(s) from BrewLogger batch pour data`
    )
  }

  const devices = (source.devices ?? []).map(mapBrewLoggerDevice)
  // Set batchId/batchRole on fermentation devices. A BrewLogger batch that has
  // pour history also becomes a BrewGraph vessel; its pressure device belongs to
  // that vessel once packaged, so derive the vessel link from the same batch.
  for (const b of source.batches ?? []) {
    const batchId = String(b.id)
    if (b.chipIdGravity) {
      const devId = chipIdToDeviceId.get(b.chipIdGravity)
      if (devId) {
        const dev = devices.find((d) => d.id === devId)
        if (dev) {
          dev.batchId = batchId
          dev.batchRole = 'gravity'
        }
      }
    }
    if (b.chipIdPressure) {
      const devId = chipIdToDeviceId.get(b.chipIdPressure)
      if (devId) {
        const dev = devices.find((d) => d.id === devId)
        if (dev) {
          const vesselId = vesselIdByBatchId.get(batchId)
          if (vesselId) {
            // A device reports readings to either the active batch or a stored/on-tap
            // vessel. Keeping both links would make future pressure readings go to
            // the vessel anyway, while leaving a misleading batch assignment in UI.
            dev.vesselId = vesselId
          } else {
            dev.batchId = batchId
            dev.batchRole = 'pressure'
          }
        }
      }
    }
    logDebug(
      'brewloggerRestore.mapBrewLoggerToBrewGraph()',
      `batch ${b.id} chipIdGravity=${b.chipIdGravity} chipIdPressure=${b.chipIdPressure}`
    )
  }

  // Assembled through the shared builder so a BrewLogger import lands in the
  // same shape as a native backup — one destination format, one restore path.
  // `backup` mode because the mapping produces ids and device links that the
  // restore needs to rebuild the relationships.
  return buildExportDocument({
    batches: (source.batches ?? []).map(mapBrewLoggerBatch) as unknown as SourceBatch[],
    devices: devices as unknown as SourceDevice[],
    taps,
    vessels,
    mode: 'backup'
  })
}

/**
 * Import a BrewLogger backup, validating it before anything is touched.
 *
 * A malformed BrewLogger file must be rejected before mapping — the mapping
 * functions coalesce missing fields to defaults, so a wrong-shaped file left
 * unvalidated would produce a plausible-looking document and import as
 * partial or subtly wrong data. That is
 * the worst failure mode available — worse than a crash, because nothing tells the
 * user their history is now wrong.
 *
 * Validation happens here rather than inside `mapBrewLoggerToBrewGraph`, which is
 * also called by the tests and by the offline converter with already-checked input.
 *
 * The check is deliberately permissive (see `brewlogger-import.schema.json`): this
 * is a format we do not control, so it catches wrong types and missing essentials
 * while accepting unknown fields a future BrewLogger version might add.
 */
export async function processBrewLoggerRestore(
  source: BrewLoggerBackup,
  deps: RestoreDeps
): Promise<RestoreReport> {
  const problem = validateBrewloggerDocument(source)
  if (problem) {
    throw new Error(
      'This does not look like a BrewLogger export, so nothing has been ' +
        'changed: ' +
        problem
    )
  }
  const mapped = mapBrewLoggerToBrewGraph(source)
  return processBrewGraphRestore(mapped, deps)
}
