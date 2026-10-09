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

/**
 * Builds `brewgraph-batch-export-v1` documents client-side.
 *
 * There is no server-side export endpoint. Documents are assembled here from
 * the ordinary REST responses — the same mechanism `backupCreate.ts` uses — so
 * anything the API can return, an export can carry.
 *
 * **The container is always a list.** A single-batch export is a list of one, so
 * no reader ever branches on "one batch or many". Depth varies by mode instead:
 * `ml` and `archive` record what was measured, `backup` records what is stored.
 */

export const EXPORT_SCHEMA_VERSION = '1'

export interface ExportReading {
  deviceChipId: string | null
  temperature: number | null
  battery: number | null
  rssi: number | null
  runTime: number | null
  excluded: boolean
  isAggregate: boolean
  createdAt: string | null
}

export interface ExportGravityReading extends ExportReading {
  gravity: number | null
  angle: number | null
  velocity: number | null
}

export interface ExportPressureReading extends ExportReading {
  pressure: number | null
}

/**
 * A temperature reading, on the export's own base -- **not** `ExportReading`.
 * TempReading carries no `runTime`/`angle`/`velocity` (no sensor measures
 * them), but does carry `tempType` (beer vs chamber probe), which gravity and
 * pressure readings have no equivalent of.
 */
export interface ExportTemperatureReading {
  deviceChipId: string | null
  temperature: number | null
  tempType: string | null
  battery: number | null
  rssi: number | null
  excluded: boolean
  isAggregate: boolean
  createdAt: string | null
}

/**
 * One `BatchNote` row, carrying exactly the fields a restore can write back.
 *
 * `BatchNoteCreate` accepts `content`, `createdAt`, `noteType` and `testResult` —
 * so those are what is exported. `id`, `batchId` and `updatedAt` are omitted
 * deliberately: a restore recreates the batch under a new id, so the old
 * relationship is meaningless and the note's own id would collide. `createdBy`
 * is dropped for the same reason it is not settable — the creating identity does
 * not survive the move.
 *
 * `testResult` matters more than it looks: it holds a diacetyl-test outcome, so
 * dropping it would lose a decision the brewer made, not just an annotation.
 */
export interface ExportBatchNote {
  content: string
  createdAt: string | null
  noteType: string | null
  testResult: string | null
}

export interface ExportBatchEntry {
  /** `archive` and `backup`. Absent from `ml`, which records only what was measured. */
  batchNotes?: ExportBatchNote[]

  /** `backup` mode only. Absent from `ml` and `archive`, which carry no identity. */
  id?: string | null
  description?: string | null
  acceptIngest?: boolean
  brewer?: string | null
  ebc?: number | null
  ibu?: number | null
  carbonationVolumes?: number | null
  brewfatherBatchId?: string | null
  fermentationChamber?: string | null
  packageDate?: string | null
  conditioningDays?: number | null
  status?: string | null

  name: string | null
  brewDate: string | null
  style: string | null
  og: number | null
  fg: number | null
  abv: number | null
  volume: number | null
  yeast: string | null
  yeastProductId: string | null
  notes: string | null
  recipeCost: number | null
  costCurrency: string | null
  fermentation: unknown | null
  gravityReadings: ExportGravityReading[]
  pressureReadings: ExportPressureReading[]
  temperatureReadings: ExportTemperatureReading[]
  fermentationSteps: unknown[]
  dryHops: unknown[]
}

export interface ExportDevice {
  chipId: string | null
  name: string | null
  role: string
  board: string | null
  gyroModel: string | null
  deviceFiltered: boolean

  /** `backup` mode only — identity, links and configuration a restore needs. */
  id?: string | null
  deviceType?: string | null
  mdns?: string | null
  url?: string | null
  config?: string | null
  token?: string | null
  deviceColor?: string | null
  collectLogs?: boolean
  description?: string | null
  batchId?: string | null
  vesselId?: string | null
  batchRole?: string | null
  gravityFormula?: string | null
  gravityFormulaUnit?: 'sg' | 'plato' | null
  gravityCalibrationData?: { angle: number; gravity: number }[]
}

export interface ExportDocument {
  schemaVersion: string
  exportedAt: string
  source: string
  sourceInstanceId?: string
  /** Which depth this document was produced at — restore requires `backup`. */
  mode: string
  settings: Record<string, unknown>
  devices: ExportDevice[]
  taps: unknown[]
  vessels: unknown[]
  batches: ExportBatchEntry[]
}

/**
 * Input shapes, as the REST endpoints return them.
 *
 * Every field is optional: these describe what this module *reads*, not what the
 * API guarantees. Declaring them is what lets the mapping be type-checked
 * without either a `Record<string, any>` escape hatch or a second full copy of
 * the API's own types.
 */
export interface SourceGravityReading {
  deviceId?: string
  gravity?: number | null
  temperature?: number | null
  angle?: number | null
  velocity?: number | null
  battery?: number | null
  rssi?: number | null
  runTime?: number | null
  excluded?: boolean
  isAggregate?: boolean
  createdAt?: string | null
}

export interface SourcePressureReading extends Omit<SourceGravityReading, 'gravity' | 'angle'> {
  pressure?: number | null
}

/**
 * As returned by `GET /batches/{id}/temp` (and the vessel equivalent) --
 * carries `tempType`, no `runTime`/`angle`/`velocity`.
 */
export interface SourceTemperatureReading {
  deviceId?: string
  temperature?: number | null
  tempType?: string | null
  battery?: number | null
  rssi?: number | null
  excluded?: boolean
  isAggregate?: boolean
  createdAt?: string | null
}

export interface SourceFermentationStep {
  name?: string | null
  type?: string | null
  temp?: number | null
  days?: number | null
  order?: number | null
}

export interface SourceDryHop {
  name?: string | null
  amount?: number | null
  triggerMethod?: string | null
  triggerGravity?: number | null
  triggerHoursBefore?: number | null
  triggeredAt?: string | null
  completedAt?: string | null
}

export interface SourceBatchNote {
  content?: string | null
  createdAt?: string | null
  noteType?: string | null
  testResult?: string | null
}

export interface SourceBatch {
  id?: string
  description?: string | null
  acceptIngest?: boolean
  brewer?: string | null
  ebc?: number | null
  ibu?: number | null
  carbonationVolumes?: number | null
  brewfatherBatchId?: string | null
  fermentationChamber?: string | null
  packageDate?: string | null
  conditioningDays?: number | null
  status?: string | null
  name?: string | null
  brewDate?: string | null
  style?: string | null
  og?: number | null
  fg?: number | null
  abv?: number | null
  volume?: number | null
  yeast?: string | null
  yeastProductId?: string | null
  notes?: string | null
  recipeCost?: number | null
  costCurrency?: string | null
  gravity?: SourceGravityReading[]
  pressure?: SourcePressureReading[]
  temperature?: SourceTemperatureReading[]
  /** A serialised JSON string on the batch record; an array elsewhere. Both accepted. */
  fermentationSteps?: SourceFermentationStep[] | string
  dryHops?: SourceDryHop[]
  /** Fetched separately — notes live at `GET /batches/{id}/notes`, not on the batch. */
  batchNotes?: SourceBatchNote[]
}

export interface SourceDevice {
  id?: string
  chipId?: string
  deviceType?: string | null
  mdns?: string | null
  url?: string | null
  /**
   * Declared `string | null` to match ExportDevice.config and the export-v1 schema's
   * `nullableString` contract, but the API's actual `DeviceBase.config` field is
   * `Optional[Union[Dict[str, Any], str]]` and returns a real object once a device's
   * config has been fetched — this type was wrong, not aspirational. buildDeviceEntry
   * below stringifies it; the object case here documents what actually arrives.
   */
  config?: string | Record<string, unknown> | null
  token?: string | null
  deviceColor?: string | null
  collectLogs?: boolean
  description?: string | null
  batchId?: string | null
  vesselId?: string | null
  name?: string | null
  batchRole?: string | null
  chipFamily?: string | null
  gyroModel?: string | null
  deviceFiltered?: boolean
  gravityFormula?: string | null
  gravityFormulaUnit?: 'sg' | 'plato' | null
  gravityCalibrationData?: { angle: number; gravity: number }[]
}

function gravityReading(r: SourceGravityReading, chipIdByDeviceId: Map<string, string>): ExportGravityReading {
  return {
    deviceChipId: (r.deviceId ? chipIdByDeviceId.get(r.deviceId) : null) ?? null,
    gravity: r.gravity ?? null,
    temperature: r.temperature ?? null,
    angle: r.angle ?? null,
    velocity: r.velocity ?? null,
    battery: r.battery ?? null,
    rssi: r.rssi ?? null,
    runTime: r.runTime ?? null,
    excluded: r.excluded ?? false,
    isAggregate: r.isAggregate ?? false,
    createdAt: r.createdAt ?? null
  }
}

function pressureReading(
  r: SourcePressureReading,
  chipIdByDeviceId: Map<string, string>
): ExportPressureReading {
  return {
    deviceChipId: (r.deviceId ? chipIdByDeviceId.get(r.deviceId) : null) ?? null,
    pressure: r.pressure ?? null,
    temperature: r.temperature ?? null,
    battery: r.battery ?? null,
    rssi: r.rssi ?? null,
    runTime: r.runTime ?? null,
    excluded: r.excluded ?? false,
    isAggregate: r.isAggregate ?? false,
    createdAt: r.createdAt ?? null
  }
}

function temperatureReading(
  r: SourceTemperatureReading,
  chipIdByDeviceId: Map<string, string>
): ExportTemperatureReading {
  return {
    deviceChipId: (r.deviceId ? chipIdByDeviceId.get(r.deviceId) : null) ?? null,
    temperature: r.temperature ?? null,
    tempType: r.tempType ?? null,
    battery: r.battery ?? null,
    rssi: r.rssi ?? null,
    excluded: r.excluded ?? false,
    isAggregate: r.isAggregate ?? false,
    createdAt: r.createdAt ?? null
  }
}

/**
 * Normalise the fermentation schedule to the export's array shape.
 *
 * The batch record carries it as a **serialised JSON string**, while the export
 * format uses an array of step objects. Accepting either is what lets one
 * builder serve both — and the string form is easy to miss, because `[].map` on
 * it throws only once a batch actually has a schedule.
 */
function normaliseFermentationSteps(raw: SourceBatch['fermentationSteps']): unknown[] {
  let steps: SourceFermentationStep[] = []
  if (Array.isArray(raw)) {
    steps = raw
  } else if (typeof raw === 'string' && raw.trim() !== '') {
    try {
      const parsed: unknown = JSON.parse(raw)
      if (Array.isArray(parsed)) steps = parsed as SourceFermentationStep[]
    } catch {
      // A malformed schedule must not fail the whole export: the readings are
      // the irreplaceable part, and a backup that refuses to be written is
      // worse than one missing a step list.
      steps = []
    }
  }
  return steps.map((s) => ({
    name: s.name ?? null,
    type: s.type ?? null,
    temp: s.temp ?? null,
    days: s.days ?? null,
    order: s.order ?? null
  }))
}

/**
 * Build one `batches[]` entry.
 *
 * Readings are carried in full **including excluded ones, flagged**: the export
 * is lossless against the reading tables, and excluding a reading annotates it
 * rather than authorising its deletion. A consumer that archives through this
 * format and then deletes needs the dropped field to be destroyed, not merely
 * absent.
 *
 * `batchNotes` follows the same rule and for a sharper reason: emitting none
 * at any depth would silently lose every note on restore. Notes are the one
 * part of a batch the system cannot reconstruct from measurements.
 *
 * No ground-truth (`truth`) field is produced. A completion label is a human
 * judgement the system does not hold, and deriving one from a prediction would
 * train a model on its own output.
 */
export function buildBatchEntry(
  batch: SourceBatch,
  chipIdByDeviceId: Map<string, string> = new Map(),
  mode: ExportMode = 'ml'
): ExportBatchEntry {
  // Notes are user-authored prose, so they are the first thing `ml` must not
  // carry and the first thing `archive` exists for. Keyed off "not ml" rather
  // than "is backup": archive and backup agree here and only differ on identity.
  const notes =
    mode === 'ml'
      ? {}
      : {
          batchNotes: (batch.batchNotes ?? []).map((n) => ({
            content: n.content ?? '',
            createdAt: n.createdAt ?? null,
            noteType: n.noteType ?? null,
            testResult: n.testResult ?? null
          }))
        }

  const identity =
    mode === 'backup'
      ? {
          id: batch.id ?? null,
          description: batch.description ?? null,
          acceptIngest: batch.acceptIngest ?? true,
          brewer: batch.brewer ?? null,
          ebc: batch.ebc ?? null,
          ibu: batch.ibu ?? null,
          carbonationVolumes: batch.carbonationVolumes ?? null,
          brewfatherBatchId: batch.brewfatherBatchId ?? null,
          fermentationChamber: batch.fermentationChamber ?? null,
          packageDate: batch.packageDate ?? null,
          conditioningDays: batch.conditioningDays ?? null,
          status: batch.status ?? null
        }
      : {}

  return {
    ...notes,
    ...identity,
    name: batch.name ?? null,
    brewDate: batch.brewDate ?? null,
    style: batch.style ?? null,
    og: batch.og ?? null,
    fg: batch.fg ?? null,
    abv: batch.abv ?? null,
    volume: batch.volume ?? null,
    yeast: batch.yeast ?? null,
    yeastProductId: batch.yeastProductId ?? null,
    notes: batch.notes ?? null,
    recipeCost: batch.recipeCost ?? null,
    costCurrency: batch.costCurrency ?? null,
    // OSS records no fermentation-prediction block. The key stays present and
    // null so readers do not have to branch on the producing product.
    fermentation: null,
    gravityReadings: (batch.gravity ?? []).map((r) =>
      gravityReading(r, chipIdByDeviceId)
    ),
    pressureReadings: (batch.pressure ?? []).map((r) =>
      pressureReading(r, chipIdByDeviceId)
    ),
    temperatureReadings: (batch.temperature ?? []).map((r) =>
      temperatureReading(r, chipIdByDeviceId)
    ),
    fermentationSteps: normaliseFermentationSteps(batch.fermentationSteps),
    dryHops: (batch.dryHops ?? []).map((h) => ({
      name: h.name ?? null,
      amount: h.amount ?? null,
      triggerMethod: h.triggerMethod ?? null,
      triggerGravity: h.triggerGravity ?? null,
      triggerHoursBefore: h.triggerHoursBefore ?? null,
      triggeredAt: h.triggeredAt ?? null,
      completedAt: h.completedAt ?? null
    }))
  }
}

/**
 * Map a device to the export's lookup-table shape.
 *
 * In `backup` mode the entry also carries identity, links and configuration —
 * without them a restore recreates devices that are unconfigured and attached to
 * nothing. `token` is present here and **only** here: it identifies a device to
 * a batch or tap and carries no privilege, but a training export has no use for
 * it and a backup file travels differently from a settings screen.
 */
export function buildDeviceEntry(device: SourceDevice, mode: ExportMode = 'ml'): ExportDevice {
  const base: ExportDevice = {
    chipId: device.chipId ?? null,
    name: device.name ?? null,
    role: device.batchRole ?? 'gravity',
    board: device.chipFamily ?? null,
    gyroModel: device.gyroModel ?? null,
    deviceFiltered: device.deviceFiltered ?? false
  }
  if (mode !== 'backup') return base

  return {
    ...base,
    id: device.id ?? null,
    deviceType: device.deviceType ?? null,
    mdns: device.mdns ?? null,
    url: device.url ?? null,
    // export-v1.schema.json declares `config` a nullableString, but the API returns an
    // object once a device's config has actually been fetched (DeviceBase.config:
    // Optional[Union[Dict[str, Any], str]]) -- stringify so every backup-mode export
    // actually satisfies the schema it's validated against, instead of embedding a raw
    // object that fails validation on essentially every device with a config.
    config: device.config != null && typeof device.config === 'object'
      ? JSON.stringify(device.config)
      : device.config ?? null,
    token: device.token ?? null,
    deviceColor: device.deviceColor ?? null,
    collectLogs: device.collectLogs ?? false,
    description: device.description ?? null,
    batchId: device.batchId ?? null,
    vesselId: device.vesselId ?? null,
    batchRole: device.batchRole ?? null,
    gravityFormula: device.gravityFormula ?? null,
    gravityFormulaUnit: device.gravityFormulaUnit ?? null,
    gravityCalibrationData: device.gravityCalibrationData ?? []
  }
}

/**
 * How much of the database the document carries. Depth is the only variable —
 * the format and container never change.
 *
 * - `ml` — what was *measured*. No PII, no identity, no tokens.
 * - `archive` — `ml` plus batch notes.
 * - `backup` — what is *stored*: ids, relationships and configuration, so a
 *   restore can rebuild the dependencies. A backup is a snapshot of the
 *   database, and a document without ids cannot relink devices to their batches
 *   and vessels.
 */
export type ExportMode = 'ml' | 'archive' | 'backup'

export interface BuildExportDocumentInput {
  batches?: SourceBatch[]
  devices?: SourceDevice[]
  taps?: unknown[]
  vessels?: unknown[]
  settings?: Record<string, unknown>
  sourceInstanceId?: string
  mode?: ExportMode
}

/**
 * Assemble a full export document.
 *
 * Sibling blocks are always present, empty when they have no content: an absent
 * key and an empty list read differently, so "omit when irrelevant" would be a
 * branch in disguise.
 *
 * `devices` is a top-level lookup table that readings resolve `deviceChipId`
 * against, and holds only the devices this export's readings actually reference
 * — an export is self-contained, not a copy of the device inventory.
 */
export function buildExportDocument({
  batches = [],
  devices = [],
  taps = [],
  vessels = [],
  settings = {},
  sourceInstanceId,
  mode = 'ml'
}: BuildExportDocumentInput = {}): ExportDocument {
  const chipIdByDeviceId = new Map<string, string>(
    devices
      .filter((d): d is SourceDevice & { id: string; chipId: string } => !!d.id && !!d.chipId)
      .map((d) => [d.id, d.chipId] as [string, string])
  )

  const entries = batches.map((b) => buildBatchEntry(b, chipIdByDeviceId, mode))

  const referenced = new Set<string>()
  for (const entry of entries) {
    for (const r of entry.gravityReadings) if (r.deviceChipId) referenced.add(r.deviceChipId)
    for (const r of entry.pressureReadings) if (r.deviceChipId) referenced.add(r.deviceChipId)
    for (const r of entry.temperatureReadings) if (r.deviceChipId) referenced.add(r.deviceChipId)
  }

  return {
    schemaVersion: EXPORT_SCHEMA_VERSION,
    exportedAt: new Date().toISOString(),
    source: 'oss',
    ...(mode === 'backup' && sourceInstanceId ? { sourceInstanceId } : {}),
    mode,
    settings,
    devices: (mode === 'backup'
      ? devices
      : devices.filter((d) => !!d.chipId && referenced.has(d.chipId))
    ).map((d) => buildDeviceEntry(d, mode)),
    taps,
    vessels,
    batches: entries
  }
}
