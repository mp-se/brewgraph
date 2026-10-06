/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { describe, it, expect } from 'vitest'
import { buildExportDocument, buildBatchEntry } from '../exportDocument'

const READING = {
  deviceId: 'dev-1',
  gravity: 1.048,
  temperature: 18.5,
  angle: 25.3,
  velocity: 0.4,
  battery: 4.13,
  rssi: -71,
  runTime: 5,
  excluded: false,
  isAggregate: false,
  createdAt: '2026-01-02T10:00:00Z'
}

const DEVICE = {
  id: 'dev-1',
  chipId: 'a1b2c3',
  name: 'GravityMon 7',
  batchRole: 'gravity',
  chipFamily: 'esp32',
  gyroModel: 'ICM42670P',
  deviceFiltered: true
}

function batch(overrides = {}) {
  return {
    id: 'batch-1',
    name: '80. Helles',
    brewDate: '2026-01-02',
    og: 1.048,
    fg: 1.005,
    gravity: [READING],
    pressure: [],
    ...overrides
  }
}

describe('buildExportDocument', () => {
  it('includes sourceInstanceId only in backup mode', () => {
    const backup = buildExportDocument({ batches: [batch()], devices: [DEVICE], mode: 'backup', sourceInstanceId: 'source-1' })
    expect(backup.sourceInstanceId).toBe('source-1')
    const archive = buildExportDocument({ batches: [batch()], devices: [DEVICE], mode: 'archive', sourceInstanceId: 'source-1' })
    expect(archive.sourceInstanceId).toBeUndefined()
  })
  it('always produces a list container, even for one batch', () => {
    const doc = buildExportDocument({ batches: [batch()], devices: [DEVICE] })
    expect(Array.isArray(doc.batches)).toBe(true)
    expect(doc.batches).toHaveLength(1)
  })

  it('carries many batches through the same container', () => {
    const doc = buildExportDocument({
      batches: [batch({ name: 'One' }), batch({ name: 'Two' })],
      devices: [DEVICE]
    })
    expect(doc.batches.map((b) => b.name)).toEqual(['One', 'Two'])
  })

  it('stamps the schema version and names OSS as the source', () => {
    const doc = buildExportDocument({ batches: [batch()], devices: [DEVICE] })
    expect(doc.schemaVersion).toBe('1')
    expect(doc.source).toBe('oss')
  })

  it('keeps sibling blocks present when empty', () => {
    // An absent key and an empty list read differently to a consumer, so
    // "omit when irrelevant" would be a branch in disguise.
    const doc = buildExportDocument({ batches: [batch()], devices: [DEVICE] })
    expect(doc.taps).toEqual([])
    expect(doc.vessels).toEqual([])
    expect(doc.settings).toEqual({})
  })

  it('resolves readings to devices by chipId', () => {
    const doc = buildExportDocument({ batches: [batch()], devices: [DEVICE] })
    expect(doc.batches[0].gravityReadings[0].deviceChipId).toBe('a1b2c3')
    expect(doc.devices[0].chipId).toBe('a1b2c3')
    expect(doc.devices[0].board).toBe('esp32')
  })

  it('includes only devices the export actually references', () => {
    // An export is self-contained, not a copy of the device inventory.
    const unrelated = { ...DEVICE, id: 'dev-9', chipId: 'ffffff' }
    const doc = buildExportDocument({ batches: [batch()], devices: [DEVICE, unrelated] })
    expect(doc.devices.map((d) => d.chipId)).toEqual(['a1b2c3'])
  })
})

describe('backup mode — a snapshot of the database', () => {
  const DEV = {
    ...DEVICE,
    deviceType: 'gravitymon',
    mdns: 'gravmon.local',
    url: 'http://gravmon.local',
    config: '{"sleep":300}',
    token: 'tok_abc',
    deviceColor: '#ff0000',
    collectLogs: true,
    description: 'Fermenter 1',
    batchId: 'batch-1',
    vesselId: null
  }

  it('carries ids so restore can rebuild the links', () => {
    // Restore builds old->new id maps to relink devices to their batches and
    // vessels. Without ids it cannot reassemble the relationships at all.
    const doc = buildExportDocument({ batches: [batch()], devices: [DEV], mode: 'backup' })
    expect(doc.batches[0].id).toBe('batch-1')
    expect(doc.devices[0].id).toBe('dev-1')
    expect(doc.devices[0].batchId).toBe('batch-1')
  })

  it('carries device configuration', () => {
    // Restoring devices without config leaves a brewery of unconfigured hardware.
    const doc = buildExportDocument({ batches: [batch()], devices: [DEV], mode: 'backup' })
    expect(doc.devices[0]).toMatchObject({
      deviceType: 'gravitymon',
      mdns: 'gravmon.local',
      url: 'http://gravmon.local',
      config: '{"sleep":300}',
      collectLogs: true
    })
  })

  it('stringifies an object config instead of embedding it raw', () => {
    // The API's actual DeviceBase.config is Optional[Union[Dict[str, Any], str]] and
    // returns a real object once a device's config has been fetched -- this repo's own
    // SourceDevice type used to claim `string | null`, which was aspirational, not true.
    // An un-stringified object here fails export-v1.schema.json's `nullableString`
    // constraint on essentially every device that has a config. Regression for that gap
    // (tasks/backlog.md, flagged 2026-09-12, not previously root-caused).
    const devWithObjectConfig = { ...DEV, config: { sleep: 300, wifi: { ssid: 'brew' } } }
    const doc = buildExportDocument({ batches: [batch()], devices: [devWithObjectConfig], mode: 'backup' })
    expect(typeof doc.devices[0].config).toBe('string')
    expect(JSON.parse(doc.devices[0].config)).toEqual({ sleep: 300, wifi: { ssid: 'brew' } })
  })

  it('carries the extra batch fields a restore needs', () => {
    const doc = buildExportDocument({
      batches: [batch({ description: 'A batch', brewer: 'Magnus', ebc: 12.4, ibu: 33 })],
      devices: [DEV],
      mode: 'backup'
    })
    expect(doc.batches[0]).toMatchObject({
      description: 'A batch',
      brewer: 'Magnus',
      ebc: 12.4,
      ibu: 33
    })
  })

  /*
   * `packageDate`/`conditioningDays`/`status` are ordinary persisted BatchBase
   * fields and must be included to preserve the batch state on round-trip.
   */
  it('carries packageDate/conditioningDays/status for round-tripping', () => {
    const doc = buildExportDocument({
      batches: [
        batch({ packageDate: '2026-02-01', conditioningDays: 14, status: 'conditioning' })
      ],
      devices: [DEV],
      mode: 'backup'
    })
    expect(doc.batches[0]).toMatchObject({
      packageDate: '2026-02-01',
      conditioningDays: 14,
      status: 'conditioning'
    })
  })

  it('omits packageDate/conditioningDays/status outside backup mode', () => {
    const doc = buildExportDocument({
      batches: [batch({ packageDate: '2026-02-01', conditioningDays: 14, status: 'conditioning' })],
      devices: [DEV],
      mode: 'archive'
    })
    expect(doc.batches[0].packageDate).toBeUndefined()
    expect(doc.batches[0].conditioningDays).toBeUndefined()
    expect(doc.batches[0].status).toBeUndefined()
  })

  it('includes devices with no readings yet', () => {
    // ml/archive carry only referenced devices because an export is
    // self-contained. A backup must recreate every device, including ones that
    // have never reported.
    const idle = { ...DEV, id: 'dev-9', chipId: 'ffffff' }
    const doc = buildExportDocument({ batches: [batch()], devices: [DEV, idle], mode: 'backup' })
    expect(doc.devices.map((d) => d.chipId).sort()).toEqual(['a1b2c3', 'ffffff'])
  })

  it('declares its own mode so a reader knows what it holds', () => {
    const doc = buildExportDocument({ batches: [batch()], devices: [DEV], mode: 'backup' })
    expect(doc.mode).toBe('backup')
  })
})

describe('ml and archive modes withhold identity and credentials', () => {
  const DEV = { ...DEVICE, token: 'tok_abc', config: '{"sleep":300}', batchId: 'batch-1' }

  it.each(['ml', 'archive'])('%s mode carries no ingest token', (mode) => {
    // A token identifies a device to a batch and carries no privilege, but a
    // training export has no use for it.
    const doc = buildExportDocument({ batches: [batch()], devices: [DEV], mode })
    expect(doc.devices[0].token).toBeUndefined()
  })

  it.each(['ml', 'archive'])('%s mode carries no ids', (mode) => {
    const doc = buildExportDocument({ batches: [batch()], devices: [DEV], mode })
    expect(doc.batches[0].id).toBeUndefined()
    expect(doc.devices[0].id).toBeUndefined()
  })

  it('defaults to ml when no mode is given', () => {
    const doc = buildExportDocument({ batches: [batch()], devices: [DEV] })
    expect(doc.mode).toBe('ml')
    expect(doc.devices[0].token).toBeUndefined()
  })
})

describe('buildBatchEntry — losslessness', () => {
  it('carries every reading field, not just the ones charts use', () => {
    // Hosted archives through this format and then deletes, so a dropped field
    // is destroyed rather than merely absent.
    const entry = buildBatchEntry(batch(), new Map([['dev-1', 'a1b2c3']]))
    const reading = entry.gravityReadings[0]
    expect(reading).toMatchObject({
      gravity: 1.048,
      temperature: 18.5,
      angle: 25.3,
      velocity: 0.4,
      battery: 4.13,
      rssi: -71,
      runTime: 5
    })
  })

  it('exports excluded readings, flagged rather than dropped', () => {
    // Excluding a reading annotates it; it does not authorise deleting it.
    const entry = buildBatchEntry(
      batch({ gravity: [{ ...READING, excluded: true }] }),
      new Map([['dev-1', 'a1b2c3']])
    )
    expect(entry.gravityReadings).toHaveLength(1)
    expect(entry.gravityReadings[0].excluded).toBe(true)
  })

  it('never produces a ground-truth field', () => {
    // A completion label is a human judgement the system does not hold.
    // Deriving one from a prediction would train a model on its own output.
    const entry = buildBatchEntry(batch(), new Map())
    expect(entry.truth).toBeUndefined()
    expect(entry.fermentation).toBeNull()
  })

  it('tolerates a batch with no readings at all', () => {
    const entry = buildBatchEntry({ name: 'Empty' }, new Map())
    expect(entry.gravityReadings).toEqual([])
    expect(entry.pressureReadings).toEqual([])
    expect(entry.temperatureReadings).toEqual([])
  })

  /*
   * Temperature readings carry `tempType` (beer vs chamber probe) and no
   * `runTime`/`angle`/`velocity` — a distinct shape from gravity/pressure, not
   * reused `ExportReading`. A hardcoded `temperatureReadings: []` used to mean
   * a backup carried no temperature history at all regardless of what the
   * batch actually had.
   */
  it('carries temperature readings with their own shape, resolved to a device chip', () => {
    const entry = buildBatchEntry(
      batch({
        temperature: [
          {
            deviceId: 'dev-1',
            temperature: 19.2,
            tempType: 'chamber',
            battery: 3.9,
            rssi: -60,
            excluded: false,
            isAggregate: false,
            createdAt: '2026-01-02T11:00:00Z'
          }
        ]
      }),
      new Map([['dev-1', 'a1b2c3']])
    )
    expect(entry.temperatureReadings).toHaveLength(1)
    expect(entry.temperatureReadings[0]).toEqual({
      deviceChipId: 'a1b2c3',
      temperature: 19.2,
      tempType: 'chamber',
      battery: 3.9,
      rssi: -60,
      excluded: false,
      isAggregate: false,
      createdAt: '2026-01-02T11:00:00Z'
    })
  })
})
