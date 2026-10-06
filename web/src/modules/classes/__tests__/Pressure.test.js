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
import { Pressure } from '@/modules/classes'

describe('Pressure - Data Class', () => {
  describe('Constructor', () => {
    it('should create a Pressure with default values', () => {
      const p = new Pressure()
      expect(p.id).toBe(0)
      expect(p.pressure).toBe(0.0)
      expect(p.temperature).toBeNull()
      expect(p.battery).toBeNull()
      expect(p.rssi).toBeNull()
      expect(p.runTime).toBeNull()
      expect(p.excluded).toBe(false)
      expect(p.createdAt).toBe('')
      expect(p.batchId).toBe('')
      expect(p.deviceId).toBeNull()
    })

    it('should use provided values', () => {
      const p = new Pressure({
        id: 3,
        pressure: 12.5,
        temperature: 18.0,
        battery: 3.8,
        excluded: true
      })
      expect(p.id).toBe(3)
      expect(p.pressure).toBe(12.5)
      expect(p.temperature).toBe(18.0)
      expect(p.battery).toBe(3.8)
      expect(p.excluded).toBe(true)
    })

    it('should default null optional fields to null', () => {
      const p = new Pressure({ temperature: null, battery: null, rssi: null, runTime: null })
      expect(p.temperature).toBeNull()
      expect(p.battery).toBeNull()
      expect(p.rssi).toBeNull()
      expect(p.runTime).toBeNull()
    })
  })

  describe('fromJson', () => {
    it('should create a Pressure from JSON', () => {
      const json = {
        id: 7,
        pressure: 15.0,
        temperature: 20.0,
        battery: 3.9,
        rssi: -68.0,
        runTime: 1.5,
        excluded: false,
        createdAt: '2024-03-01T12:00:00',
        batchId: 'b2',
        deviceId: 'd2'
      }
      const p = Pressure.fromJson(json)
      expect(p.id).toBe(7)
      expect(p.pressure).toBe(15.0)
      expect(p.temperature).toBe(20.0)
      expect(p.battery).toBe(3.9)
      expect(p.rssi).toBe(-68.0)
      expect(p.runTime).toBe(1.5)
      expect(p.excluded).toBe(false)
      expect(p.createdAt).toBe('2024-03-01T12:00:00')
      expect(p.batchId).toBe('b2')
      expect(p.deviceId).toBe('d2')
    })

    it('should default missing optional fields to null', () => {
      const p = Pressure.fromJson({ id: 1, pressure: 10.0 })
      expect(p.temperature).toBeNull()
      expect(p.battery).toBeNull()
      expect(p.rssi).toBeNull()
      expect(p.runTime).toBeNull()
      expect(p.excluded).toBe(false)
      expect(p.batchId).toBe('')
      expect(p.deviceId).toBeNull()
    })
  })

  describe('toJson', () => {
    it('should serialize mutable fields', () => {
      const p = new Pressure({
        pressure: 11.0,
        temperature: 17.0,
        battery: 3.7,
        rssi: -75,
        runTime: 0.8,
        excluded: true
      })
      const json = p.toJson()
      expect(json.pressure).toBe(11.0)
      expect(json.temperature).toBe(17.0)
      expect(json.battery).toBe(3.7)
      expect(json.rssi).toBe(-75)
      expect(json.runTime).toBe(0.8)
      expect(json.excluded).toBe(true)
      expect(json.id).toBeUndefined()
    })
  })

  describe('setters', () => {
    it('should update all fields via setters', () => {
      const p = new Pressure()
      p.id = 42
      p.pressure = 20.0
      p.temperature = 15.0
      p.battery = 4.0
      p.rssi = -55
      p.runTime = 3.0
      p.excluded = true
      p.createdAt = '2024-07-01'
      p.batchId = 'batch2'
      p.deviceId = 'dev2'
      expect(p.pressure).toBe(20.0)
      expect(p.excluded).toBe(true)
      expect(p.batchId).toBe('batch2')
      expect(p.deviceId).toBe('dev2')
    })
  })
})
