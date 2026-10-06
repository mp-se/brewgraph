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
import { Tap } from '@/modules/classes'

describe('Tap - Data Class', () => {
  describe('Constructor', () => {
    it('should create a Tap with default values', () => {
      const t = new Tap()
      expect(t.id).toBe('')
      expect(t.name).toBe('')
      expect(t.tapNumber).toBeNull()
      expect(t.glassSize).toBeNull()
      expect(t.location).toBe('')
      expect(t.notes).toBe('')
      expect(t.vesselName).toBeNull()
      expect(t.volumeRemaining).toBeNull()
      expect(t.batchName).toBeNull()
      expect(t.batchId).toBeNull()
    })

    it('should create a Tap with provided values', () => {
      const t = new Tap({
        id: 't1',
        name: 'Tap 1',
        tapNumber: 1,
        location: 'bar',
        notes: 'left handle'
      })
      expect(t.id).toBe('t1')
      expect(t.name).toBe('Tap 1')
      expect(t.tapNumber).toBe(1)
      expect(t.location).toBe('bar')
      expect(t.notes).toBe('left handle')
    })

    it('should default null notes to empty string', () => {
      const t = new Tap({ notes: null })
      expect(t.notes).toBe('')
    })
  })

  describe('fromJson', () => {
    it('should create a Tap from JSON', () => {
      const json = {
        id: 't1',
        name: 'Tap 1',
        tapNumber: 2,
        glassSize: 0.33,
        location: 'kegerator',
        notes: 'IPA',
        createdAt: '2024-01-01T00:00:00',
        updatedAt: '2024-01-02T00:00:00'
      }
      const t = Tap.fromJson(json)
      expect(t.id).toBe('t1')
      expect(t.name).toBe('Tap 1')
      expect(t.tapNumber).toBe(2)
      expect(t.glassSize).toBe(0.33)
      expect(t.location).toBe('kegerator')
      expect(t.createdAt).toBe('2024-01-01T00:00:00')
    })

    it('should default glassSize to null when absent from JSON', () => {
      const t = Tap.fromJson({ id: 't1', name: 'Tap 1' })
      expect(t.glassSize).toBeNull()
    })

    it('should populate dashboard projection fields from JSON', () => {
      const json = {
        id: 't1',
        name: 'Tap 1',
        vesselName: 'Keg A',
        volumeRemaining: 15.0,
        batchName: 'Summer IPA',
        batchId: 'b1'
      }
      const t = Tap.fromJson(json)
      expect(t.vesselName).toBe('Keg A')
      expect(t.volumeRemaining).toBe(15.0)
      expect(t.batchName).toBe('Summer IPA')
      expect(t.batchId).toBe('b1')
    })

    it('should default missing optional fields to null', () => {
      const t = Tap.fromJson({ id: 't1', name: 'Tap 1' })
      expect(t.tapNumber).toBeNull()
      expect(t.vesselName).toBeNull()
      expect(t.batchId).toBeNull()
      expect(t.location).toBe('')
      expect(t.notes).toBe('')
    })

    it('should populate lastCleanedAt from JSON', () => {
      const t = Tap.fromJson({
        id: 't1',
        name: 'Tap 1',
        lastCleanedAt: '2026-01-01T00:00:00Z'
      })
      expect(t.lastCleanedAt).toBe('2026-01-01T00:00:00Z')
    })

    it('should default lastCleanedAt to empty string when absent from JSON', () => {
      const t = Tap.fromJson({ id: 't1', name: 'Tap 1' })
      expect(t.lastCleanedAt).toBe('')
    })
  })

  describe('toJson', () => {
    it('should serialize only core fields', () => {
      const t = new Tap({
        id: 't1',
        name: 'Tap 1',
        tapNumber: 3,
        glassSize: 0.33,
        location: 'bar',
        notes: 'cold'
      })
      const json = t.toJson()
      expect(json.name).toBe('Tap 1')
      expect(json.tapNumber).toBe(3)
      expect(json.glassSize).toBe(0.33)
      expect(json.location).toBe('bar')
      expect(json.notes).toBe('cold')
      expect(json.id).toBeUndefined()
      expect(json.vesselName).toBeUndefined()
      expect(json.lastCleanedAt).toBeUndefined()
    })
  })

  describe('setters', () => {
    it('should update fields via setters', () => {
      const t = new Tap()
      t.name = 'Updated Tap'
      t.tapNumber = 5
      t.glassSize = 0.5
      t.vesselName = 'Keg B'
      expect(t.name).toBe('Updated Tap')
      expect(t.tapNumber).toBe(5)
      expect(t.glassSize).toBe(0.5)
      expect(t.vesselName).toBe('Keg B')
    })
  })
})

describe('Tap - additional coverage', () => {
  it('exercises all extended getters and setters', () => {
    const t = new Tap({
      id: 't1',
      volumeRemaining: 12.5,
      batchId: 'b1',
      createdAt: '2024-01-01',
      updatedAt: '2024-01-02'
    })
    expect(t.volumeRemaining).toBe(12.5)
    expect(t.batchId).toBe('b1')
    expect(t.createdAt).toBe('2024-01-01')
    expect(t.updatedAt).toBe('2024-01-02')

    t.volumeRemaining = 5.0
    t.batchId = 'b2'
    t.batchName = 'My Beer'
    t.createdAt = '2024-06-01'
    t.updatedAt = '2024-06-02'
    t.id = 't2'
    t.location = 'bar'
    t.notes = 'cold'

    expect(t.volumeRemaining).toBe(5.0)
    expect(t.batchId).toBe('b2')
    expect(t.batchName).toBe('My Beer')
    expect(t.createdAt).toBe('2024-06-01')
    expect(t.updatedAt).toBe('2024-06-02')
    expect(t.id).toBe('t2')
  })

  it('constructor null location and notes default to empty string', () => {
    const t = new Tap({ location: null, notes: null })
    expect(t.location).toBe('')
    expect(t.notes).toBe('')
  })

  it('compare returns false for each differing field', () => {
    const base = { name: 'T1', tapNumber: 1, glassSize: 0.33, location: 'bar', notes: 'cold' }
    const a = new Tap(base)
    expect(Tap.compare(a, new Tap({ ...base, name: 'T2' }))).toBe(false)
    expect(Tap.compare(a, new Tap({ ...base, tapNumber: 2 }))).toBe(false)
    expect(Tap.compare(a, new Tap({ ...base, glassSize: 0.5 }))).toBe(false)
    expect(Tap.compare(a, new Tap({ ...base, location: 'cellar' }))).toBe(false)
    expect(Tap.compare(a, new Tap({ ...base, notes: '' }))).toBe(false)
    expect(Tap.compare(a, new Tap(base))).toBe(true)
  })
})
