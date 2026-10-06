/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

/*
 * What `brewloggerRestore` is expected to accept, pinned to a schema.
 *
 * BrewLogger's format is one we do not control, so the balance differs from the
 * export schema: a false rejection refuses a user's real data. Unknown keys are
 * therefore allowed and almost nothing is required. Wrong *types* are what the
 * schema exists to catch — a gravity of "1.010" reads fine and computes wrong.
 *
 * Derived from the BrewLogger source (src/modules/classes/*.js,
 * src/views/BackupView.vue) plus a survey of 7 real exports. Two
 * behaviours drive the shape: `cleanupJson()` deletes every null before writing,
 * while other export paths keep theirs, so each optional field permits both.
 */

import { describe, it, expect } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import Ajv from 'ajv/dist/2020'

const findSchema = () => {
  let dir = process.cwd()
  for (;;) {
    const candidate = resolve(dir, 'api/oss/brewlogger-import.schema.json')
    if (existsSync(candidate)) return candidate
    const parent = dirname(dir)
    if (parent === dir) throw new Error('api/oss/brewlogger-import.schema.json not found')
    dir = parent
  }
}

const validate = new Ajv({ strict: false, allErrors: true }).compile(
  JSON.parse(readFileSync(findSchema(), 'utf8'))
)

const exportFile = () => ({
  name: '83. Helles ESP32 ICM',
  chipIdGravity: '19a54c',
  brewDate: '2026-07-03',
  og: 1.048029411,
  fg: 1.009,
  // A JSON-encoded string in every real export, not an array.
  fermentationSteps: '[{"order": 0, "temp": 10, "days": 10, "type": "Primary"}]',
  predictionAtTimestamp: null,
  id: 46,
  gravity: [
    {
      temperature: 10.5,
      gravity: 1.0221,
      velocity: null,
      angle: 45.3,
      battery: 4.05,
      rssi: -62,
      corrGravity: 1.0223,
      runTime: 3,
      created: '2026-07-04T10:00:00',
      active: true,
      chamberTemperature: null,
      beerTemperature: null,
      batchId: 46,
      id: 9001
    }
  ],
  pressure: [],
  pour: []
})

const explain = () => JSON.stringify(validate.errors, null, 2)


describe('brewlogger import schema', () => {
  it('accepts a single-batch export', () => {
    expect(validate(exportFile()) ? null : explain()).toBe(null)
  })

  it('accepts a backup container', () => {
    const backup = {
      meta: { version: '0.8', software: 'BrewLogger', created: '2026-08-19' },
      batches: [exportFile()],
      devices: [],
      pressure: [],
      pour: []
    }
    expect(validate(backup) ? null : explain()).toBe(null)
  })

  it('accepts an export with every null stripped', () => {
    // cleanupJson() removes null-valued keys, so absent must be as valid as null.
    const doc = exportFile()
    for (const k of Object.keys(doc)) if (doc[k] === null) delete doc[k]
    doc.gravity = doc.gravity.map((r) => {
      const out = { ...r }
      for (const k of Object.keys(out)) if (out[k] === null) delete out[k]
      return out
    })
    expect(validate(doc) ? null : explain()).toBe(null)
  })

  it('accepts unknown keys, so a future BrewLogger version still imports', () => {
    const doc = exportFile()
    doc.somethingBrewLoggerAddsIn2027 = 42
    expect(validate(doc) ? null : explain()).toBe(null)
  })

  it.each([
    ['batch loses its name', (d) => delete d.name],
    ['batch loses its readings', (d) => delete d.gravity],
    ['a reading loses created', (d) => delete d.gravity[0].created],
    ['created is empty', (d) => (d.gravity[0].created = '')],
    ['gravity arrives as a string', (d) => (d.gravity[0].gravity = '1.010')],
    ['og arrives as a string', (d) => (d.og = '1.048')],
    ['readings are not a list', (d) => (d.gravity = {})],
    ['active is a string', (d) => (d.gravity[0].active = 'yes')]
  ])('rejects: %s', (_name, mutate) => {
    const doc = exportFile()
    mutate(doc)
    expect(validate(doc)).toBe(false)
  })
})
