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

import { describe, it, expect, vi } from 'vitest'
import {
  mapBrewLoggerDevice,
  mapDeviceType,
  mapBrewLoggerGravity,
  mapBrewLoggerPressure,
  mapBrewLoggerBatch,
  mapBrewLoggerBatchToVessel,
  mapBrewLoggerToBrewGraph
} from '../brewloggerRestore'

vi.mock('@/ui', () => ({
  logInfo: vi.fn(),
  logDebug: vi.fn(),
  logError: vi.fn()
}))

const makeDevice = (overrides = {}) => ({
  id: 1,
  chipId: 'abc123',
  chipFamily: 'esp8266',
  software: 'Gravitymon',
  mdns: 'grav-test',
  config: '{}',
  url: 'http://grav-test.local',
  description: 'My iSpindel',
  bleColor: 'blue',
  collectLogs: true,
  fermentationStep: [],
  ...overrides
})

const makeGravity = (overrides = {}) => ({
  id: 10,
  batchId: 5,
  temperature: 20.5,
  gravity: 1.045,
  velocity: 0.05,
  angle: 45.2,
  battery: 4.1,
  rssi: -75,
  corrGravity: 1.046,
  runTime: 900,
  created: '2026-01-01T12:00:00',
  active: true,
  ...overrides
})

const makePressure = (overrides = {}) => ({
  id: 20,
  batchId: 5,
  temperature: 18.0,
  pressure: 1200,
  pressure1: 0,
  battery: 4.2,
  rssi: -80,
  runTime: 901,
  created: '2026-01-02T08:00:00',
  active: true,
  ...overrides
})

const makeBatch = (overrides = {}) => ({
  id: 5,
  name: 'Test NEIPA',
  description: 'A tasty NEIPA',
  chipIdGravity: 'abc123',
  chipIdPressure: 'def456',
  active: true,
  tapList: true,
  brewDate: '2026-01-01',
  style: 'NEIPA',
  brewer: 'Magnus',
  abv: 6.5,
  ebc: 5.0,
  ibu: 12.0,
  fg: 1.005,
  og: 1.056,
  brewfatherId: 'bf123',
  fermentationChamber: 0,
  fermentationSteps: '[]',
  gravity: [],
  pressure: [],
  pour: [],
  ...overrides
})

describe('mapDeviceType', () => {
  /*
   * BrewLogger writes the device kind as capitalised, hyphenated free text;
   * the API validates against a lowercase/underscore registry. Passing it
   * through unchanged would fail every device with a 422, silently, since
   * the restore continues past individual failures.
   */
  it.each([
    ['Gravitymon', 'gravitymon'],
    ['Pressuremon', 'pressuremon'],
    ['Chamber-Controller', 'chamber_controller'],
    ['Gravitymon-Gateway', 'gravitymon_gateway'],
    ['Kegmon', 'kegmon'],
    ['iSpindel', 'ispindel']
  ])('maps BrewLogger %s to %s', (software, expected) => {
    expect(mapDeviceType(software)).toBe(expected)
  })

  // null, not '': the API rejects '' as an unregistered type but accepts no type,
  // so the device survives the import and its type can be set afterwards.
  it('returns null for an unknown kind rather than inventing one', () => {
    expect(mapDeviceType('SomeFutureDevice')).toBeNull()
  })

  it('handles the empty/missing software field seen in real exports', () => {
    expect(mapDeviceType('')).toBeNull()
    expect(mapDeviceType(null)).toBeNull()
    expect(mapDeviceType(undefined)).toBeNull()
  })

  it('keeps a device with no software as an untyped device', () => {
    // A real export's device a94af9: every field empty except chipId.
    const result = mapBrewLoggerToBrewGraph({
      meta: { version: '0.8', software: 'BrewLogger', created: '2026-01-01' },
      devices: [
        { id: 21, chipId: 'a94af9', chipFamily: '', software: '', mdns: '', config: '',
          url: '', description: '', bleColor: '', collectLogs: false, fermentationStep: [] }
      ],
      batches: []
    })
    expect(result.devices[0].chipId).toBe('a94af9')
    expect(result.devices[0].deviceType).toBeNull()
  })
})

describe('mapBrewLoggerDevice', () => {
  it('falls back to white when bleColor is an empty string', () => {
    // Every device in the reference export has bleColor: '' — `??` let that through
    // and '' is not a valid DeviceColor, so the POST 422'd.
    expect(mapBrewLoggerDevice(makeDevice({ bleColor: '' })).deviceColor).toBe('white')
  })


  it('maps all fields correctly', () => {
    const result = mapBrewLoggerDevice(makeDevice())
    expect(result.id).toBe('1')
    expect(result.name).toBe('grav-test')
    expect(result.chipId).toBe('abc123')
    expect(result.chipFamily).toBe('esp8266')
    // Normalised to the DeviceType enum value — the API rejects 'Gravitymon'.
    expect(result.deviceType).toBe('gravitymon')
    expect(result.description).toBe('My iSpindel')
    expect(result.collectLogs).toBe(true)
    expect(result.token).toBe('')
    expect(result.fermentationStep).toEqual([])
  })

  it('uses mdns as name', () => {
    const result = mapBrewLoggerDevice(makeDevice({ mdns: 'my-device' }))
    expect(result.name).toBe('my-device')
  })

  it('handles missing optional fields gracefully', () => {
    const result = mapBrewLoggerDevice({ id: 99 })
    expect(result.id).toBe('99')
    expect(result.name).toBe('')
    expect(result.chipId).toBe('')
    expect(result.description).toBe('')
    expect(result.collectLogs).toBe(false)
    expect(result.fermentationStep).toEqual([])
  })
})

describe('mapBrewLoggerGravity', () => {
  it('maps all fields correctly', () => {
    const result = mapBrewLoggerGravity(makeGravity(), 'batch-uuid')
    expect(result.batchId).toBe('batch-uuid')
    expect(result.temperature).toBe(20.5)
    expect(result.gravity).toBe(1.045)
    expect(result.velocity).toBe(0.05)
    expect(result.angle).toBe(45.2)
    expect(result.battery).toBe(4.1)
    expect(result.rssi).toBe(-75)
    expect(result.runTime).toBe(900)
    expect(result.createdAt).toBe('2026-01-01T12:00:00')
    expect(result.excluded).toBe(false)
    expect(result.deviceId).toBeNull()
  })

  it('inverts active flag to excluded', () => {
    const active = mapBrewLoggerGravity(makeGravity({ active: true }), 'b1')
    expect(active.excluded).toBe(false)

    const inactive = mapBrewLoggerGravity(makeGravity({ active: false }), 'b1')
    expect(inactive.excluded).toBe(true)
  })

  it('handles null optional fields', () => {
    const g = { id: 11, gravity: 1.045, active: true, created: '2026-01-01T00:00:00' }
    const result = mapBrewLoggerGravity(g, 'b1')
    expect(result.temperature).toBeNull()
    expect(result.velocity).toBeNull()
    expect(result.angle).toBeNull()
    expect(result.battery).toBeNull()
    expect(result.rssi).toBeNull()
    expect(result.runTime).toBeNull()
  })
})

describe('mapBrewLoggerPressure', () => {
  it('maps all fields correctly', () => {
    const result = mapBrewLoggerPressure(makePressure(), 'batch-uuid')
    expect(result.batchId).toBe('batch-uuid')
    expect(result.pressure).toBe(1200)
    expect(result.temperature).toBe(18.0)
    expect(result.createdAt).toBe('2026-01-02T08:00:00')
    expect(result.excluded).toBe(false)
    expect(result.deviceId).toBeNull()
  })

  it('maps temperature -273 to null (no-sensor sentinel)', () => {
    const result = mapBrewLoggerPressure(makePressure({ temperature: -273 }), 'b1')
    expect(result.temperature).toBeNull()
  })

  it('drops pressure1 (not in output)', () => {
    const result = mapBrewLoggerPressure(makePressure(), 'b1')
    expect(result).not.toHaveProperty('pressure1')
  })

  it('maps null temperature (not sentinel) to null', () => {
    const result = mapBrewLoggerPressure(makePressure({ temperature: null }), 'b1')
    expect(result.temperature).toBeNull()
  })

  it('inverts active flag to excluded', () => {
    const result = mapBrewLoggerPressure(makePressure({ active: false }), 'b1')
    expect(result.excluded).toBe(true)
  })

  it('handles null optional fields', () => {
    const p = { id: 21, pressure: 1200, active: true, created: '2026-01-01T00:00:00' }
    const result = mapBrewLoggerPressure(p, 'b1')
    expect(result.battery).toBeNull()
    expect(result.rssi).toBeNull()
    expect(result.runTime).toBeNull()
  })
})

describe('mapBrewLoggerBatch', () => {
  it('maps scalar fields correctly', () => {
    const result = mapBrewLoggerBatch(makeBatch())
    expect(result.id).toBe('5')
    expect(result.name).toBe('Test NEIPA')
    expect(result.description).toBe('A tasty NEIPA')
    expect(result.acceptIngest).toBe(true)
    expect(result.brewDate).toBe('2026-01-01')
    expect(result.style).toBe('NEIPA')
    expect(result.brewer).toBe('Magnus')
    expect(result.abv).toBe(6.5)
    expect(result.fg).toBe(1.005)
    expect(result.og).toBe(1.056)
    expect(result.brewfatherBatchId).toBe('bf123')
    expect(result.fermentationSteps).toBe('[]')
    expect(result.fermentationChamber).toBeNull()
    expect(result.carbonationVolumes).toBeNull()
    expect(result.notes).toBe('')
  })

  it('maps active=true to acceptIngest=true', () => {
    const result = mapBrewLoggerBatch(makeBatch({ active: true }))
    expect(result.acceptIngest).toBe(true)
  })

  it('maps active=false to acceptIngest=false', () => {
    const result = mapBrewLoggerBatch(makeBatch({ active: false }))
    expect(result.acceptIngest).toBe(false)
  })

  it('maps gravity readings through mapBrewLoggerGravity', () => {
    const gravity = [makeGravity()]
    const result = mapBrewLoggerBatch(makeBatch({ gravity }))
    expect(result.gravity).toHaveLength(1)
    expect(result.gravity[0].createdAt).toBe('2026-01-01T12:00:00')
    expect(result.gravity[0].excluded).toBe(false)
    expect(result.gravity[0]).not.toHaveProperty('corrGravity')
  })

  it('maps pressure readings through mapBrewLoggerPressure', () => {
    const pressure = [makePressure()]
    const result = mapBrewLoggerBatch(makeBatch({ pressure }))
    expect(result.pressure).toHaveLength(1)
    expect(result.pressure[0].createdAt).toBe('2026-01-02T08:00:00')
    expect(result.pressure[0]).not.toHaveProperty('pressure1')
  })

  it('drops pour data (no equivalent in output)', () => {
    const pour = [
      {
        id: 1,
        pour: 0,
        volume: 3.5,
        maxVolume: 19,
        created: '2026-01-01',
        active: true,
        batchId: 5
      }
    ]
    const result = mapBrewLoggerBatch(makeBatch({ pour }))
    expect(result).not.toHaveProperty('pour')
  })

  it('handles missing optional fields with defaults', () => {
    const result = mapBrewLoggerBatch({ id: 42, active: false })
    expect(result.name).toBe('')
    expect(result.description).toBe('')
    expect(result.brewDate).toBeNull()
    expect(result.style).toBe('')
    expect(result.brewer).toBe('')
    expect(result.abv).toBe(0)
    expect(result.ebc).toBe(0)
    expect(result.ibu).toBe(0)
    expect(result.fg).toBe(0)
    expect(result.og).toBe(0)
    expect(result.brewfatherBatchId).toBe('')
    expect(result.fermentationSteps).toBe('')
    expect(result.acceptIngest).toBe(false)
    expect(result.gravity).toEqual([])
    expect(result.pressure).toEqual([])
  })

  it('maps an empty brewDate to null (the API rejects "")', () => {
    expect(mapBrewLoggerBatch(makeBatch({ brewDate: '' })).brewDate).toBeNull()
  })

  it('derives a status the API accepts', () => {
    const pour = [{ id: 1, pour: 0, volume: 3, maxVolume: 19, created: '2026-01-01', active: true }]
    expect(mapBrewLoggerBatch(makeBatch({ active: true })).status).toBe('fermenting')
    expect(mapBrewLoggerBatch(makeBatch({ active: false, pour })).status).toBe('packaged')
    expect(mapBrewLoggerBatch(makeBatch({ active: false, pour: [] })).status).toBe('archived')
  })
})

describe('mapBrewLoggerToBrewGraph', () => {
  it('carries a non-null status into every batch entry', () => {
    const result = mapBrewLoggerToBrewGraph({
      meta: { version: '0.8', software: 'BrewLogger', created: '2026-01-01' },
      devices: [],
      batches: [makeBatch({ active: false })]
    })
    expect(result.batches[0].status).toBe('archived')
  })

  const makeFullBackup = (overrides = {}) => ({
    meta: { version: '0.8', software: 'BrewLogger', created: '2026-01-01' },
    devices: [makeDevice()],
    batches: [makeBatch()],
    pressure: [],
    pour: [],
    ...overrides
  })

  it('produces a v1 backup document, not a bespoke container', () => {
    // BrewLogger is an import source, not a format we support: its files are
    // converted on the way in and land in the same shape a native backup
    // produces, so import and restore share one destination.
    const result = mapBrewLoggerToBrewGraph(makeFullBackup())
    expect(result.schemaVersion).toBe('1')
    expect(result.source).toBe('oss')
    expect(result.mode).toBe('backup')
    expect(result.meta).toBeUndefined()
  })

  it('maps all devices', () => {
    const result = mapBrewLoggerToBrewGraph(makeFullBackup())
    expect(result.devices).toHaveLength(1)
    expect(result.devices[0].chipId).toBe('abc123')
    expect(result.devices[0].deviceColor).toBe('blue')
  })

  it('maps all batches', () => {
    const result = mapBrewLoggerToBrewGraph(makeFullBackup())
    expect(result.batches).toHaveLength(1)
    expect(result.batches[0].name).toBe('Test NEIPA')
  })

  it('produces empty taps and vessels', () => {
    const result = mapBrewLoggerToBrewGraph(makeFullBackup())
    expect(result.taps).toEqual([])
    expect(result.vessels).toEqual([])
  })

  it('links a packaged batch pressure device to its auto-created vessel', () => {
    const result = mapBrewLoggerToBrewGraph(makeFullBackup({
      devices: [makeDevice({ id: 2, chipId: 'def456', software: 'Pressuremon' })],
      batches: [makeBatch({
        pour: [{
          id: 1,
          batchId: 5,
          pour: 0.5,
          volume: 18.5,
          maxVolume: 19,
          created: '2026-01-01T12:00:00',
          active: true
        }]
      })]
    }))

    expect(result.vessels).toHaveLength(1)
    expect(result.devices[0].vesselId).toBe(result.vessels[0].id)
    expect(result.devices[0].batchId).toBeNull()
    expect(result.devices[0].batchRole).toBeNull()
  })

  it('handles empty devices and batches', () => {
    const result = mapBrewLoggerToBrewGraph(makeFullBackup({ devices: [], batches: [] }))
    expect(result.devices).toEqual([])
    expect(result.batches).toEqual([])
  })

  it('logs a warning when top-level pour records are present', async () => {
    const { logInfo } = await import('@/ui')
    const pour = [
      { id: 1, batchId: 5, pour: 0, volume: 3, maxVolume: 19, created: '2026-01-01', active: true }
    ]
    mapBrewLoggerToBrewGraph(makeFullBackup({ pour }))
    expect(logInfo).toHaveBeenCalledWith(
      expect.stringContaining('brewloggerRestore'),
      expect.stringContaining('Skipping')
    )
  })

  it('resolves chipIdGravity to device batchId/batchRole via device map', () => {
    const device = makeDevice({ id: 7, chipId: 'abc123' })
    const batch = makeBatch({ chipIdGravity: 'abc123', chipIdPressure: null })
    const result = mapBrewLoggerToBrewGraph(makeFullBackup({ devices: [device], batches: [batch] }))
    expect(result.devices[0].batchId).toBe('5')
    expect(result.devices[0].batchRole).toBe('gravity')
  })

  it('leaves device batchId null when chipId not found in devices', () => {
    const device = makeDevice({ id: 7, chipId: 'other-chip' })
    const batch = makeBatch({ chipIdGravity: 'unknown-chip', chipIdPressure: null })
    const result = mapBrewLoggerToBrewGraph(makeFullBackup({ devices: [device], batches: [batch] }))
    expect(result.devices[0].batchId).toBeNull()
  })

  it('creates tap and vessel for batch with pours and tapList=true', () => {
    const pour = [
      {
        id: 1,
        pour: 0.5,
        volume: 18.5,
        maxVolume: 19,
        created: '2026-01-01T10:00:00',
        active: true
      }
    ]
    const batch = makeBatch({ tapList: true, pour })
    const result = mapBrewLoggerToBrewGraph(makeFullBackup({ batches: [batch] }))
    expect(result.taps).toHaveLength(1)
    expect(result.vessels).toHaveLength(1)
    expect(result.vessels[0].tapId).toBe(result.taps[0].id)
  })

  it('does not create tap for batch without tapList', () => {
    const pour = [
      {
        id: 1,
        pour: 0.5,
        volume: 18.5,
        maxVolume: 19,
        created: '2026-01-01T10:00:00',
        active: true
      }
    ]
    const batch = makeBatch({ tapList: false, pour })
    const result = mapBrewLoggerToBrewGraph(makeFullBackup({ batches: [batch] }))
    expect(result.taps).toHaveLength(0)
    expect(result.vessels).toHaveLength(1) // vessel from pours but no tap
  })

  it('assigns tapNumber incrementally for multiple tapped batches', () => {
    const pour1 = [
      {
        id: 1,
        pour: 0.5,
        volume: 18.5,
        maxVolume: 19,
        created: '2026-01-01T10:00:00',
        active: true
      }
    ]
    const pour2 = [
      {
        id: 2,
        pour: 0.5,
        volume: 18.5,
        maxVolume: 19,
        created: '2026-01-02T10:00:00',
        active: true
      }
    ]
    const batch1 = makeBatch({ id: 1, tapList: true, pour: pour1 })
    const batch2 = { ...makeBatch({ id: 2, tapList: true, pour: pour2 }), name: 'Batch 2' }
    const result = mapBrewLoggerToBrewGraph(makeFullBackup({ batches: [batch1, batch2] }))
    expect(result.taps).toHaveLength(2)
    expect(result.taps[0].tapNumber).toBe(1)
    expect(result.taps[1].tapNumber).toBe(2)
  })

  it('skips device with no chipId from chip map', () => {
    const device = makeDevice({ chipId: undefined })
    const batch = makeBatch({ chipIdGravity: null, chipIdPressure: null })
    const result = mapBrewLoggerToBrewGraph(makeFullBackup({ devices: [device], batches: [batch] }))
    expect(result.devices[0].batchId).toBeNull()
    expect(result.devices[0].batchRole).toBeNull()
  })

  it('skips tap creation when vessel not found for tapList batch (no pours)', () => {
    const batch = makeBatch({ tapList: true, pour: [] })
    const result = mapBrewLoggerToBrewGraph(makeFullBackup({ batches: [batch] }))
    expect(result.taps).toHaveLength(0)
  })
})

describe('mapBrewLoggerBatchToVessel', () => {
  const makePour = (overrides = {}) => ({
    id: 1,
    pour: 0.5,
    volume: 18.5,
    maxVolume: 19,
    created: '2026-01-02T10:00:00',
    active: true,
    ...overrides
  })

  it('returns null for batch with no pours', () => {
    const result = mapBrewLoggerBatchToVessel(makeBatch({ pour: [] }))
    expect(result).toBeNull()
  })

  it('returns null for batch with undefined pour', () => {
    const result = mapBrewLoggerBatchToVessel(makeBatch({ pour: undefined }))
    expect(result).toBeNull()
  })

  it('creates vessel from batch pours', () => {
    const pour = [makePour()]
    const result = mapBrewLoggerBatchToVessel(makeBatch({ pour }))
    expect(result).not.toBeNull()
    expect(result.batchId).toBe('5')
    expect(result.vesselType).toBe('keg')
    expect(result.totalVolume).toBe(19)
    expect(result.pourEvents).toHaveLength(1)
  })

  it('uses brewDate as fillDate when available', () => {
    const pour = [makePour()]
    const result = mapBrewLoggerBatchToVessel(makeBatch({ pour, brewDate: '2026-01-01' }))
    expect(result.fillDate).toBe('2026-01-01')
  })

  it('falls back to first pour date when brewDate is empty', () => {
    const pour = [makePour({ created: '2026-01-02T10:00:00' })]
    const result = mapBrewLoggerBatchToVessel(makeBatch({ pour, brewDate: '' }))
    expect(result.fillDate).toBe('2026-01-02')
  })

  it('sets status to serving when volumeRemaining > 0', () => {
    const pour = [makePour({ volume: 5 })]
    const result = mapBrewLoggerBatchToVessel(makeBatch({ pour }))
    expect(result.status).toBe('serving')
  })

  it('sets status to clean when volumeRemaining is 0', () => {
    const pour = [makePour({ volume: 0 })]
    const result = mapBrewLoggerBatchToVessel(makeBatch({ pour }))
    expect(result.status).toBe('clean')
  })

  it('sorts pours chronologically', () => {
    const pours = [
      makePour({ id: 2, created: '2026-01-03T10:00:00', volume: 10 }),
      makePour({ id: 1, created: '2026-01-01T10:00:00', volume: 18.5 })
    ]
    const result = mapBrewLoggerBatchToVessel(makeBatch({ pour: pours }))
    expect(result.pourEvents[0].createdAt).toBe('2026-01-01T10:00:00')
    expect(result.volumeRemaining).toBe(10) // last sorted pour
  })
})
