/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

/*
 * This module's output, validated against the shared schema.
 *
 * Several programs produce `brewgraph-batch-export-v1` -- this module validates
 * each against the shared schema, rather than each producer pinning its own key
 * set in its own test — independent, self-consistent key lists can each pass
 * while still disagreeing with each other.
 *
 * `api/oss/export-v1.schema.json` is the single definition. Validating against it
 * checks more than a key list can -- types, the `mode` enum, and that `ml` depth
 * carries no identity field or ingest token.
 */

import { describe, it, expect } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
// The 2020-12 build specifically: ajv's default export is draft-07 and rejects
// the schema outright, which is a clearer failure than silently ignoring
// `unevaluatedProperties` -- the keyword the whole schema depends on.
import Ajv from 'ajv/dist/2020'
import { buildExportDocument } from '../exportDocument'

/*
 * Walk up for the schema rather than hardcoding a depth. `import.meta.url` is not
 * a file URL under this vitest config, and a fixed `../../..` chain breaks the
 * moment the suite moves or the runner's cwd changes -- either of which would
 * leave every assertion passing against nothing.
 */
const findSchema = () => {
  let dir = process.cwd()
  for (;;) {
    const candidate = resolve(dir, 'api/oss/export-v1.schema.json')
    if (existsSync(candidate)) return candidate
    const parent = dirname(dir)
    if (parent === dir) throw new Error('api/oss/export-v1.schema.json not found')
    dir = parent
  }
}

const schema = JSON.parse(readFileSync(findSchema(), 'utf8'))
const validate = new Ajv({ strict: false, allErrors: true }).compile(schema)

const explain = () => JSON.stringify(validate.errors, null, 2)


const device = {
  id: 'd1',
  chipId: 'chip1',
  name: 'Gravity',
  board: 'esp32',
  token: 'tok',
  url: 'http://x'
}
const batch = {
  id: 'b1',
  name: 'Test Batch',
  brewDate: '2026-01-01',
  gravity: [{ deviceId: 'd1', gravity: 1.05, createdAt: '2026-01-02T00:00:00Z' }],
  pressure: [{ deviceId: 'd1', pressure: 1.2, createdAt: '2026-01-02T00:00:00Z' }]
}

const batchWithNotes = {
  ...batch,
  batchNotes: [
    { content: 'Dry hopped — 50g Citra', createdAt: '2026-01-05T12:00:00Z', noteType: 'general' },
    {
      content: 'Diacetyl test clean',
      createdAt: '2026-01-09T09:00:00Z',
      noteType: 'diacetyl_test',
      testResult: 'pass'
    }
  ]
}

const build = (mode) => buildExportDocument({ batches: [batch], devices: [device], mode })

describe('export document conforms to the shared schema', () => {
  it('ml mode validates', () => {
    expect(validate(build('ml')) ? null : explain()).toBe(null)
  })

  it('archive and backup validate', () => {
    // A missing `batchNotes` block is out of spec at archive, and silent data
    // loss on restore at backup.
    for (const mode of ['archive', 'backup']) {
      expect(validate(build(mode)) ? null : `${mode}: ${explain()}`).toBe(null)
    }
  })

  it('declares its own mode, because depth is not inferable from content', () => {
    for (const mode of ['ml', 'backup']) {
      expect(build(mode).mode).toBe(mode)
    }
  })

  it('never writes a truth block', () => {
    // `truth` is a human judgement. The schema permits one on a stored file, so
    // this is the half a schema cannot express: no *producer* may write it.
    for (const mode of ['ml', 'backup']) {
      expect(build(mode).batches[0]).not.toHaveProperty('truth')
    }
  })

  it('keeps ingest tokens out of ml depth', () => {
    expect(build('ml').devices[0]).not.toHaveProperty('token')
    expect(build('backup').devices[0]).toHaveProperty('token')
  })

  it('rejects a document that drops a reading column', () => {
    // Guards the guard: if the schema stopped rejecting, every case above would
    // pass for the wrong reason.
    const doc = build('ml')
    delete doc.batches[0].gravityReadings[0].runTime
    expect(validate(doc)).toBe(false)
  })
})

describe('batchNotes', () => {
  /*
   * `archive` is `ml` + `batchNotes[]`; `backup` is everything. The builder
   * must emit `batchNotes` at both depths, or a restore silently drops every
   * note a batch had.
   */
  it.each(['archive', 'backup'])('carries the notes it was given at %s depth', (mode) => {
    const doc = buildExportDocument({ batches: [batchWithNotes], devices: [device], mode })
    expect(validate(doc) ? null : explain()).toBe(null)
    expect(doc.batches[0].batchNotes).toEqual([
      {
        content: 'Dry hopped — 50g Citra',
        createdAt: '2026-01-05T12:00:00Z',
        noteType: 'general',
        testResult: null
      },
      {
        content: 'Diacetyl test clean',
        createdAt: '2026-01-09T09:00:00Z',
        noteType: 'diacetyl_test',
        testResult: 'pass'
      }
    ])
  })

  it('omits notes entirely at ml depth', () => {
    // Notes are user-authored prose. `ml` records what was measured, and a
    // training corpus has no business carrying someone's brew log.
    const doc = buildExportDocument({ batches: [batchWithNotes], devices: [device], mode: 'ml' })
    expect(doc.batches[0]).not.toHaveProperty('batchNotes')
  })

  it('emits an empty list rather than omitting the key when a batch has none', () => {
    // The key is required at archive depth, so "no notes" and "notes not
    // exported" must not look the same to a reader.
    expect(build('archive').batches[0].batchNotes).toEqual([])
  })

  it('keeps testResult, which is a decision and not an annotation', () => {
    // A diacetyl result is the brewer's judgement that the beer is ready. It
    // would be the easiest field to drop as "just metadata" and the worst to lose.
    const doc = buildExportDocument({
      batches: [batchWithNotes],
      devices: [device],
      mode: 'backup'
    })
    expect(doc.batches[0].batchNotes[1].testResult).toBe('pass')
  })
})
