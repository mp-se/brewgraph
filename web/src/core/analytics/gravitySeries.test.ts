/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import { describe, expect, it } from 'vitest'
import { alcoholPoints, gravityPoints, gravityVelocityPoints } from './gravitySeries'
import { readingStats } from './readingStats'

const readings = [
  { created: '2026-01-01T10:00:00Z', gravity: 1.05 },
  { created: '2026-01-01T11:00:00Z', gravity: null },
  { created: '2026-01-01T12:00:00Z', gravity: 1.04 }
]

describe('readings without a gravity', () => {
  it('leave a gap in the gravity series instead of a zero', () => {
    expect(gravityPoints(readings, true).map((point) => point.y)).toEqual([1.05, 1.04])
  })

  it('are skipped by the alcohol and velocity series', () => {
    expect(alcoholPoints(readings)).toHaveLength(2)
    expect(() => gravityVelocityPoints(readings)).not.toThrow()
  })

  it('do not affect the gravity range', () => {
    const stats = readingStats(
      readings.map((reading) => ({ ...reading, temperature: null })),
      { getValue: (reading) => reading.gravity, getCreated: (reading) => reading.created }
    )
    expect(stats.value).toEqual({ min: 1.04, max: 1.05 })
  })
})
