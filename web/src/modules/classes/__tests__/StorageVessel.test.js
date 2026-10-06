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
import { StorageVessel } from '@/modules/classes'

describe('StorageVessel - Data Class', () => {
  describe('Constructor', () => {
    it('should create a StorageVessel with default values', () => {
      const v = new StorageVessel()
      expect(v.id).toBe('')
      expect(v.batchId).toBe('')
      expect(v.tapId).toBeNull()
      expect(v.vesselNumber).toBeNull()
      expect(v.vesselType).toBe('keg')
      expect(v.name).toBe('')
      expect(v.totalVolume).toBe(0.0)
      expect(v.volumeRemaining).toBe(0.0)
      expect(v.status).toBe('filled')
      expect(v.location).toBe('')
      expect(v.notes).toBe('')
      expect(v.bottleVolume).toBeNull()
      expect(v.bottleCount).toBeNull()
      expect(v.bottlesRemaining).toBeNull()
    })

    it('should create a StorageVessel with provided values', () => {
      const v = new StorageVessel({
        id: 'v1',
        batchId: 'b1',
        vesselType: 'bottles',
        name: 'Keg A',
        totalVolume: 19.0,
        volumeRemaining: 15.5,
        status: 'serving',
        bottleVolume: 0.33,
        bottleCount: 24,
        bottlesRemaining: 20
      })
      expect(v.id).toBe('v1')
      expect(v.batchId).toBe('b1')
      expect(v.vesselType).toBe('bottles')
      expect(v.totalVolume).toBe(19.0)
      expect(v.volumeRemaining).toBe(15.5)
      expect(v.status).toBe('serving')
      expect(v.bottleVolume).toBe(0.33)
      expect(v.bottleCount).toBe(24)
      expect(v.bottlesRemaining).toBe(20)
    })

    it('should default null location to empty string', () => {
      const v = new StorageVessel({ location: null })
      expect(v.location).toBe('')
    })
  })

  describe('fromJson', () => {
    it('should create a StorageVessel from JSON', () => {
      const json = {
        id: 'v1',
        batchId: 'b1',
        tapId: 't1',
        vesselType: 'keg',
        name: 'Primary',
        fillDate: '2024-01-01',
        totalVolume: 19.0,
        volumeRemaining: 18.0,
        status: 'filled',
        location: 'cellar',
        notes: 'dry hop',
        createdAt: '2024-01-01T00:00:00',
        updatedAt: '2024-01-02T00:00:00'
      }
      const v = StorageVessel.fromJson(json)
      expect(v.id).toBe('v1')
      expect(v.tapId).toBe('t1')
      expect(v.name).toBe('Primary')
      expect(v.fillDate).toBe('2024-01-01')
      expect(v.location).toBe('cellar')
      expect(v.notes).toBe('dry hop')
    })

    it('should round-trip vesselNumber via fromJson', () => {
      const v = StorageVessel.fromJson({
        id: 'v1',
        batchId: 'b1',
        vesselType: 'keg',
        name: 'X',
        fillDate: '',
        totalVolume: 0,
        volumeRemaining: 0,
        status: 'filled',
        vesselNumber: 7
      })
      expect(v.vesselNumber).toBe(7)
    })

    it('should default missing optional fields', () => {
      const v = StorageVessel.fromJson({
        id: 'v1',
        batchId: 'b1',
        vesselType: 'keg',
        name: 'X',
        fillDate: '',
        totalVolume: 0,
        volumeRemaining: 0,
        status: 'filled'
      })
      expect(v.tapId).toBeNull()
      expect(v.vesselNumber).toBeNull()
      expect(v.bottleVolume).toBeNull()
      expect(v.location).toBe('')
      expect(v.notes).toBe('')
    })
  })

  describe('toJson', () => {
    it('should serialize all mutable fields', () => {
      const v = new StorageVessel({
        batchId: 'b1',
        vesselType: 'keg',
        name: 'K1',
        totalVolume: 19.0,
        volumeRemaining: 10.0,
        status: 'serving'
      })
      const json = v.toJson()
      expect(json.batchId).toBe('b1')
      expect(json.vesselType).toBe('keg')
      expect(json.name).toBe('K1')
      expect(json.totalVolume).toBe(19.0)
      expect(json.volumeRemaining).toBe(10.0)
      expect(json.status).toBe('serving')
      expect(json.vesselNumber).toBeNull()
      expect(json.id).toBeUndefined()
    })

    it('should include vesselNumber in serialized output', () => {
      const v = new StorageVessel({
        batchId: 'b1',
        vesselType: 'keg',
        name: 'K1',
        totalVolume: 19.0,
        volumeRemaining: 10.0,
        status: 'serving',
        vesselNumber: 5
      })
      expect(v.toJson().vesselNumber).toBe(5)
    })
  })

  describe('setters', () => {
    it('should update fields via setters', () => {
      const v = new StorageVessel()
      v.name = 'Updated'
      v.volumeRemaining = 5.0
      v.status = 'serving'
      expect(v.name).toBe('Updated')
      expect(v.volumeRemaining).toBe(5.0)
      expect(v.status).toBe('serving')
    })
  })

  describe('compare', () => {
    it('returns true when vessels are identical', () => {
      const a = new StorageVessel({
        name: 'K1',
        vesselType: 'keg',
        vesselNumber: 2,
        totalVolume: 19,
        volumeRemaining: 19,
        status: 'filled'
      })
      const b = new StorageVessel({
        name: 'K1',
        vesselType: 'keg',
        vesselNumber: 2,
        totalVolume: 19,
        volumeRemaining: 19,
        status: 'filled'
      })
      expect(StorageVessel.compare(a, b)).toBe(true)
    })

    it('treats an unassigned batch id as unchanged when JSON normalizes it to null', () => {
      const newVessel = new StorageVessel({ batchId: '', name: 'K1' })
      const savedBaseline = StorageVessel.fromJson(newVessel.toJson())

      expect(StorageVessel.compare(newVessel, savedBaseline)).toBe(true)
    })

    it('returns false when vesselNumber differs', () => {
      const a = new StorageVessel({
        name: 'K1',
        vesselType: 'keg',
        vesselNumber: 1,
        totalVolume: 19,
        volumeRemaining: 19,
        status: 'filled'
      })
      const b = new StorageVessel({
        name: 'K1',
        vesselType: 'keg',
        vesselNumber: 2,
        totalVolume: 19,
        volumeRemaining: 19,
        status: 'filled'
      })
      expect(StorageVessel.compare(a, b)).toBe(false)
    })
  })

  describe('computed properties', () => {
    it('isOnTap is true when tapId is set', () => {
      const v = new StorageVessel({ tapId: 'tap-1' })
      expect(v.isOnTap).toBe(true)
    })

    it('isOnTap is false when tapId is null', () => {
      const v = new StorageVessel({ tapId: null })
      expect(v.isOnTap).toBe(false)
    })

    it('isEmpty is true for keg with volumeRemaining <= 0', () => {
      const v = new StorageVessel({ vesselType: 'keg', volumeRemaining: 0 })
      expect(v.isEmpty).toBe(true)
    })

    it('isEmpty is false for keg with volume remaining', () => {
      const v = new StorageVessel({ vesselType: 'keg', volumeRemaining: 5.0 })
      expect(v.isEmpty).toBe(false)
    })

    it('isEmpty is true for bottle vessel with bottlesRemaining <= 0', () => {
      const v = new StorageVessel({ vesselType: 'bottles', bottlesRemaining: 0 })
      expect(v.isEmpty).toBe(true)
    })

    it('isEmpty is false for bottle vessel with bottles remaining', () => {
      const v = new StorageVessel({ vesselType: 'bottles', bottlesRemaining: 5 })
      expect(v.isEmpty).toBe(false)
    })
  })
})

describe('StorageVessel - additional coverage', () => {
  it('exercises all remaining getters and setters', () => {
    const v = new StorageVessel({
      id: 'v1',
      batchId: 'b1',
      tapId: 't1',
      vesselNumber: 3,
      vesselType: 'bottles',
      name: 'K',
      fillDate: '2024-01-01',
      totalVolume: 19,
      volumeRemaining: 10,
      bottleVolume: 0.33,
      bottleCount: 24,
      bottlesRemaining: 20,
      status: 'serving',
      location: 'cellar',
      notes: 'dry hop',
      createdAt: '2024-01-01T00:00:00',
      updatedAt: '2024-01-02T00:00:00',
      pourCount: 5,
      batchName: 'Pilsner'
    })
    expect(v.id).toBe('v1')
    expect(v.batchId).toBe('b1')
    expect(v.tapId).toBe('t1')
    expect(v.createdAt).toBe('2024-01-01T00:00:00')
    expect(v.updatedAt).toBe('2024-01-02T00:00:00')
    expect(v.pourCount).toBe(5)
    expect(v.batchName).toBe('Pilsner')

    v.id = 'v2'
    v.batchId = 'b2'
    v.tapId = null
    v.vesselNumber = 7
    v.vesselType = 'keg'
    v.fillDate = '2024-06-01'
    v.totalVolume = 30
    v.volumeRemaining = 25
    v.bottleVolume = null
    v.bottleCount = null
    v.bottlesRemaining = null
    v.createdAt = '2024-06-01T00:00:00'
    v.updatedAt = '2024-06-02T00:00:00'
    v.pourCount = 2
    v.batchName = 'Lager'
    v.location = 'fridge'
    v.notes = 'cold'

    expect(v.id).toBe('v2')
    expect(v.tapId).toBeNull()
    expect(v.pourCount).toBe(2)
    expect(v.batchName).toBe('Lager')
    expect(v.vesselType).toBe('keg')
    expect(v.fillDate).toBe('2024-06-01')
    expect(v.totalVolume).toBe(30)
    expect(v.volumeRemaining).toBe(25)
  })

  it('fromJson populates pourCount, batchName, timestamps', () => {
    const v = StorageVessel.fromJson({
      id: 'v1',
      batchId: 'b1',
      vesselType: 'keg',
      name: 'X',
      fillDate: '',
      totalVolume: 0,
      volumeRemaining: 0,
      status: 'filled',
      createdAt: '2024-01-01',
      updatedAt: '2024-01-02',
      pourCount: 3,
      batchName: 'IPA'
    })
    expect(v.pourCount).toBe(3)
    expect(v.batchName).toBe('IPA')
    expect(v.createdAt).toBe('2024-01-01')
    expect(v.updatedAt).toBe('2024-01-02')
  })

  it('defaults null batchName in constructor', () => {
    const v = new StorageVessel({ batchName: null })
    expect(v.batchName).toBeNull()
  })

  it('compare returns false for each differing field', () => {
    const base = {
      name: 'K',
      vesselType: 'keg',
      totalVolume: 19,
      volumeRemaining: 19,
      status: 'filled',
      location: '',
      notes: '',
      bottleVolume: null,
      bottleCount: null,
      bottlesRemaining: null,
      vesselNumber: 1,
      fillDate: '2024-01-01'
    }
    const a = new StorageVessel(base)
    expect(StorageVessel.compare(a, new StorageVessel({ ...base, totalVolume: 20 }))).toBe(false)
    expect(StorageVessel.compare(a, new StorageVessel({ ...base, volumeRemaining: 10 }))).toBe(
      false
    )
    expect(StorageVessel.compare(a, new StorageVessel({ ...base, status: 'serving' }))).toBe(false)
    expect(StorageVessel.compare(a, new StorageVessel({ ...base, location: 'cellar' }))).toBe(false)
    expect(StorageVessel.compare(a, new StorageVessel({ ...base, notes: 'dry hop' }))).toBe(false)
    expect(StorageVessel.compare(a, new StorageVessel({ ...base, bottleVolume: 0.33 }))).toBe(false)
    expect(StorageVessel.compare(a, new StorageVessel({ ...base, bottleCount: 12 }))).toBe(false)
    expect(StorageVessel.compare(a, new StorageVessel({ ...base, bottlesRemaining: 6 }))).toBe(
      false
    )
    expect(StorageVessel.compare(a, new StorageVessel({ ...base, fillDate: '2025-01-01' }))).toBe(
      false
    )
    expect(StorageVessel.compare(a, new StorageVessel({ ...base, vesselType: 'bottles' }))).toBe(
      false
    )
    expect(StorageVessel.compare(a, new StorageVessel({ ...base, name: 'Other' }))).toBe(false)
    expect(StorageVessel.compare(a, new StorageVessel({ ...base, batchId: 'batch-2' }))).toBe(false)
    expect(StorageVessel.compare(a, new StorageVessel({ ...base, tapId: 'tap-1' }))).toBe(false)
    expect(StorageVessel.compare(a, new StorageVessel({ ...base, conditioningDays: 14 }))).toBe(false)
  })
})

describe('StorageVessel - conditioningDays', () => {
  it('defaults to null in constructor', () => {
    const v = new StorageVessel()
    expect(v.conditioningDays).toBeNull()
  })

  it('accepts a value in constructor', () => {
    const v = new StorageVessel({ conditioningDays: 21 })
    expect(v.conditioningDays).toBe(21)
  })

  it('getter returns the set value', () => {
    const v = new StorageVessel({ conditioningDays: 14 })
    expect(v.conditioningDays).toBe(14)
  })

  it('setter updates the value', () => {
    const v = new StorageVessel()
    v.conditioningDays = 30
    expect(v.conditioningDays).toBe(30)
  })

  it('setter can clear to null', () => {
    const v = new StorageVessel({ conditioningDays: 14 })
    v.conditioningDays = null
    expect(v.conditioningDays).toBeNull()
  })

  it('fromJson maps conditioningDays from response', () => {
    const v = StorageVessel.fromJson({
      id: 'v1',
      batchId: 'b1',
      vesselType: 'keg',
      name: 'X',
      fillDate: '2024-01-01',
      conditioningDays: 28,
      totalVolume: 19,
      volumeRemaining: 19,
      status: 'filled'
    })
    expect(v.conditioningDays).toBe(28)
  })

  it('fromJson defaults missing conditioningDays to null', () => {
    const v = StorageVessel.fromJson({
      id: 'v1',
      batchId: 'b1',
      vesselType: 'keg',
      name: 'X',
      fillDate: '',
      totalVolume: 0,
      volumeRemaining: 0,
      status: 'filled'
    })
    expect(v.conditioningDays).toBeNull()
  })

  it('toJson includes conditioningDays', () => {
    const v = new StorageVessel({ conditioningDays: 14 })
    expect(v.toJson().conditioningDays).toBe(14)
  })

  it('toJson includes null conditioningDays when not set', () => {
    const v = new StorageVessel()
    expect(v.toJson().conditioningDays).toBeNull()
  })

  it('sends a null batch for a vessel that holds none (an empty vessel)', () => {
    expect(new StorageVessel({ name: 'Keg 1' }).toJson().batchId).toBeNull()
    expect(new StorageVessel({ name: 'Keg 1', batchId: 'b1' }).toJson().batchId).toBe('b1')
  })
})
