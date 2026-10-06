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

import { logDebug, logError, logInfo } from '@/ui'
import { apiFetch } from '@/modules/apiClient'
import { buildExportDocument } from './exportDocument'
import type { ExportDocument, SourceBatch, SourceDevice } from './exportDocument'

export interface BackupCreateDeps {
  baseURL: string
  token: string
  /**
   * Override for reading one batch. Leave unset: the default reads the plain API JSON. A getter
   * that returns the app's `Batch` class loses the data, because the class keeps it in private
   * `_`-prefixed fields that do not survive being spread into the export.
   */
  getBatch?: (id: string | number) => Promise<Record<string, unknown> | null>
  onProgress: () => void
}

async function fetchJson<T>(url: string, token: string): Promise<T | null> {
  try {
    const res = await apiFetch('GET', url, undefined, { baseURL: '', token, timeout: false })
    if (!res.ok) {
      logError('backupCreate.fetchJson()', 'HTTP error', res.status, url)
      return null
    }
    return (await res.json()) as T
  } catch (err) {
    logError('backupCreate.fetchJson()', 'Exception:', err, url)
    return null
  }
}

/**
 * Collect every item from an offset-paginated `{items, pages}` endpoint
 * (`Page[...]` — devices, batches, taps, vessels), following every page.
 *
 * A single `?pageSize=200` fetch silently truncates an installation with more
 * than 200 rows, and restore then deletes everything the backup never
 * captured. `null` on
 * failure, matching `fetchJson`'s own contract, so a fatal fetch here can
 * still abort the whole backup the same way a single-page failure used to.
 */
async function fetchAllPages<T>(url: string, token: string): Promise<T[] | null> {
  const items: T[] = []
  const sep = url.includes('?') ? '&' : '?'
  let page = 1
  for (;;) {
    const data = await fetchJson<{ items: T[]; pages: number }>(
      `${url}${sep}page=${page}&pageSize=200`,
      token
    )
    if (data === null) return null
    items.push(...(data.items ?? []))
    if (page >= (data.pages ?? 1)) break
    page++
  }
  return items
}

/**
 * Collect every item from a cursor-paginated `{items, nextCursor, hasMore}`
 * endpoint (`CursorPage[...]` — batch/vessel gravity, pressure and temp, pour
 * events, and batch notes). `includeExcluded=true` (the default) because a
 * backup is lossless against the reading tables — excluding a reading annotates
 * it, it does not authorise dropping it from a snapshot. Notes have no such
 * parameter, so they are fetched with `includeExcluded: false`.
 *
 * Fatal: a page that cannot be read throws, so the backup is not written. A file with a
 * silent gap in its readings or notes would restore as if it were complete.
 */
async function fetchAllCursor<T>(
  url: string,
  token: string,
  { includeExcluded = true }: { includeExcluded?: boolean } = {}
): Promise<T[]> {
  const items: T[] = []
  const sep = url.includes('?') ? '&' : '?'
  const excluded = includeExcluded ? '&includeExcluded=true' : ''
  let cursor: string | undefined
  for (;;) {
    const cursorParam = cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''
    const data = await fetchJson<{ items: T[]; nextCursor: string | null; hasMore: boolean }>(
      `${url}${sep}limit=1000${excluded}${cursorParam}`,
      token
    )
    if (data === null) {
      logError('backupCreate.fetchAllCursor()', 'Failed to fetch page', url)
      throw new Error(`Could not read ${url.replace(/^.*\/api\//, '')}`)
    }
    items.push(...(data.items ?? []))
    if (!data.hasMore || !data.nextCursor) break
    cursor = data.nextCursor
  }
  return items
}

/**
 * Fetch every sub-resource of one batch that `BatchListResponse`/`BatchResponse`
 * don't carry: reading *counts* stand in for the arrays, there is no
 * `fermentationSteps` field at all, and `dryHops` covers only the active
 * subset. Without these, a backup carries no fermentation history at all.
 *
 * Any sub-resource that cannot be read aborts the backup (see `fetchAllCursor`).
 */
async function collectBatchDetail(
  bid: string,
  apiURL: string,
  token: string
): Promise<Pick<SourceBatch, 'batchNotes' | 'gravity' | 'pressure' | 'temperature' | 'fermentationSteps'>> {
  // `GET /batches/{id}/notes` is a `CursorPage[...]` like the readings, not a bare array: reading
  // it as one made every backup throw in buildExportDocument (`.map is not a function`).
  const notes = await fetchAllCursor<Record<string, unknown>>(
    apiURL + 'batches/' + bid + '/notes',
    token,
    { includeExcluded: false }
  )
  const gravity = await fetchAllCursor<Record<string, unknown>>(apiURL + 'batches/' + bid + '/gravity', token)
  const pressure = await fetchAllCursor<Record<string, unknown>>(apiURL + 'batches/' + bid + '/pressure', token)
  const temperature = await fetchAllCursor<Record<string, unknown>>(apiURL + 'batches/' + bid + '/temp', token)
  const steps = await fetchJson<Record<string, unknown>[]>(
    apiURL + 'batches/' + bid + '/fermentation-steps',
    token
  )
  if (steps === null) {
    logError('backupCreate.collectBatchDetail()', 'Failed to fetch fermentation steps for batch', bid)
    throw new Error(`Could not read batches/${bid}/fermentation-steps`)
  }
  return { batchNotes: notes, gravity, pressure, temperature, fermentationSteps: steps }
}

function chipFor(deviceId: unknown, chipIdByDeviceId: Map<string, string>): string | null {
  return typeof deviceId === 'string' ? (chipIdByDeviceId.get(deviceId) ?? null) : null
}

/**
 * Build one vessel export entry: identity/config fields, plus its pour events
 * and temperature/pressure history (a vessel carries no gravity sub-resource —
 * kegs and bottles don't take a gravity reading). `deviceChipId` is resolved
 * the same way batch readings are, so restore can relink a vessel's readings
 * to the devices it just recreated.
 */
async function collectVesselDetail(
  v: Record<string, unknown>,
  chipIdByDeviceId: Map<string, string>,
  apiURL: string,
  token: string
): Promise<Record<string, unknown>> {
  const vid = v.id as string
  const pourEvents = await fetchAllCursor<Record<string, unknown>>(apiURL + 'vessels/' + vid + '/pours', token)
  const vesselTemp = await fetchAllCursor<Record<string, unknown>>(apiURL + 'vessels/' + vid + '/temp', token)
  const vesselPressure = await fetchAllCursor<Record<string, unknown>>(
    apiURL + 'vessels/' + vid + '/pressure',
    token
  )
  return {
    id: vid,
    batchId: (v.batchId as string) ?? '',
    tapId: (v.tapId as string | null) ?? null,
    vesselNumber: (v.vesselNumber as number | null) ?? null,
    vesselType: (v.vesselType as string) ?? 'keg',
    name: (v.name as string) ?? '',
    fillDate: (v.fillDate as string) ?? '',
    totalVolume: (v.totalVolume as number) ?? 0,
    volumeRemaining: (v.volumeRemaining as number) ?? 0,
    bottleVolume: (v.bottleVolume as number | null) ?? null,
    bottleCount: (v.bottleCount as number | null) ?? null,
    bottlesRemaining: (v.bottlesRemaining as number | null) ?? null,
    status: (v.status as string) ?? 'filled',
    location: (v.location as string) ?? '',
    notes: (v.notes as string) ?? '',
    pourEvents: pourEvents.map((pe) => ({
      id: pe.id as string,
      vesselId: vid,
      pourAmount: pe.pourAmount as number,
      volumeRemaining: pe.volumeRemaining as number,
      isManual: (pe.isManual as boolean) ?? false,
      excluded: (pe.excluded as boolean) ?? false,
      createdAt: pe.createdAt as string
    })),
    temperatureReadings: vesselTemp.map((r) => ({
      deviceChipId: chipFor(r.deviceId, chipIdByDeviceId),
      temperature: (r.temperature as number | null) ?? null,
      tempType: (r.tempType as string | null) ?? null,
      battery: (r.battery as number | null) ?? null,
      rssi: (r.rssi as number | null) ?? null,
      excluded: (r.excluded as boolean) ?? false,
      isAggregate: (r.isAggregate as boolean) ?? false,
      createdAt: (r.createdAt as string | null) ?? null
    })),
    pressureReadings: vesselPressure.map((r) => ({
      deviceChipId: chipFor(r.deviceId, chipIdByDeviceId),
      pressure: (r.pressure as number | null) ?? null,
      temperature: (r.temperature as number | null) ?? null,
      battery: (r.battery as number | null) ?? null,
      rssi: (r.rssi as number | null) ?? null,
      runTime: (r.runTime as number | null) ?? null,
      excluded: (r.excluded as boolean) ?? false,
      isAggregate: (r.isAggregate as boolean) ?? false,
      createdAt: (r.createdAt as string | null) ?? null
    }))
  }
}

/**
 * Create a full backup as a `brewgraph-batch-export-v1` document in `backup` mode.
 *
 * **A backup is a snapshot of the database**, so it carries identity, links and
 * configuration as well as measurements — that is what lets a restore rebuild
 * the dependencies between devices, batches and vessels.
 *
 * This produces the same document the per-batch export produces, differing
 * only in depth — not a bespoke `meta: {version: '2.0'}` container of raw
 * REST responses, which was never a format of its own: whatever the API
 * returned that day would become the file.
 */
export async function createBrewGraphBackup(
  deps: BackupCreateDeps
): Promise<ExportDocument | null> {
  const { baseURL, token, onProgress } = deps
  const apiURL = baseURL + 'api/'
  const getBatch =
    deps.getBatch ?? ((id: string | number) => fetchJson<Record<string, unknown>>(apiURL + 'batches/' + id, token))

  const collectedBatches: SourceBatch[] = []
  const collectedTaps: unknown[] = []
  const collectedVessels: unknown[] = []
  let collectedDevices: SourceDevice[] = []

  // The server owns this opaque UUID. It is stable per installation and lets a
  // destination recognise repeated imports without exposing host identity.
  const tenantSettings = await fetchJson<Record<string, unknown>>(
    apiURL + 'tenant/settings', token
  )
  if (tenantSettings === null) return null

  // Fetch devices. `GET /api/devices` is a `Page[...]` envelope, not a plain
  // array -- unwrapping it here is what lets buildExportDocument's own
  // `.filter()`/`.map()` over `devices` not throw against the real API.
  const deviceList = await fetchAllPages<Record<string, unknown>>(apiURL + 'devices', token)
  if (deviceList === null) {
    logError('backupCreate.createBrewGraphBackup()', 'Failed to fetch devices')
    return null
  }
  logDebug('backupCreate.createBrewGraphBackup()', 'Collected devices', deviceList.length)
  collectedDevices = deviceList as unknown as SourceDevice[]
  const chipIdByDeviceId = new Map<string, string>()
  for (const d of deviceList) {
    if (d.id && d.chipId) chipIdByDeviceId.set(d.id as string, d.chipId as string)
  }

  // Fetch every batch across every page, then full batch data sequentially.
  const batchList = await fetchAllPages<Record<string, unknown>>(apiURL + 'batches', token)
  if (batchList === null) {
    logError('backupCreate.createBrewGraphBackup()', 'Failed to fetch batches')
    return null
  }
  logDebug('backupCreate.createBrewGraphBackup()', 'Collected batch list', batchList.length)

  // The full batch is passed through as-is — not squeezed through
  // Batch.fromJson().toJson() first, which would silently drop any field the
  // editor class does not model, a lossy step in the one place that must not
  // lose anything. buildExportDocument owns the mapping, and its tests say
  // which fields survive.
  // Notes are a separate resource — `GET /batches/{id}/notes`, not a field on the
  // batch — so they must be fetched explicitly here, or the builder has nothing
  // to emit.
  for (const b of batchList) {
    const full = await getBatch(b.id as string)
    if (!full) {
      logError('backupCreate.createBrewGraphBackup()', 'Failed to fetch batch', b.id)
      throw new Error(`Could not read batch ${b.id}`)
    }
    const detail = await collectBatchDetail(b.id as string, apiURL, token)
    collectedBatches.push({ ...full, ...detail } as SourceBatch)
    onProgress()
  }

  // Fetch every page: a single-page fetch silently truncates an installation
  // with more than 200 taps.
  const tapList = await fetchAllPages<Record<string, unknown>>(apiURL + 'taps', token)
  if (tapList === null) throw new Error('Could not read taps')
  collectedTaps.push(...tapList.map((t) => ({
    id: t.id as string,
    name: t.name as string,
    tapNumber: (t.tapNumber as number | null) ?? null,
    location: (t.location as string) ?? '',
    notes: (t.notes as string) ?? ''
  })))
  logInfo('backupCreate.createBrewGraphBackup()', 'Collected taps', collectedTaps.length)

  // Fetch vessels with their pour events and temperature/pressure history.
  // `GET /api/vessels` is a `Page[...]` envelope, unwrapped and fully
  // paginated the same way devices/batches/taps are.
  const vesselList = await fetchAllPages<Record<string, unknown>>(apiURL + 'vessels', token)
  if (vesselList === null) throw new Error('Could not read vessels')
  for (const v of vesselList) {
    collectedVessels.push(
      await collectVesselDetail(v, chipIdByDeviceId, apiURL, token)
    )
  }
  logInfo(
    'backupCreate.createBrewGraphBackup()',
    'Collected vessels',
    collectedVessels.length
  )

  return buildExportDocument({
    batches: collectedBatches,
    devices: collectedDevices,
    taps: collectedTaps,
    vessels: collectedVessels,
    sourceInstanceId: tenantSettings.backupSourceId as string | undefined,
    mode: 'backup'
  })
}
