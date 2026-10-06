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
import { Batch } from '@/modules/classes'

describe('Batch - Data Class', () => {
  describe('Constructor', () => {
    it('should create a Batch with default values', () => {
      const batch = new Batch()
      expect(batch.id).toBe('')
      expect(batch.name).toBe('')
      expect(batch.description).toBe('')
      expect(batch.acceptIngest).toBe(true)
      expect(batch.gravityDeviceId).toBeNull()
      expect(batch.pressureDeviceId).toBeNull()
      expect(batch.chamberDeviceId).toBeNull()
      expect(batch.brewDate).toBe('')
      expect(batch.style).toBe('')
      expect(batch.brewer).toBe('')
      expect(batch.abv).toBe(0)
      expect(batch.ebc).toBeNull()
      expect(batch.ibu).toBeNull()
      expect(batch.fg).toBeNull()
      expect(batch.og).toBeNull()
      expect(batch.carbonationVolumes).toBeNull()
      expect(batch.brewfatherBatchId).toBe('')
      expect(batch.notes).toBe('')
      expect(batch.gravityCount).toBe(0)
      expect(batch.pressureCount).toBe(0)
      expect(batch.createdAt).toBe('')
      expect(batch.updatedAt).toBe('')
    })

    it('should create a Batch with provided values', () => {
      const batch = new Batch({
        id: 'abc-123',
        name: 'Test Batch',
        acceptIngest: false,
        og: 1.055,
        fg: 1.012,
        abv: 5.6,
        ibu: 30,
        ebc: 15,
        brewer: 'Magnus',
        style: 'IPA',
        brewDate: '2024-01-01',
        gravityDeviceId: 'd1',
        pressureDeviceId: 'd2',
        chamberDeviceId: 'd3',
        carbonationVolumes: 2.5,
        brewfatherBatchId: 'bf1',
        notes: 'test notes'
      })
      expect(batch.id).toBe('abc-123')
      expect(batch.name).toBe('Test Batch')
      expect(batch.acceptIngest).toBe(false)
      expect(batch.og).toBe(1.055)
      expect(batch.fg).toBe(1.012)
      expect(batch.abv).toBe(5.6)
      expect(batch.gravityDeviceId).toBe('d1')
      expect(batch.pressureDeviceId).toBe('d2')
      expect(batch.chamberDeviceId).toBe('d3')
      expect(batch.carbonationVolumes).toBe(2.5)
      expect(batch.brewfatherBatchId).toBe('bf1')
    })

    it('should default null notes to empty string', () => {
      const batch = new Batch({ notes: null })
      expect(batch.notes).toBe('')
    })

    it('should default null gravityCount/pressureCount to 0', () => {
      const batch = new Batch({ gravityCount: null, pressureCount: null })
      expect(batch.gravityCount).toBe(0)
      expect(batch.pressureCount).toBe(0)
    })
  })

  describe('fromJson', () => {
    it('preserves nullable recipe values instead of converting them to zero', () => {
      const batch = Batch.fromJson({ name: 'Unmeasured' })

      expect(batch.og).toBeNull()
      expect(batch.fg).toBeNull()
      expect(batch.ebc).toBeNull()
      expect(batch.ibu).toBeNull()
      expect(batch.toJson()).toMatchObject({ og: null, fg: null, ebc: null, ibu: null })
    })

    it('should create a Batch from full JSON', () => {
      const json = {
        id: 'abc-123',
        name: 'JSON Batch',
        description: 'desc',
        og: 1.06,
        fg: 1.01,
        abv: 6.5,
        ibu: 40,
        ebc: 18,
        brewer: 'Alice',
        style: 'Stout',
        brewDate: '2024-02-01',
        carbonationVolumes: 2.2,
        brewfatherBatchId: 'bfx',
        notes: 'notes here',
        gravityCount: 10,
        pressureCount: 5,
        createdAt: '2024-01-01T00:00:00',
        updatedAt: '2024-01-02T00:00:00'
      }
      const batch = Batch.fromJson(json)
      expect(batch.id).toBe('abc-123')
      expect(batch.name).toBe('JSON Batch')
      expect(batch.og).toBe(1.06)
      expect(batch.fg).toBe(1.01)
      expect(batch.gravityDeviceId).toBeNull()
      expect(batch.carbonationVolumes).toBe(2.2)
      expect(batch.gravityCount).toBe(10)
      expect(batch.pressureCount).toBe(5)
      expect(batch.createdAt).toBe('2024-01-01T00:00:00')
    })

    it('should default missing optional fields', () => {
      const batch = Batch.fromJson({ id: 'x', name: 'Minimal' })
      expect(batch.gravityDeviceId).toBeNull()
      expect(batch.brewDate).toBe('')
      expect(batch.abv).toBe(0)
      expect(batch.carbonationVolumes).toBeNull()
      expect(batch.notes).toBe('')
    })
  })

  describe('fromDashboardJson', () => {
    it('should create a Batch from dashboard projection', () => {
      const bd = {
        id: 'd1',
        name: 'Dashboard Batch',
        acceptIngest: true,
        gravityCount: 3,
        pressureCount: 1
      }
      const batch = Batch.fromDashboardJson(bd)
      expect(batch.id).toBe('d1')
      expect(batch.name).toBe('Dashboard Batch')
      expect(batch.acceptIngest).toBe(true)
      expect(batch.gravityCount).toBe(3)
      expect(batch.pressureCount).toBe(1)
    })
  })

  describe('toJson', () => {
    it('should serialize mutable fields without id', () => {
      const batch = new Batch({
        id: 'skip-me',
        name: 'Batch',
        description: 'desc',
        acceptIngest: false,
        og: 1.05,
        fg: 1.01,
        brewDate: '2024-03-01',
        notes: 'note'
      })
      const json = batch.toJson()
      expect(json.name).toBe('Batch')
      expect(json.acceptIngest).toBe(false)
      expect(json.og).toBe(1.05)
      expect(json.brewDate).toBe('2024-03-01')
      expect(json.notes).toBe('note')
      expect(json.id).toBeUndefined()
    })

    it('should convert empty brewDate to null', () => {
      const batch = new Batch({ brewDate: '' })
      const json = batch.toJson()
      expect(json.brewDate).toBeNull()
    })
  })

  describe('compare', () => {
    it('should return true for equal batches', () => {
      const b1 = new Batch({ name: 'A', og: 1.05 })
      const b2 = new Batch({ name: 'A', og: 1.05 })
      expect(Batch.compare(b1, b2)).toBe(true)
    })

    it('should return false for different batches', () => {
      const b1 = new Batch({ name: 'A' })
      const b2 = new Batch({ name: 'B' })
      expect(Batch.compare(b1, b2)).toBe(false)
    })

    it.each([
      ['gravityDeviceId', { gravityDeviceId: 'gravity-1' }],
      ['pressureDeviceId', { pressureDeviceId: 'pressure-1' }],
      ['chamberDeviceId', { chamberDeviceId: 'chamber-1' }]
    ])('detects a changed %s assignment', (_field, changed) => {
      const saved = new Batch()
      expect(Batch.compare(saved, new Batch(changed))).toBe(false)
    })
  })

  describe('setters', () => {
    it('reads and writes all dashboard and metadata accessors', () => {
      const reading = { value: 1 }
      const batch = new Batch({ temperatureCount: 1 })

      batch.description = 'description'
      batch.acceptIngest = false
      batch.tempDeviceId = 'temp-1'
      batch.style = 'stout'
      batch.brewer = 'Brewer'
      batch.abv = 5
      batch.ebc = 20
      batch.ibu = 40
      batch.volume = 19
      batch.packageDate = '2026-01-01'
      batch.conditioningDays = 14
      batch.brewfatherBatchId = 'bf-1'
      batch.maxGravityReading = reading
      batch.minGravityReading = reading
      batch.maxPressureReading = reading
      batch.minPressureReading = reading
      batch.fermentationChamber = 'chamber'
      batch.fermentationSteps = '[]'
      batch.yeast = 'yeast'
      batch.yeastProductId = 'yeast-1'
      batch.createdAt = 'created'
      batch.updatedAt = 'updated'
      batch.status = 'packaged'

      expect(batch).toMatchObject({
        description: 'description',
        acceptIngest: false,
        tempDeviceId: 'temp-1',
        style: 'stout',
        brewer: 'Brewer',
        abv: 5,
        ebc: 20,
        ibu: 40,
        volume: 19,
        packageDate: '2026-01-01',
        conditioningDays: 14,
        brewfatherBatchId: 'bf-1',
        temperatureCount: 1,
        maxGravityReading: reading,
        minGravityReading: reading,
        maxPressureReading: reading,
        minPressureReading: reading,
        fermentationChamber: 'chamber',
        fermentationSteps: '[]',
        yeast: 'yeast',
        yeastProductId: 'yeast-1',
        createdAt: 'created',
        updatedAt: 'updated',
        status: 'packaged'
      })
    })

    it('should update all fields via setters', () => {
      const batch = new Batch()
      batch.id = 'new-id'
      batch.name = 'Updated'
      batch.brewDate = '2024-06-01'
      batch.og = 1.06
      batch.fg = 1.008
      batch.gravityDeviceId = 'gd1'
      batch.pressureDeviceId = 'pd1'
      batch.chamberDeviceId = 'kd1'
      batch.gravityCount = 15
      batch.pressureCount = 8
      batch.carbonationVolumes = 2.8
      batch.notes = 'updated notes'
      expect(batch.name).toBe('Updated')
      expect(batch.brewDate).toBe('2024-06-01')
      expect(batch.og).toBe(1.06)
      expect(batch.gravityCount).toBe(15)
    })
  })
})
