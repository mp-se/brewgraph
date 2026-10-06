import { describe, expect, it } from 'vitest'
import {
  abv,
  assignmentCandidates,
  decimalPrecision,
  decimalStep,
  gravityToPlato,
  platoToGravity,
  pressureToBAR,
  pressureToKPA,
  detectDeviceType,
  detectPlatform,
  deviceEndpoint,
  roundValue,
  tempToC,
  tempToF,
  volumeCLtoUKOZ,
  volumeCLtoL,
  volumeCLtoUSOZ,
  volumeLtoUSGallon,
  volumeUKGallonToL,
  volumeUSGallonToL,
  dryHopsPayload,
  applyMovingAverage,
  alcoholPoints,
  formatDurationShort,
  gravityPoints,
  readingStats,
  relativeTime,
  validationErrorSummary
} from '@brewgraph/core'

describe('shared brewing calculations', () => {
  it('converts gravity between specific gravity and Plato', () => {
    expect(gravityToPlato(1)).toBeCloseTo(0, 1)
    expect(platoToGravity(12)).toBeCloseTo(1.048, 2)
  })

  it('converts temperature, pressure, and volume using canonical factors', () => {
    expect(tempToF(20)).toBe(68)
    expect(tempToC(68)).toBe(20)
    expect(pressureToKPA(1)).toBeCloseTo(6.89475729, 7)
    expect(pressureToBAR(1)).toBeCloseTo(0.0689475729, 9)
    expect(volumeLtoUSGallon(1)).toBeCloseTo(0.264172052, 9)
    expect(volumeCLtoUSOZ(10)).toBeCloseTo(3.38140225, 8)
    expect(volumeCLtoUKOZ(2.84)).toBeCloseTo(0.9973958, 7)
    expect(volumeUSGallonToL(volumeLtoUSGallon(20))).toBeCloseTo(20, 7)
    expect(volumeUKGallonToL(0.2199692483)).toBeCloseTo(1, 7)
    expect(volumeCLtoL(50)).toBe(0.5)
  })

  it('calculates ABV and safely rounds optional values', () => {
    expect(abv(1.05, 1.01)).toBeGreaterThan(0)
    expect(abv(1.05, 1.05)).toBe(0)
    expect(roundValue(1.2345, 2)).toBe(1.23)
    expect(roundValue(null)).toBe(0)
  })

  it('normalizes dry-hop trigger timing into the canonical payload', () => {
    expect(dryHopsPayload([{ name: 'Citra', amount: 25, triggerHoursBefore: 0.4 }])).toEqual([
      {
        name: 'Citra',
        amount: 25,
        triggerMethod: 'hours_before_completion',
        triggerHoursBefore: 1,
        triggerGravity: null
      }
    ])
  })

  it('smooths telemetry with a moving average', () => {
    expect(applyMovingAverage([{ x: 1, y: 10 }, { x: 2, y: 30 }, { x: 3, y: 50 }], 2)).toEqual([
      { x: 1, y: 10 }, { x: 2, y: 20 }, { x: 3, y: 40 }
    ])
  })

  it('formats text and time relative to an injected clock', () => {
    const now = new Date('2026-01-08T12:00:00Z')
    expect(relativeTime('2026-01-07T12:00:00Z', now)).toBe('1 d ago')
    expect(formatDurationShort(777600)).toBe('1w 2d ')
  })

  it('aggregates active readings without sorting the caller collection', () => {
    const readings = [
      { excluded: false, temperature: 20, gravity: 1.01, created: '2026-01-01T01:00:00Z' },
      { excluded: true, temperature: 40, gravity: 1.2, created: '2026-01-01T00:00:00Z' },
      { excluded: false, temperature: 18, gravity: 1.05, created: '2026-01-01T00:00:00Z' }
    ]
    const stats = readingStats(readings, {
      getValue: (reading) => reading.gravity,
      getCreated: (reading) => reading.created
    })
    expect(stats).toMatchObject({ readings: 2, value: { min: 1.01, max: 1.05 } })
    expect(stats.date.first).toBe('2026-01-01T00:00:00Z')
    expect(readings[0].created).toBe('2026-01-01T01:00:00Z')
  })

  it('maps gravity series with caller-provided calculation policy', () => {
    expect(gravityPoints([{ created: '2026-01-01', gravity: 1.05 }], false, (sg) => (sg - 1) * 250)).toEqual([
      { x: '2026-01-01', y: 12.5 }
    ])
    expect(alcoholPoints([{ created: '2026-01-01', gravity: 1.05 }])).toEqual([
      { x: '2026-01-01', y: 0 }
    ])
  })

  it('classifies device status without application dependencies', () => {
    expect(detectDeviceType({ gravity: 1.05 })).toBe('gravitymon')
    expect(detectDeviceType({ scale_raw1: 2, gravity: 1.05 })).toBe('kegmon')
    expect(detectPlatform({ platform: 'ESP32 Arduino' })).toBe('esp32')
  })

  it('selects assignment candidates while leaving UI labels to the caller', () => {
    const devices = [
      { id: 'gravity', deviceType: 'gravitymon', mdns: 'tilt.local' },
      { id: 'pressure', deviceType: 'pressuremon', description: 'Fermenter' },
      { id: 'chamber-offline', deviceType: 'chamber_controller', url: '' },
      { id: 'chamber', deviceType: 'chamber_controller', url: 'http://chamber.local' }
    ]
    expect(assignmentCandidates(devices, 'gravity').map((device) => device.id)).toEqual(['gravity'])
    expect(assignmentCandidates(devices, 'temperature-control').map((device) => device.id)).toEqual(['chamber'])
    expect(deviceEndpoint(devices[1])).toBe('Fermenter')
  })

  it('calculates input precision and gives concise schema errors', () => {
    expect(decimalPrecision('gravity', { gravity: 5 }, { gravity: 4 })).toBe(5)
    expect(decimalStep(4)).toBe(0.0001)
    expect(validationErrorSummary([
      { instancePath: '/batch', keyword: 'required', params: { missingProperty: 'name' } },
      { instancePath: '/batch', keyword: 'required', params: { missingProperty: 'name' } }
    ])).toBe('/batch is missing "name"; and 1 more problem(s)')
  })
})
