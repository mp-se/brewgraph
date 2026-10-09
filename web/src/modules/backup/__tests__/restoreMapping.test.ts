import { describe, expect, it } from 'vitest'
import type { ExportBatchEntry } from '../exportDocument'
import {
  mapBatchPayload,
  mapBatchReading,
  mapDeviceAssignment,
  mapDevicePayload,
  mapPourEvent,
  mapTapPayload,
  mapVesselPayload,
  mapVesselReading
} from '../restoreMapping'

function batch(overrides: Partial<ExportBatchEntry> = {}): ExportBatchEntry {
  return {
    id: 'old-batch',
    description: null,
    acceptIngest: true,
    brewer: null,
    ebc: null,
    ibu: null,
    carbonationVolumes: null,
    brewfatherBatchId: null,
    fermentationChamber: null,
    packageDate: null,
    conditioningDays: null,
    status: 'fermenting',
    name: 'Test batch',
    brewDate: null,
    style: null,
    og: null,
    fg: null,
    abv: null,
    volume: null,
    yeast: null,
    yeastProductId: null,
    notes: null,
    recipeCost: null,
    costCurrency: null,
    fermentation: null,
    gravityReadings: [],
    pressureReadings: [],
    temperatureReadings: [],
    fermentationSteps: [],
    dryHops: [],
    ...overrides
  }
}

describe('backup restore mapping', () => {
  it('strips export-only device fields and defers assignments', () => {
    const result = mapDevicePayload({
      id: 'old-device',
      chipId: 'aabbcc',
      name: 'Hydrometer',
      role: 'gravity',
      board: 'esp32',
      gyroModel: 'mpu6050',
      deviceFiltered: false,
      batchId: 'old-batch',
      batchRole: 'gravity',
      vesselId: 'old-vessel',
      gravityFormula: '1+tilt/1000',
      gravityFormulaUnit: 'sg',
      gravityCalibrationData: [{ angle: 30, gravity: 1.03 }]
    })

    expect(result.payload).toMatchObject({
      id: 'old-device',
      chipId: 'aabbcc',
      fermentationStep: [],
      collectLogs: false,
      gravityFormula: '1+tilt/1000',
      gravityFormulaUnit: 'sg',
      gravityCalibrationData: [{ angle: 30, gravity: 1.03 }]
    })
    expect(result.payload).not.toHaveProperty('role')
    expect(result.payload).not.toHaveProperty('batchId')
    expect(result.assignment).toEqual({
      batchId: 'old-batch',
      batchRole: 'gravity',
      vesselId: 'old-vessel'
    })
  })

  it('maps deferred device assignments and preserves role-only assignments', () => {
    const batchMap = new Map([['old-batch', 'new-batch']])
    const vesselMap = new Map([['old-vessel', 'new-vessel']])
    expect(
      mapDeviceAssignment(
        { batchId: 'old-batch', batchRole: 'gravity', vesselId: 'old-vessel' },
        batchMap,
        vesselMap
      )
    ).toEqual({ batchId: 'new-batch', batchRole: 'gravity', vesselId: 'new-vessel' })
    expect(
      mapDeviceAssignment({ batchId: null, batchRole: 'gravity', vesselId: null }, batchMap, vesselMap)
    ).toEqual({ batchId: null, batchRole: 'gravity', vesselId: null })
    expect(
      mapDeviceAssignment({ batchId: null, batchRole: null, vesselId: null }, batchMap, vesselMap)
    ).toBeNull()
  })

  it('creates archived batches as fermenting and retains dry hops and nullable measurements', () => {
    const { payload, archived } = mapBatchPayload(
      batch({
        name: 'Archived IPA',
        status: 'archived',
        og: null,
        fg: null,
        dryHops: [{ name: 'Citra' }],
        fermentation: { currentStep: 2 },
        fermentationChamber: 'Cold room'
      })
    )

    expect(archived).toBe(true)
    expect(payload.status).toBe('fermenting')
    expect(payload.og).toBeNull()
    expect(payload.fg).toBeNull()
    expect(payload.dryHops).toEqual([{ name: 'Citra' }])
    expect(payload).not.toHaveProperty('id')
    expect(payload).not.toHaveProperty('gravityReadings')
    expect(payload).not.toHaveProperty('fermentation')
    expect(mapBatchPayload(batch({ name: 'Active', status: 'fermenting' })).archived).toBe(false)
  })

  it('relinks reading rows through stable device chip IDs and removes export references', () => {
    const devices = new Map([['aabbcc', 'device-new']])
    expect(
      mapBatchReading(
        { deviceChipId: 'aabbcc', gravity: 1.05, createdAt: '2026-01-01' },
        'batch-new',
        devices
      )
    ).toEqual({ gravity: 1.05, createdAt: '2026-01-01', batchId: 'batch-new', deviceId: 'device-new' })
    expect(mapBatchReading({ deviceChipId: 'missing', pressure: 12 }, 'batch-new', devices)).toEqual({
      pressure: 12,
      batchId: 'batch-new',
      deviceId: null
    })
    expect(mapVesselReading({ deviceChipId: 'aabbcc', temperature: 19 }, 'vessel-new', devices)).toEqual({
      temperature: 19,
      vesselId: 'vessel-new',
      deviceId: 'device-new'
    })
  })

  it('maps taps, vessel links, and pour records to API payloads', () => {
    expect(mapTapPayload({ id: 'tap-old', name: 'Serving', tapNumber: 2, location: 'Bar', notes: 'N' })).toEqual({
      name: 'Serving',
      tapNumber: 2,
      location: 'Bar',
      notes: 'N'
    })
    expect(
      mapVesselPayload(
        {
          id: 'v-old',
          batchId: 'b-old',
          tapId: 't-old',
          vesselNumber: null,
          vesselType: 'keg',
          name: 'Keg',
          fillDate: '2026-01-01',
          totalVolume: 19,
          volumeRemaining: 18,
          bottleVolume: null,
          bottleCount: null,
          bottlesRemaining: null,
          status: 'filled',
          location: 'Cellar',
          notes: '',
          pourEvents: []
        },
        new Map([['b-old', 'b-new']]),
        new Map([['t-old', 't-new']])
      )
    ).toMatchObject({ batchId: 'b-new', tapId: 't-new', name: 'Keg' })
    expect(mapPourEvent({
      id: 'pour-old',
      vesselId: 'v-old',
      excluded: false,
      pourAmount: 1,
      volumeRemaining: 18,
      isManual: false,
      createdAt: '2026-01-01'
    })).toEqual({
      pourAmount: 1,
      volumeRemaining: 18,
      isManual: false,
      createdAt: '2026-01-01'
    })
  })
})
