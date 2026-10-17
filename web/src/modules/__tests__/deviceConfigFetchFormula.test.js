/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import { describe, it, expect, vi } from 'vitest'

const logged = []
vi.mock('@/ui', () => ({
  logDebug: (...args) => logged.push(args),
  logError: (...args) => logged.push(args)
}))
vi.mock('@/modules/detect', () => ({
  detectMdns: () => 'gravmon',
  detectPlatform: () => 'esp32',
  detectDeviceType: () => 'gravitymon'
}))

import { Device } from '@/modules/classes'
import { fetchDeviceConfigV1 } from '../deviceConfigFetch'
import { describeFormulaFill, FORMULA_NOT_APPLIED, fillFormulaFromConfig } from '../backup/deviceConfigFormula'

const FORMULA = '0.000028686523*tilt^2-0.00036143062*tilt+0.99992490'
const answers = {
  'api/status': { id: 'abc123', app_ver: '2.0' },
  'api/config': {
    wifi_pass: 'S3CRET-WIFI', mqtt_pass: 'S3CRET-MQTT', influxdb2_token: 'S3CRET-INFLUX',
    gravity_formula: FORMULA, gravity_unit: 'P',
    formula_calculation_data: [{ a: 30, g: 1.03 }, { a: 0, g: 1.09 }, { a: 45, g: 1.05 }]
  },
  'api/feature': {},
  'api/format': 'json'
}
const proxy = async (_method, url) => answers[url.replace('http://gm.local/', '')]

/** The fetch followed by the fill, as the device page does it. */
async function fetchAndFill(device) {
  expect(await fetchDeviceConfigV1(device, proxy, () => {})).toBe(true)
  logged.length = 0 // the fetch's own debug trace is not under test; the fill must add nothing
  const fill = fillFormulaFromConfig(device)
  Object.assign(device, fill.fields)
  return fill
}

describe('fetching a configuration and filling the formula fields', () => {
  it('fills a device with no formula, replaces its default unit and marks it changed', async () => {
    const device = new Device({ url: 'http://gm.local/', gravityFormulaUnit: 'sg' })
    const saved = Device.fromJson(device.toJson())
    const fill = await fetchAndFill(device)

    expect(fill.problems).toEqual([])
    expect(device.gravityFormula).toBe(FORMULA)
    expect(device.gravityFormulaUnit).toBe('plato')
    expect(device.gravityCalibrationData).toEqual([{ angle: 30, gravity: 1.03 }, { angle: 45, gravity: 1.05 }])
    expect(Device.compare(device, saved)).toBe(false)
    expect(describeFormulaFill(fill)).toBe('Filled formula, unit (plato), 2 calibration points from the device configuration')
    expect(device.toJson()).not.toHaveProperty('applyGravityFormula', true)
  })

  it('fills nothing when the device already has a formula, and says so', async () => {
    const device = new Device({ url: 'http://gm.local/', gravityFormula: '1+tilt/1000', gravityFormulaUnit: 'sg' })
    const fill = await fetchAndFill(device)

    expect(fill.problems).toEqual([FORMULA_NOT_APPLIED])
    expect(device.gravityFormula).toBe('1+tilt/1000')
    expect(device.gravityFormulaUnit).toBe('sg')
    expect(device.gravityCalibrationData).toEqual([])
  })

  it('lets nothing else from the configuration reach the fields, messages or logs', async () => {
    const device = new Device({ url: 'http://gm.local/' })
    const fill = await fetchAndFill(device)
    const visible = JSON.stringify({ fields: fill.fields, problems: fill.problems, text: describeFormulaFill(fill), logged })
    expect(visible).not.toContain('S3CRET')
    expect(logged).toEqual([])
    expect(Object.keys(fill.fields).sort()).toEqual(['gravityCalibrationData', 'gravityFormula', 'gravityFormulaUnit'])
  })
})
