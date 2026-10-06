/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import { describe, it, expect } from 'vitest'
import { describeBackupFormat } from '../detectFormat'
import { buildExportDocument } from '../exportDocument'

describe('describeBackupFormat', () => {
  it('names a BrewLogger file by its meta block', () => {
    expect(describeBackupFormat({ meta: { software: 'BrewLogger', version: '0.8' } })).toBe(
      'BrewLogger v0.8'
    )
  })

  it('names a file this app wrote, which carries source and schemaVersion instead of meta', () => {
    const doc = buildExportDocument({ devices: [], taps: [], vessels: [], batches: [] })
    expect(describeBackupFormat(doc)).toBe(`BrewGraph v${doc.schemaVersion}`)
  })

  it('does not claim a version for something unrecognised', () => {
    expect(describeBackupFormat({ foo: 1 })).toBe('Unknown format')
    expect(describeBackupFormat(null)).toBe('Unknown format')
  })
})
