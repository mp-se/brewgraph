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
import { Pour } from '@/modules/classes'

describe('Pour - Data Class', () => {
  describe('Constructor', () => {
    it('should create a Pour with default values', () => {
      const p = new Pour()
      expect(p.id).toBe(0)
      expect(p.pour).toBe(0.0)
      expect(p.volume).toBe(0.0)
      expect(p.maxVolume).toBe(0.0)
      expect(p.created).toBe('')
      expect(p.batchId).toBe(0)
      expect(p.active).toBe(true)
    })

    it('should use provided values', () => {
      const p = new Pour({
        id: 5,
        pour: 0.5,
        volume: 9.5,
        maxVolume: 19.0,
        created: '2024-01-01',
        batchId: 10,
        active: false
      })
      expect(p.id).toBe(5)
      expect(p.pour).toBe(0.5)
      expect(p.volume).toBe(9.5)
      expect(p.maxVolume).toBe(19.0)
      expect(p.created).toBe('2024-01-01')
      expect(p.batchId).toBe(10)
      expect(p.active).toBe(false)
    })
  })

  describe('fromJson', () => {
    it('should create a Pour from JSON', () => {
      const json = {
        id: 3,
        pour: 0.33,
        volume: 8.0,
        maxVolume: 19.0,
        created: '2024-05-01T10:00:00',
        batchId: 7,
        active: true
      }
      const p = Pour.fromJson(json)
      expect(p.id).toBe(3)
      expect(p.pour).toBe(0.33)
      expect(p.volume).toBe(8.0)
      expect(p.maxVolume).toBe(19.0)
      expect(p.created).toBe('2024-05-01T10:00:00')
      expect(p.batchId).toBe(7)
      expect(p.active).toBe(true)
    })
  })

  describe('toJson', () => {
    it('should serialize all fields including batchId', () => {
      const p = new Pour({
        pour: 1.0,
        volume: 5.0,
        maxVolume: 10.0,
        created: '2024-06-01',
        batchId: 2,
        active: false
      })
      const json = p.toJson()
      expect(json.pour).toBe(1.0)
      expect(json.volume).toBe(5.0)
      expect(json.maxVolume).toBe(10.0)
      expect(json.created).toBe('2024-06-01')
      expect(json.batchId).toBe(2)
      expect(json.active).toBe(false)
      expect(json.id).toBeUndefined()
    })
  })

  describe('setters', () => {
    it('should update all fields via setters', () => {
      const p = new Pour()
      p.id = 99
      p.pour = 2.0
      p.volume = 7.0
      p.maxVolume = 20.0
      p.created = '2024-08-01'
      p.batchId = 15
      p.active = false
      expect(p.pour).toBe(2.0)
      expect(p.volume).toBe(7.0)
      expect(p.batchId).toBe(15)
      expect(p.active).toBe(false)
    })
  })
})

describe('Pour - undefined branch coverage', () => {
  it('constructor uses defaults when fields are undefined', () => {
    const p = new Pour({
      pour: undefined,
      volume: undefined,
      maxVolume: undefined,
      created: undefined,
      batchId: undefined,
      active: undefined
    })
    expect(p.pour).toBe(0.0)
    expect(p.volume).toBe(0.0)
    expect(p.maxVolume).toBe(0.0)
    expect(p.created).toBe('')
    expect(p.batchId).toBe(0)
    expect(p.active).toBe(true)
  })
})
