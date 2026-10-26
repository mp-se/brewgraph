/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { describeFormulaFill, FORMULA_NOT_APPLIED, fillFormulaFromConfig } from '../deviceConfigFormula'
import { buildDeviceEntry } from '../exportDocument'
import { mapDevicePayload } from '../restoreMapping'
import { restoreDevices } from '../restoreEntities'
import { emptyRestoreReport } from '../restoreSupport'

const logged: unknown[][] = []
vi.mock('@/ui', () => ({
  logDebug: (...args: unknown[]) => { logged.push(args) },
  logInfo: (...args: unknown[]) => { logged.push(args) },
  logError: (...args: unknown[]) => { logged.push(args) }
}))

const SECRETS = ['S3CRET-WIFI', 'S3CRET-TOKEN', 'S3CRET-MQTT', 'secret.example/hook', 'S3CRET-INFLUX']

type Slot = { a: number; g: number }
const slots = (used: Slot[]): Slot[] =>
  [...used, ...Array.from({ length: Math.max(0, 20 - used.length) }, () => ({ a: 0, g: 1 }))]

/** The capture envelope a device row carries, around a firmware answer holding dummy secrets. */
function capture(firmware: Record<string, unknown>, asObjects = false): string | Record<string, unknown> {
  const config = {
    wifi_ssid: 'dummy-net', wifi_pass: 'S3CRET-WIFI', token: 'S3CRET-TOKEN', mqtt_pass: 'S3CRET-MQTT',
    http_post_target: 'http://secret.example/hook', influxdb2_token: 'S3CRET-INFLUX',
    formula_calibration_temp: 20, gravity_temp_adjustment: true, gyro_calibration: [1, 2, 3],
    ...firmware
  }
  const raw = { config, format: 'json', status: { rssi: -60 } }
  const envelope = {
    v: 1, kind: 'device-config', capturedAt: '2026-10-02T13:54:12Z', source: 'proxy_fetch',
    data: { raw: asObjects ? raw : JSON.stringify(raw) }
  }
  return asObjects ? envelope : JSON.stringify(envelope)
}

const POLYNOMIAL = '0.000028686523*tilt^2-0.00036143062*tilt+0.99992490'
const EXPONENT = '-8.1595791e-7*tilt^3+0.00010120890*tilt^2-0.0022066128*tilt+0.99997836'
const EXPONENT_STORED = '-0.00000081595791*tilt^3+0.00010120890*tilt^2-0.0022066128*tilt+0.99997836'
const sixPoints: Slot[] = [27.7, 30, 35, 40, 45, 50].map((a, i) => ({ a, g: 1 + i * 0.01 }))
const fivePoints: Slot[] = [20, 30, 40, 50, 60].map((a, i) => ({ a, g: 1.01 + i * 0.01 }))

function device(config: unknown, extra: Record<string, unknown> = {}) {
  return { chipId: 'aabbcc', name: 'Hydrometer', role: 'gravity', deviceType: 'gravitymon', config, ...extra }
}

describe('filling the formula fields from a device capture', () => {
  it('reads a plain polynomial, its unit and its used points', () => {
    const fill = fillFormulaFromConfig(device(capture({
      gravity_formula: POLYNOMIAL, gravity_unit: 'G', formula_calculation_data: slots(sixPoints)
    })))
    expect(fill.problems).toEqual([])
    expect(fill.fields.gravityFormula).toBe(POLYNOMIAL)
    expect(fill.fields.gravityFormulaUnit).toBe('sg')
    expect(fill.fields.gravityCalibrationData).toEqual(sixPoints.map(p => ({ angle: p.a, gravity: p.g })))
  })

  it('rewrites exponent notation and reads the older unit key', () => {
    const fill = fillFormulaFromConfig(device(capture({
      gravity_formula: EXPONENT, gravity_format: 'P', formula_calculation_data: slots(fivePoints)
    })))
    expect(fill.fields.gravityFormula).toBe(EXPONENT_STORED)
    expect(fill.fields.gravityFormulaUnit).toBe('plato')
    expect(fill.fields.gravityCalibrationData).toHaveLength(5)
  })

  it('reads a firmware answer stored as it came, without the capture envelope', () => {
    const bare = JSON.stringify({
      status: { rssi: -60 }, format: 'json',
      config: { token: 'S3CRET-TOKEN', gravity_formula: EXPONENT, gravity_format: 'G', formula_calculation_data: fivePoints }
    })
    const fill = fillFormulaFromConfig(device(bare))
    expect(fill.fields.gravityFormula).toBe(EXPONENT_STORED)
    expect(fill.fields.gravityFormulaUnit).toBe('sg')
    expect(fill.fields.gravityCalibrationData).toHaveLength(5)
    expect(JSON.stringify(fill)).not.toContain('S3CRET')
  })

  it('lets gravity_unit win over gravity_format', () => {
    const fill = fillFormulaFromConfig(device(capture({ gravity_unit: 'G', gravity_format: 'P' })))
    expect(fill.fields.gravityFormulaUnit).toBe('sg')
  })

  it('fills points without a formula and drops unused slots whatever their gravity', () => {
    const used: Slot[] = [{ a: 27.7, g: 1 }, { a: 0, g: 1.05 }, { a: 45, g: 1.04 }]
    const fill = fillFormulaFromConfig(device(capture({
      gravity_formula: '', gravity_unit: 'G', formula_calculation_data: slots(used)
    })))
    expect(fill.fields.gravityFormula).toBeUndefined()
    expect(fill.fields.gravityCalibrationData).toEqual([
      { angle: 27.7, gravity: 1 }, { angle: 45, gravity: 1.04 }
    ])
  })

  it('accepts a capture whose levels are already objects', () => {
    const fill = fillFormulaFromConfig(device(capture({ gravity_formula: POLYNOMIAL }, true)))
    expect(fill.fields.gravityFormula).toBe(POLYNOMIAL)
  })

  it('leaves a rejected formula out, reports it, and still fills unit and points', () => {
    const fill = fillFormulaFromConfig(device(capture({
      gravity_formula: 'bad(tilt)', gravity_unit: 'P', formula_calculation_data: slots(fivePoints)
    })))
    expect(fill.fields.gravityFormula).toBeUndefined()
    expect(fill.problems).toHaveLength(1)
    expect(fill.problems[0]).toMatch(/^gravity formula left out/)
    expect(fill.fields.gravityFormulaUnit).toBe('plato')
    expect(fill.fields.gravityCalibrationData).toHaveLength(5)
  })

  it('drops and reports points that fail point validation or repeat an angle', () => {
    const fill = fillFormulaFromConfig(device(capture({
      formula_calculation_data: slots([
        { a: 10, g: 1.02 }, { a: 30, g: 2 }, { a: 40, g: 1.04 }, { a: 40, g: 1.05 }, { a: 50, g: 1.05 }
      ])
    })))
    expect(fill.fields.gravityCalibrationData).toEqual([{ angle: 40, gravity: 1.04 }, { angle: 50, gravity: 1.05 }])
    expect(fill.problems).toEqual(['3 calibration points left out (outside the valid range or repeated)'])
  })

  it('keeps at most the calibration limit of points', () => {
    const many: Slot[] = Array.from({ length: 25 }, (_, i) => ({ a: 20 + i, g: 1.02 }))
    const fill = fillFormulaFromConfig(device(capture({ formula_calculation_data: many })))
    expect(fill.fields.gravityCalibrationData).toHaveLength(20)
  })

  it('never overwrites a formula or a point that is already set, and says so', () => {
    const config = capture({ gravity_formula: POLYNOMIAL, gravity_unit: 'G', formula_calculation_data: slots(sixPoints) })
    for (const set of [
      { gravityFormula: '1+tilt/1000' },
      { gravityFormula: '1+tilt/1000', gravityFormulaUnit: 'plato' },
      { gravityCalibrationData: [{ angle: 30, gravity: 1.03 }] }
    ]) {
      const fill = fillFormulaFromConfig(device(config, set))
      expect(fill.fields).toEqual({})
      expect(fill.problems).toEqual([FORMULA_NOT_APPLIED])
    }
  })

  it('stays silent when the device has a formula but the configuration carries none', () => {
    const fill = fillFormulaFromConfig(device(capture({ gravity_formula: '', gravity_unit: 'G' }), { gravityFormula: '1+tilt/1000' }))
    expect(fill).toEqual({ fields: {}, problems: [] })
  })

  it('stays silent when the configuration holds what the device already has', () => {
    const config = capture({ gravity_formula: EXPONENT, gravity_unit: 'G', formula_calculation_data: slots(fivePoints) })
    const same = { gravityFormula: EXPONENT_STORED, gravityCalibrationData: fivePoints.map(p => ({ angle: p.a, gravity: p.g })).reverse() }
    expect(fillFormulaFromConfig(device(config, same))).toEqual({ fields: {}, problems: [] })
    const other = { ...same, gravityCalibrationData: [{ angle: 20, gravity: 1.05 }] }
    expect(fillFormulaFromConfig(device(config, other)).problems).toEqual([FORMULA_NOT_APPLIED])
  })

  it('fills only a device with an explicit gravity type', () => {
    const config = capture({ gravity_formula: POLYNOMIAL, gravity_unit: 'G' })
    for (const deviceType of [null, undefined, '']) {
      expect(fillFormulaFromConfig(device(config, { deviceType }))).toEqual({ fields: {}, problems: [] })
    }
    for (const deviceType of ['gravitymon', 'ispindel', 'rapt_pill']) {
      expect(fillFormulaFromConfig(device(config, { deviceType })).fields.gravityFormula).toBe(POLYNOMIAL)
    }
  })

  it('fills an empty device', () => {
    const fill = fillFormulaFromConfig(device(capture({ gravity_formula: POLYNOMIAL, gravity_unit: 'P', formula_calculation_data: slots(fivePoints) }),
      { gravityFormula: null, gravityFormulaUnit: null, gravityCalibrationData: [] }))
    expect(Object.keys(fill.fields).sort()).toEqual(['gravityCalibrationData', 'gravityFormula', 'gravityFormulaUnit'])
    expect(fill.problems).toEqual([])
    expect(describeFormulaFill(fill)).toBe('Filled formula, unit (plato), 5 calibration points from the device configuration')
  })

  it('fills a formula only, and points only', () => {
    expect(fillFormulaFromConfig(device(capture({ gravity_formula: POLYNOMIAL }))).fields).toEqual({ gravityFormula: POLYNOMIAL })
    const points = fillFormulaFromConfig(device(capture({ formula_calculation_data: slots(fivePoints) })))
    expect(Object.keys(points.fields)).toEqual(['gravityCalibrationData'])
  })

  it('replaces a default unit when no formula or points exist', () => {
    const fill = fillFormulaFromConfig(device(capture({ gravity_unit: 'P' }), { gravityFormulaUnit: 'sg' }))
    expect(fill.fields).toEqual({ gravityFormulaUnit: 'plato' })
    expect(describeFormulaFill(fill)).toBe('Filled unit (plato) from the device configuration')
  })

  it('never reads or sets the apply flag', () => {
    const fill = fillFormulaFromConfig(device(capture({ gravity_formula: POLYNOMIAL, applyGravityFormula: true })))
    expect(JSON.stringify(fill)).not.toMatch(/apply/i)
  })

  it('describes nothing when nothing was filled', () => {
    expect(describeFormulaFill({ fields: {}, problems: [] })).toBe('')
  })

  it.each([
    ['empty string', ''], ['null', null], ['undefined', undefined], ['not JSON', 'plain text'],
    ['JSON array', '[1,2]'], ['envelope without data', '{"v":1}'], ['data without raw', '{"data":{}}'],
    ['raw not JSON', '{"data":{"raw":"nope"}}'], ['raw without config', '{"data":{"raw":"{}"}}'],
    ['config not an object', '{"data":{"raw":"{\\"config\\":5}"}}'], ['a number', 7]
  ])('does nothing, silently, for a config that is %s', (_name, config) => {
    const fill = fillFormulaFromConfig(device(config))
    expect(fill).toEqual({ fields: {}, problems: [] })
  })

  it('ignores devices that cannot carry a formula and malformed entries', () => {
    const config = capture({ gravity_formula: POLYNOMIAL, gravity_unit: 'G' })
    expect(fillFormulaFromConfig(device(config, { deviceType: 'pressuremon' }))).toEqual({ fields: {}, problems: [] })
    const odd = fillFormulaFromConfig(device(capture({
      gravity_formula: 42, gravity_unit: 'X', formula_calculation_data: [null, 'x', { a: 'q' }, { a: 30 }]
    })))
    expect(odd.fields).toEqual({})
    expect(odd.problems).toEqual(['1 calibration point left out (outside the valid range or repeated)'])
  })
})

describe('restoring an old backup device', () => {
  const posted: Record<string, unknown>[] = []

  beforeEach(() => {
    posted.length = 0
    logged.length = 0
    globalThis.fetch = vi.fn(async (_url: RequestInfo | URL, opts: RequestInit = {}) => {
      posted.push(JSON.parse(typeof opts.body === 'string' ? opts.body : '{}'))
      return { ok: true, json: async () => ({ id: `new-${posted.length}` }) } as unknown as Response
    })
  })

  const deps = () => ({
    baseURL: 'http://x/', token: 'test-key', onProgress: vi.fn(),
    refreshDevices: vi.fn(), refreshBatches: vi.fn()
  })

  it('fills the formula fields, reports a rejected formula, and exposes no other config value', async () => {
    const consoleSpies = (['log', 'info', 'warn', 'error'] as const).map(m => vi.spyOn(console, m))
    const report = emptyRestoreReport()
    const devices = [
      device(capture({ gravity_formula: POLYNOMIAL, gravity_unit: 'G', formula_calculation_data: slots(sixPoints) }), { chipId: 'a1' }),
      device(capture({ gravity_formula: EXPONENT, gravity_format: 'P', formula_calculation_data: slots(fivePoints) }), { chipId: 'a2' }),
      device(capture({ gravity_formula: '', gravity_unit: 'G', formula_calculation_data: slots([{ a: 30, g: 1.03 }, { a: 0, g: 1.09 }]) }), { chipId: 'a3' }),
      device(capture({ gravity_formula: 'bad(tilt)', gravity_unit: 'G' }), { chipId: 'a4', name: 'Broken' }),
      device('', { chipId: 'a5', deviceType: null }),
      device(capture({ gravity_formula: POLYNOMIAL }), { chipId: 'a6', deviceType: 'pressuremon', role: 'pressure' })
    ]
    await restoreDevices(devices as never, deps() as never, report)

    expect(report.devices).toEqual({ restored: 6, failed: 0 })
    const formulaFields = (body: Record<string, unknown>) => ({
      formula: body.gravityFormula, unit: body.gravityFormulaUnit, points: body.gravityCalibrationData
    })
    expect(formulaFields(posted[0]).formula).toBe(POLYNOMIAL)
    expect((posted[0].gravityCalibrationData as unknown[]).length).toBe(6)
    expect(formulaFields(posted[1])).toMatchObject({ formula: EXPONENT_STORED, unit: 'plato' })
    expect(formulaFields(posted[2])).toEqual({ formula: undefined, unit: 'sg', points: [{ angle: 30, gravity: 1.03 }] })
    expect(posted[3].gravityFormula).toBeUndefined()
    expect(posted[4].gravityFormula).toBeUndefined()
    expect(posted[5].gravityFormula).toBeUndefined()
    expect(report.problems).toHaveLength(1)
    expect(report.problems[0]).toMatch(/^device "Broken": gravity formula left out/)

    // The export of a restored device writes the formula fields.
    const exported = buildDeviceEntry({ ...posted[1], id: 'x' } as never, 'backup')
    expect(exported).toMatchObject({
      gravityFormula: EXPONENT_STORED, gravityFormulaUnit: 'plato', gravityCalibrationData: expect.any(Array)
    })

    // None of the other captured values reach the formula fields, the result, the export or any log.
    const everywhere = JSON.stringify({
      fields: posted.map(formulaFields), report,
      exportedFields: [exported.gravityFormula, exported.gravityFormulaUnit, exported.gravityCalibrationData],
      logged, console: consoleSpies.map(spy => spy.mock.calls)
    })
    for (const secret of SECRETS) expect(everywhere).not.toContain(secret)
    for (const key of ['wifi_', 'mqtt_', 'influxdb2_', 'http_post_target']) expect(everywhere).not.toContain(key)
    consoleSpies.forEach(spy => spy.mockRestore())
  })

  it('replaces a default unit, and leaves a row with a formula untouched while reporting it', async () => {
    const report = emptyRestoreReport()
    const rows = [
      device(capture({ gravity_unit: 'P' }), { chipId: 'b1', gravityFormulaUnit: 'sg' }),
      device(capture({ gravity_formula: POLYNOMIAL, gravity_unit: 'P' }), {
        chipId: 'b2', name: 'Kept', gravityFormula: '1+tilt/1000', gravityFormulaUnit: 'sg'
      })
    ]
    await restoreDevices(rows as never, deps() as never, report)
    expect(posted[0].gravityFormulaUnit).toBe('plato')
    expect(posted[0].gravityFormula).toBeUndefined()
    expect(posted[1]).toMatchObject({ gravityFormula: '1+tilt/1000', gravityFormulaUnit: 'sg' })
    expect(posted.every(body => body.applyGravityFormula === undefined)).toBe(true)
    expect(report.problems).toEqual([`device "Kept": ${FORMULA_NOT_APPLIED}`])
  })

  it('maps a device payload with the problems of its capture', () => {
    const { payload, problems } = mapDevicePayload(device(capture({ gravity_formula: 'bad(tilt)' })) as never)
    expect(payload.gravityFormula).toBeUndefined()
    expect(problems).toHaveLength(1)
  })
})
