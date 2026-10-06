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

import { describe, it, expect } from 'vitest'
import { PourEvent } from '@/modules/classes'

describe('PourEvent - Data Class', () => {
  describe('Constructor', () => {
    it('should create a PourEvent with default values', () => {
      const p = new PourEvent()
      expect(p.id).toBe('')
      expect(p.vesselId).toBe('')
      expect(p.pourAmount).toBe(0.0)
      expect(p.volumeRemaining).toBe(0.0)
      expect(p.isManual).toBe(false)
      expect(p.excluded).toBe(false)
      expect(p.createdAt).toBe('')
    })

    it('should create a PourEvent with provided values', () => {
      const p = new PourEvent({
        id: 'abc',
        vesselId: 'v1',
        pourAmount: 0.5,
        volumeRemaining: 9.5,
        isManual: true
      })
      expect(p.id).toBe('abc')
      expect(p.vesselId).toBe('v1')
      expect(p.pourAmount).toBe(0.5)
      expect(p.volumeRemaining).toBe(9.5)
      expect(p.isManual).toBe(true)
    })

    it('should default null pourAmount to 0.0', () => {
      const p = new PourEvent({ pourAmount: null })
      expect(p.pourAmount).toBe(0.0)
    })
  })

  describe('fromJson', () => {
    it('should create a PourEvent from JSON', () => {
      const json = {
        id: 'p1',
        vesselId: 'v1',
        pourAmount: 0.33,
        volumeRemaining: 4.67,
        isManual: false,
        excluded: false,
        createdAt: '2024-01-01T10:00:00'
      }
      const p = PourEvent.fromJson(json)
      expect(p.id).toBe('p1')
      expect(p.vesselId).toBe('v1')
      expect(p.pourAmount).toBe(0.33)
      expect(p.volumeRemaining).toBe(4.67)
      expect(p.isManual).toBe(false)
      expect(p.excluded).toBe(false)
      expect(p.createdAt).toBe('2024-01-01T10:00:00')
    })

    it('should default missing optional fields', () => {
      const p = PourEvent.fromJson({
        id: 'x',
        vesselId: 'y',
        pourAmount: 1.0,
        volumeRemaining: 9.0
      })
      expect(p.isManual).toBe(false)
      expect(p.excluded).toBe(false)
      expect(p.createdAt).toBe('')
    })
  })

  describe('toJson', () => {
    it('should serialize only mutable fields', () => {
      const p = new PourEvent({ id: 'p1', vesselId: 'v1', pourAmount: 0.5, volumeRemaining: 9.5 })
      const json = p.toJson()
      expect(json.pourAmount).toBe(0.5)
      expect(json.id).toBeUndefined()
      expect(json.vesselId).toBeUndefined()
    })
  })

  describe('setters', () => {
    it('should update fields via setters', () => {
      const p = new PourEvent()
      p.pourAmount = 1.0
      p.excluded = true
      expect(p.pourAmount).toBe(1.0)
      expect(p.excluded).toBe(true)
    })
  })
})

describe('PourEvent - additional coverage', () => {
  it('constructor undefined branches use defaults', () => {
    const p = new PourEvent({
      pourAmount: undefined,
      volumeRemaining: undefined,
      isManual: undefined,
      excluded: undefined,
      createdAt: undefined
    })
    expect(p.pourAmount).toBe(0.0)
    expect(p.volumeRemaining).toBe(0.0)
    expect(p.isManual).toBe(false)
    expect(p.excluded).toBe(false)
    expect(p.createdAt).toBe('')
  })

  it('fromJson undefined optional fields default correctly', () => {
    const p = PourEvent.fromJson({
      id: 'p1',
      vesselId: 'v1',
      pourAmount: 0.5,
      volumeRemaining: 9.0
    })
    expect(p.isManual).toBe(false)
    expect(p.excluded).toBe(false)
    expect(p.createdAt).toBe('')
  })

  it('exercises all remaining getters and setters', () => {
    const p = new PourEvent({
      id: 'p1',
      vesselId: 'v1',
      pourAmount: 0.5,
      volumeRemaining: 9.0,
      isManual: true,
      excluded: false,
      createdAt: '2024-01-01T10:00:00'
    })
    expect(p.id).toBe('p1')
    expect(p.vesselId).toBe('v1')
    expect(p.volumeRemaining).toBe(9.0)
    expect(p.isManual).toBe(true)
    expect(p.createdAt).toBe('2024-01-01T10:00:00')

    p.id = 'p2'
    p.vesselId = 'v2'
    p.volumeRemaining = 8.0
    p.isManual = false
    p.createdAt = '2024-02-01T10:00:00'

    expect(p.id).toBe('p2')
    expect(p.vesselId).toBe('v2')
    expect(p.volumeRemaining).toBe(8.0)
    expect(p.isManual).toBe(false)
    expect(p.createdAt).toBe('2024-02-01T10:00:00')
  })
})
