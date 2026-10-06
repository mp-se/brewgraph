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
import { Batch } from '../Batch'
import { BatchNote } from '../BatchNote'
import { StorageVessel } from '../StorageVessel'
import { Device, DEVICE_TYPE_GRAVITYMON, DEVICE_TYPE_GRAVITYMON_GW, DEVICE_TYPE_PRESSUREMON, DEVICE_TYPE_ISPINDEL, DEVICE_TYPE_KEGMON, DEVICE_TYPE_CHAMBER_CONTROLLER } from '../Device'
import { Tap } from '../Tap'
import { Gravity } from '../Gravity'

// ─── Batch ────────────────────────────────────────────────────────────────────

describe('Batch', () => {
  describe('constructor defaults', () => {
    it('creates batch with empty defaults', () => {
      const b = new Batch()
      expect(b.id).toBe('')
      expect(b.name).toBe('')
      expect(b.acceptIngest).toBe(true)
      expect(b.abv).toBe(0)
      expect(b.og).toBeNull()
      expect(b.fg).toBeNull()
    })

    it('accepts provided values', () => {
      const b = new Batch({ id: 'abc', name: 'IPA', abv: 5.5 })
      expect(b.id).toBe('abc')
      expect(b.name).toBe('IPA')
      expect(b.abv).toBe(5.5)
    })
  })

  describe('setters', () => {
    it('sets name via setter', () => {
      const b = new Batch()
      b.name = 'Stout'
      expect(b.name).toBe('Stout')
    })

    it('sets acceptIngest via setter', () => {
      const b = new Batch({ acceptIngest: true })
      b.acceptIngest = false
      expect(b.acceptIngest).toBe(false)
    })
  })

  describe('readyDate computed', () => {
    it('returns null when packageDate is missing', () => {
      const b = new Batch({ conditioningDays: 14 })
      expect(b.readyDate).toBeNull()
    })

    it('returns null when conditioningDays is missing', () => {
      const b = new Batch({ packageDate: '2026-01-01' })
      expect(b.readyDate).toBeNull()
    })

    it('calculates readyDate correctly', () => {
      const b = new Batch({ packageDate: '2026-01-01', conditioningDays: 14 })
      expect(b.readyDate).toBe('2026-01-15')
    })

    it('handles month boundary', () => {
      const b = new Batch({ packageDate: '2026-01-25', conditioningDays: 10 })
      expect(b.readyDate).toBe('2026-02-04')
    })
  })

  describe('compare', () => {
    it('returns true for identical batches', () => {
      const b1 = new Batch({ name: 'IPA', abv: 5.5, og: 1.055 })
      const b2 = new Batch({ name: 'IPA', abv: 5.5, og: 1.055 })
      expect(Batch.compare(b1, b2)).toBe(true)
    })

    it('returns false when name differs', () => {
      const b1 = new Batch({ name: 'IPA' })
      const b2 = new Batch({ name: 'Stout' })
      expect(Batch.compare(b1, b2)).toBe(false)
    })

    it('returns false when abv differs', () => {
      const b1 = new Batch({ name: 'IPA', abv: 5.0 })
      const b2 = new Batch({ name: 'IPA', abv: 5.5 })
      expect(Batch.compare(b1, b2)).toBe(false)
    })

    it('returns false when acceptIngest differs', () => {
      const b1 = new Batch({ acceptIngest: true })
      const b2 = new Batch({ acceptIngest: false })
      expect(Batch.compare(b1, b2)).toBe(false)
    })
  })

  describe('fromJson', () => {
    it('maps all fields correctly', () => {
      const json = { id: 'x1', name: 'Weizen', abv: 4.8, og: 1.048, fg: 1.010, ebc: 8, ibu: 15, acceptIngest: false }
      const b = Batch.fromJson(json)
      expect(b.id).toBe('x1')
      expect(b.name).toBe('Weizen')
      expect(b.abv).toBe(4.8)
      expect(b.acceptIngest).toBe(false)
    })

    it('uses defaults for missing optional fields', () => {
      const b = Batch.fromJson({ id: 'x1', name: 'IPA' })
      expect(b.notes).toBe('')
      expect(b.fermentationSteps).toBe('')
    })
  })

  describe('fromDashboardJson', () => {
    it('maps dashboard fields', () => {
      const json = { id: 'd1', name: 'Porter', gravityCount: 10, pressureCount: 2 }
      const b = Batch.fromDashboardJson(json)
      expect(b.id).toBe('d1')
      expect(b.gravityCount).toBe(10)
      expect(b.pressureCount).toBe(2)
    })
  })

  describe('toJson', () => {
    it('includes name and fields', () => {
      const b = new Batch({ name: 'IPA', abv: 5.5, brewDate: '2026-01-01' })
      const json = b.toJson()
      expect(json.name).toBe('IPA')
      expect(json.abv).toBe(5.5)
      expect(json.brewDate).toBe('2026-01-01')
    })

    it('emits null for empty brewDate', () => {
      const b = new Batch({ name: 'IPA' })
      const json = b.toJson()
      expect(json.brewDate).toBeNull()
    })
  })
})

// ─── BatchNote ────────────────────────────────────────────────────────────────

describe('BatchNote', () => {
  it('creates with defaults', () => {
    const n = new BatchNote()
    expect(n.id).toBe('')
    expect(n.content).toBe('')
    expect(n.createdBy).toBeNull()
  })

  it('content setter works', () => {
    const n = new BatchNote({ content: 'hello' })
    n.content = 'updated'
    expect(n.content).toBe('updated')
  })

  it('fromJson maps camelCase fields', () => {
    const n = BatchNote.fromJson({
      id: 'n1', batchId: 'b1', content: 'Note text',
      createdBy: 'Magnus', createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z'
    })
    expect(n.id).toBe('n1')
    expect(n.batchId).toBe('b1')
    expect(n.content).toBe('Note text')
    expect(n.createdBy).toBe('Magnus')
  })

  it('toJson includes content', () => {
    const n = new BatchNote({ content: 'Test' })
    const json = n.toJson()
    expect(json.content).toBe('Test')
  })
})

// ─── StorageVessel ────────────────────────────────────────────────────────────

describe('StorageVessel', () => {
  describe('constructor defaults', () => {
    it('defaults vesselType to keg', () => {
      const v = new StorageVessel()
      expect(v.vesselType).toBe('keg')
    })

    it('defaults status to filled', () => {
      const v = new StorageVessel()
      expect(v.status).toBe('filled')
    })

    it('defaults volumeRemaining to 0', () => {
      const v = new StorageVessel()
      expect(v.volumeRemaining).toBe(0)
    })
  })

  describe('isOnTap', () => {
    it('returns false when tapId is null', () => {
      const v = new StorageVessel({ tapId: null })
      expect(v.isOnTap).toBe(false)
    })

    it('returns true when tapId is set', () => {
      const v = new StorageVessel({ tapId: 'tap-1' })
      expect(v.isOnTap).toBe(true)
    })
  })

  describe('isEmpty', () => {
    it('keg is empty when volumeRemaining is 0', () => {
      const v = new StorageVessel({ vesselType: 'keg', volumeRemaining: 0 })
      expect(v.isEmpty).toBe(true)
    })

    it('keg is not empty when volumeRemaining > 0', () => {
      const v = new StorageVessel({ vesselType: 'keg', volumeRemaining: 5 })
      expect(v.isEmpty).toBe(false)
    })

    it('bottle is empty when bottlesRemaining is 0', () => {
      const v = new StorageVessel({ vesselType: 'bottles', bottlesRemaining: 0 })
      expect(v.isEmpty).toBe(true)
    })

    it('bottle is not empty when bottlesRemaining > 0', () => {
      const v = new StorageVessel({ vesselType: 'bottles', bottlesRemaining: 5 })
      expect(v.isEmpty).toBe(false)
    })

    it('bottle treats null bottlesRemaining as 0', () => {
      const v = new StorageVessel({ vesselType: 'bottles', bottlesRemaining: null })
      expect(v.isEmpty).toBe(true)
    })
  })

  describe('compare', () => {
    it('returns true for identical vessels', () => {
      const v1 = new StorageVessel({ name: 'Keg A', vesselType: 'keg', totalVolume: 20 })
      const v2 = new StorageVessel({ name: 'Keg A', vesselType: 'keg', totalVolume: 20 })
      expect(StorageVessel.compare(v1, v2)).toBe(true)
    })

    it('returns false when name differs', () => {
      const v1 = new StorageVessel({ name: 'Keg A' })
      const v2 = new StorageVessel({ name: 'Keg B' })
      expect(StorageVessel.compare(v1, v2)).toBe(false)
    })

    it('returns false when status differs', () => {
      const v1 = new StorageVessel({ status: 'filled' })
      const v2 = new StorageVessel({ status: 'empty' })
      expect(StorageVessel.compare(v1, v2)).toBe(false)
    })
  })

  describe('fromJson / toJson roundtrip', () => {
    it('roundtrips all fields', () => {
      const json = {
        id: 'v1', batchId: 'b1', tapId: null, vesselNumber: null,
        vesselType: 'keg', name: 'Primary', fillDate: '2026-01-01',
        totalVolume: 20, volumeRemaining: 15, bottleVolume: null,
        bottleCount: null, bottlesRemaining: null, status: 'filled',
        location: 'Cellar', notes: '', pourCount: 0, batchName: null
      }
      const v = StorageVessel.fromJson(json)
      expect(v.name).toBe('Primary')
      expect(v.totalVolume).toBe(20)
      expect(v.location).toBe('Cellar')
      const out = v.toJson()
      expect(out.name).toBe('Primary')
      expect(out.totalVolume).toBe(20)
    })
  })
})

// ─── Device ───────────────────────────────────────────────────────────────────

describe('Device', () => {
  describe('constructor defaults', () => {
    it('creates with empty defaults', () => {
      const d = new Device()
      expect(d.id).toBe('')
      expect(d.deviceType).toBe('')
      expect(d.batchId).toBeNull()
    })
  })

  describe('device type helpers', () => {
    it('isGravitymon true for Gravitymon', () => {
      const d = new Device({ deviceType: DEVICE_TYPE_GRAVITYMON })
      expect(d.isGravitymon).toBe(true)
      expect(d.isPressuremon).toBe(false)
    })

    it('isPressuremon true for Pressuremon', () => {
      const d = new Device({ deviceType: DEVICE_TYPE_PRESSUREMON })
      expect(d.isPressuremon).toBe(true)
    })

    it('isIspindel true for iSpindel', () => {
      const d = new Device({ deviceType: DEVICE_TYPE_ISPINDEL })
      expect(d.isIspindel).toBe(true)
    })

    it('isKegmon true for KegMon', () => {
      const d = new Device({ deviceType: DEVICE_TYPE_KEGMON })
      expect(d.isKegmon).toBe(true)
    })

    it('isChamber true for Chamber Controller', () => {
      const d = new Device({ deviceType: DEVICE_TYPE_CHAMBER_CONTROLLER })
      expect(d.isChamber).toBe(true)
    })

    it('isGravitymonGw true for Gravitymon gateway', () => {
      const d = new Device({ deviceType: DEVICE_TYPE_GRAVITYMON_GW })
      expect(d.isGravitymonGw).toBe(true)
    })
  })

  describe('canIngest', () => {
    it('true for Gravitymon', () => {
      expect(new Device({ deviceType: DEVICE_TYPE_GRAVITYMON }).canIngest).toBe(true)
    })

    it('true for Pressuremon', () => {
      expect(new Device({ deviceType: DEVICE_TYPE_PRESSUREMON }).canIngest).toBe(true)
    })

    it('true for iSpindel', () => {
      expect(new Device({ deviceType: DEVICE_TYPE_ISPINDEL }).canIngest).toBe(true)
    })

    it('true for Chamber Controller', () => {
      expect(new Device({ deviceType: DEVICE_TYPE_CHAMBER_CONTROLLER }).canIngest).toBe(true)
    })
  })

  describe('canCollectLogs', () => {
    it('false for iSpindel', () => {
      expect(new Device({ deviceType: DEVICE_TYPE_ISPINDEL }).canCollectLogs).toBe(false)
    })

    it('true for Gravitymon', () => {
      expect(new Device({ deviceType: DEVICE_TYPE_GRAVITYMON }).canCollectLogs).toBe(true)
    })
  })

  describe('canFetchConfig', () => {
    it('true for Gravitymon with valid url and chipId', () => {
      const d = new Device({ deviceType: DEVICE_TYPE_GRAVITYMON, url: 'http://192.168.1.1/', chipId: 'a1b2c3' })
      expect(d.canFetchConfig).toBe(true)
    })

    it('false when url is too short', () => {
      const d = new Device({ deviceType: DEVICE_TYPE_GRAVITYMON, url: 'http://', chipId: 'a1b2c3' })
      expect(d.canFetchConfig).toBe(false)
    })

    it('false for iSpindel even with url and chipId', () => {
      const d = new Device({ deviceType: DEVICE_TYPE_ISPINDEL, url: 'http://192.168.1.1/', chipId: 'a1b2c3' })
      expect(d.canFetchConfig).toBe(false)
    })
  })

  describe('compare', () => {
    it('returns true for identical devices', () => {
      const d1 = new Device({ name: 'Sensor1', deviceType: DEVICE_TYPE_GRAVITYMON, url: 'http://x/' })
      const d2 = new Device({ name: 'Sensor1', deviceType: DEVICE_TYPE_GRAVITYMON, url: 'http://x/' })
      expect(Device.compare(d1, d2)).toBe(true)
    })

    it('returns false when deviceType differs', () => {
      const d1 = new Device({ deviceType: DEVICE_TYPE_GRAVITYMON })
      const d2 = new Device({ deviceType: DEVICE_TYPE_PRESSUREMON })
      expect(Device.compare(d1, d2)).toBe(false)
    })
  })

  describe('fromJson / toJson', () => {
    it('maps fields from JSON', () => {
      const d = Device.fromJson({ id: 'd1', name: 'Dev', deviceType: DEVICE_TYPE_GRAVITYMON, chipId: 'abc123', chipFamily: '', mdns: '', config: '', deviceColor: 'blue', url: '', description: '', collectLogs: false })
      expect(d.id).toBe('d1')
      expect(d.name).toBe('Dev')
      expect(d.isGravitymon).toBe(true)
      expect(d.deviceColor).toBe('blue')
    })

    it('toJson includes name and deviceType', () => {
      const d = new Device({ name: 'Dev', deviceType: DEVICE_TYPE_PRESSUREMON })
      const json = d.toJson()
      expect(json.name).toBe('Dev')
      expect(json.deviceType).toBe(DEVICE_TYPE_PRESSUREMON)
    })
  })
})

// ─── FermentationStep ─────────────────────────────────────────────────────────


// ─── Tap ──────────────────────────────────────────────────────────────────────

describe('Tap', () => {
  it('creates with defaults', () => {
    const t = new Tap()
    expect(t.id).toBe('')
    expect(t.tapNumber).toBeNull()
    expect(t.batchId).toBeNull()
  })

  it('compare returns true for identical taps', () => {
    const t1 = new Tap({ name: 'Tap 1', location: 'Bar' })
    const t2 = new Tap({ name: 'Tap 1', location: 'Bar' })
    expect(Tap.compare(t1, t2)).toBe(true)
  })

  it('compare returns false when name differs', () => {
    const t1 = new Tap({ name: 'Tap 1' })
    const t2 = new Tap({ name: 'Tap 2' })
    expect(Tap.compare(t1, t2)).toBe(false)
  })

  it('fromJson maps fields', () => {
    const t = Tap.fromJson({ id: 't1', name: 'Main Tap', tapNumber: 1, location: 'Kitchen', notes: '', vesselName: 'Primary Keg', volumeRemaining: 15, batchName: 'IPA', batchId: 'b1' })
    expect(t.id).toBe('t1')
    expect(t.name).toBe('Main Tap')
    expect(t.vesselName).toBe('Primary Keg')
    expect(t.batchName).toBe('IPA')
  })

  it('toJson includes name and notes', () => {
    const t = new Tap({ name: 'Bar Tap', notes: 'Cold side', location: 'Bar' })
    const json = t.toJson()
    expect(json.name).toBe('Bar Tap')
    expect(json.notes).toBe('Cold side')
  })
})

// ─── Gravity ──────────────────────────────────────────────────────────────────

describe('Gravity', () => {
  it('creates with defaults', () => {
    const g = new Gravity()
    expect(g.gravity).toBe(0)
    expect(g.excluded).toBe(false)
    expect(g.temperature).toBeNull()
  })

  it('fromJson maps fields', () => {
    const g = Gravity.fromJson({ id: 1, gravity: 1.055, temperature: 20, excluded: false, createdAt: '2026-01-01T00:00:00Z', batchId: 'b1' })
    expect(g.gravity).toBe(1.055)
    expect(g.temperature).toBe(20)
    expect(g.batchId).toBe('b1')
  })

  it('toJson includes gravity and excluded', () => {
    const g = new Gravity({ gravity: 1.010, excluded: true })
    const json = g.toJson()
    expect(json.gravity).toBe(1.010)
    expect(json.excluded).toBe(true)
  })
})
