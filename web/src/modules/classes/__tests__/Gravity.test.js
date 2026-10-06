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
import { Gravity } from '@/modules/classes'

describe('Gravity - Data Class', () => {
  describe('Constructor', () => {
    it('should create a Gravity with default values', () => {
      const g = new Gravity()
      expect(g.id).toBe(0)
      expect(g.gravity).toBe(0.0)
      expect(g.temperature).toBeNull()
      expect(g.velocity).toBeNull()
      expect(g.angle).toBeNull()
      expect(g.battery).toBeNull()
      expect(g.rssi).toBeNull()
      expect(g.runTime).toBeNull()
      expect(g.excluded).toBe(false)
      expect(g.createdAt).toBe('')
      expect(g.batchId).toBe('')
      expect(g.deviceId).toBeNull()
    })

    it('should use provided values', () => {
      const g = new Gravity({
        id: 5,
        gravity: 1.055,
        temperature: 20.0,
        angle: 34.5,
        battery: 3.8,
        excluded: true
      })
      expect(g.id).toBe(5)
      expect(g.gravity).toBe(1.055)
      expect(g.temperature).toBe(20.0)
      expect(g.angle).toBe(34.5)
      expect(g.battery).toBe(3.8)
      expect(g.excluded).toBe(true)
    })

    it('should default null optional fields to null', () => {
      const g = new Gravity({ temperature: null, velocity: null, angle: null })
      expect(g.temperature).toBeNull()
      expect(g.velocity).toBeNull()
      expect(g.angle).toBeNull()
    })
  })

  describe('fromJson', () => {
    it('should create a Gravity from JSON', () => {
      const json = {
        id: 10,
        gravity: 1.048,
        temperature: 19.5,
        velocity: 0.02,
        angle: 30.1,
        battery: 3.9,
        rssi: -72.0,
        runTime: 1.2,
        excluded: false,
        createdAt: '2024-01-01T10:00:00',
        batchId: 'b1',
        deviceId: 'd1'
      }
      const g = Gravity.fromJson(json)
      expect(g.id).toBe(10)
      expect(g.gravity).toBe(1.048)
      expect(g.temperature).toBe(19.5)
      expect(g.velocity).toBe(0.02)
      expect(g.angle).toBe(30.1)
      expect(g.battery).toBe(3.9)
      expect(g.rssi).toBe(-72.0)
      expect(g.runTime).toBe(1.2)
      expect(g.excluded).toBe(false)
      expect(g.batchId).toBe('b1')
      expect(g.deviceId).toBe('d1')
    })

    it('should default missing optional fields to null', () => {
      const g = Gravity.fromJson({ id: 1, gravity: 1.05 })
      expect(g.temperature).toBeNull()
      expect(g.velocity).toBeNull()
      expect(g.angle).toBeNull()
      expect(g.battery).toBeNull()
      expect(g.rssi).toBeNull()
      expect(g.runTime).toBeNull()
      expect(g.excluded).toBe(false)
      expect(g.batchId).toBe('')
      expect(g.deviceId).toBeNull()
    })
  })

  describe('toJson', () => {
    it('should serialize mutable fields', () => {
      const g = new Gravity({
        gravity: 1.04,
        temperature: 18.0,
        angle: 32.0,
        battery: 3.7,
        rssi: -80,
        runTime: 0.9,
        excluded: true
      })
      const json = g.toJson()
      expect(json.gravity).toBe(1.04)
      expect(json.temperature).toBe(18.0)
      expect(json.angle).toBe(32.0)
      expect(json.battery).toBe(3.7)
      expect(json.rssi).toBe(-80)
      expect(json.runTime).toBe(0.9)
      expect(json.excluded).toBe(true)
      expect(json.id).toBeUndefined()
    })
  })

  describe('setters', () => {
    it('should update all fields via setters', () => {
      const g = new Gravity()
      g.id = 99
      g.gravity = 1.01
      g.temperature = 20.0
      g.velocity = 0.05
      g.angle = 45.0
      g.battery = 4.0
      g.rssi = -60
      g.runTime = 2.0
      g.excluded = true
      g.createdAt = '2024-06-01'
      g.batchId = 'batch1'
      g.deviceId = 'dev1'
      expect(g.gravity).toBe(1.01)
      expect(g.excluded).toBe(true)
      expect(g.batchId).toBe('batch1')
    })
  })
})
