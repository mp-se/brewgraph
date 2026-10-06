/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

/*
 * Runtime validation of import files.
 *
 * Both schemas run at runtime, not just against our own producers in tests.
 * These tests cover the consumer side, where the rules are deliberately different — see
 * `relaxForImport` in validateDocument.ts for why a producer schema and a consumer
 * schema are not the same schema.
 */

import { describe, it, expect } from 'vitest'
import { validateExportDocument, validateBrewloggerDocument } from '../validateDocument'
import { buildExportDocument } from '../exportDocument'

const device = { id: 'd1', chipId: 'chip1', name: 'Gravity', board: 'esp32', token: 'tok' }
const batch = {
  id: 'b1',
  name: 'Test Batch',
  brewDate: '2026-01-01',
  gravity: [{ deviceId: 'd1', gravity: 1.05, createdAt: '2026-01-02T00:00:00Z' }],
  pressure: []
}
const backup = () => buildExportDocument({ batches: [batch], devices: [device], mode: 'backup' })

describe('validateExportDocument', () => {
  it('accepts a document this codebase just produced', () => {
    // The floor: whatever we write, we must be able to read back.
    expect(validateExportDocument(backup())).toBeNull()
  })

  it.each(['ml', 'archive', 'backup'])('accepts %s depth', (mode) => {
    expect(
      validateExportDocument(buildExportDocument({ batches: [batch], devices: [device], mode }))
    ).toBeNull()
  })

  it('rejects a gravity that arrived as a string', () => {
    // The corruption that reads fine and computes wrong — the reason this check
    // exists at all, rather than just checking the header.
    const doc = backup()
    doc.batches[0].gravityReadings[0].gravity = '1.010'
    expect(validateExportDocument(doc)).toMatch(/gravityReadings\/0\/gravity should be number/)
  })

  it('rejects batches arriving as an object instead of a list', () => {
    // Restores nothing while looking like it worked.
    const doc = backup()
    doc.batches = { b1: batch }
    expect(validateExportDocument(doc)).toMatch(/batches should be array/)
  })

  it('rejects a wrong schemaVersion', () => {
    const doc = { ...backup(), schemaVersion: '2' }
    expect(validateExportDocument(doc)).not.toBeNull()
  })

  it('rejects a document that is not an object at all', () => {
    expect(validateExportDocument('a string')).not.toBeNull()
    expect(validateExportDocument(null)).not.toBeNull()
  })

  /*
   * The two deliberate leniencies. Both would be failures in the producer suite
   * and both must pass here: a restore is what someone does after something has
   * already gone wrong, so refusing a file that would restore perfectly is the
   * expensive mistake.
   */
  it('accepts a backup missing a field it was written before', () => {
    const doc = backup()
    delete doc.batches[0].costCurrency
    delete doc.batches[0].yeastProductId
    expect(validateExportDocument(doc)).toBeNull()
  })

  it('accepts a backup from a newer build carrying an unknown field', () => {
    // `unevaluatedProperties: false` in the producer schema would refuse this,
    // which would mean a newer file cannot be restored by an older app.
    const doc = backup()
    doc.batches[0].somethingAddedIn2027 = 42
    doc.thisToo = 'ignored'
    expect(validateExportDocument(doc)).toBeNull()
  })

  it('still applies the right per-mode shape after relaxation', () => {
    // Guards the relaxation itself: `if` conditions use `required` internally, so
    // stripping it everywhere would make all three mode branches match at once and
    // the per-depth rules would quietly stop applying.
    const doc = backup()
    doc.batches[0].gravityReadings[0].gravity = 'not a number'
    expect(validateExportDocument(doc)).not.toBeNull()
  })
})

describe('validateBrewloggerDocument', () => {
  const blBatch = () => ({
    name: '83. Helles',
    gravity: [{ created: '2026-07-04T10:00:00', gravity: 1.0221 }]
  })

  it('accepts a minimal single-batch export', () => {
    expect(validateBrewloggerDocument(blBatch())).toBeNull()
  })

  it('accepts a backup container', () => {
    expect(
      validateBrewloggerDocument({
        meta: { version: '0.8' },
        batches: [blBatch()],
        devices: [],
        pressure: [],
        pour: []
      })
    ).toBeNull()
  })

  it('accepts unknown keys, so a future BrewLogger version still imports', () => {
    expect(validateBrewloggerDocument({ ...blBatch(), somethingNew: 1 })).toBeNull()
  })

  it('rejects a gravity that arrived as a string', () => {
    const doc = blBatch()
    doc.gravity[0].gravity = '1.010'
    expect(validateBrewloggerDocument(doc)).not.toBeNull()
  })

  it('rejects something that is not a BrewLogger file at all', () => {
    expect(validateBrewloggerDocument({ hello: 'world' })).not.toBeNull()
  })
})

describe('error messages', () => {
  it('names the failing path so a brewer can find it', () => {
    const doc = backup()
    doc.batches[0].gravityReadings[0].gravity = '1.010'
    // ajv's raw output is a keyword plus a JSON pointer. The pointer is the useful
    // half — it says which batch and which field.
    expect(validateExportDocument(doc)).toContain('/batches/0/gravityReadings/0/gravity')
  })

  it('caps a flood of errors rather than printing hundreds', () => {
    // A file of the wrong shape produces one error per element. Five, then a count.
    const doc = backup()
    doc.batches = Array.from({ length: 50 }, () => ({ gravityReadings: 'nope' }))
    const message = validateExportDocument(doc)
    expect(message).toMatch(/and \d+ more problem\(s\)/)
    expect(message.split(';').length).toBeLessThanOrEqual(6)
  })
})

describe('a backup whose batches have lost their identity', () => {
  it('is refused, because restoring it would delete everything and recreate nothing', () => {
    const doc = buildExportDocument({
      mode: 'backup',
      devices: [],
      batches: [{ id: 'b1', name: 'Good', status: 'fermenting' }, { id: null, name: null, status: null }]
    })
    doc.batches[1].id = null
    doc.batches[1].name = null
    expect(validateExportDocument(doc)).toMatch(/1 of 2 batches have no id or name \(\/batches\/1\)/)
  })

  it('accepts a backup whose batches are named', () => {
    const doc = buildExportDocument({
      mode: 'backup',
      batches: [{ id: 'b1', name: 'Good', status: 'fermenting' }]
    })
    expect(validateExportDocument(doc)).toBeNull()
  })
})
