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
import { Prediction } from '@/modules/classes'

describe('Prediction - Data Class', () => {
  describe('Constructor', () => {
    it('should create a Prediction with default values', () => {
      const p = new Prediction()
      expect(p.id).toBe(0)
      expect(p.batchId).toBe('')
      expect(p.deviceId).toBe('')
      expect(p.vesselId).toBe('')
      expect(p.predictionType).toBe('')
      expect(p.outcome).toBe('')
      expect(p.hoursLeft).toBeNull()
      expect(p.createdAt).toBe('')
    })

    it('should use provided values', () => {
      const p = new Prediction({
        id: 5,
        batchId: 'b1',
        deviceId: 'd1',
        vesselId: 'v1',
        predictionType: 'fermentation_progress',
        outcome: 'fermenting',
        hoursLeft: 24.5,
        createdAt: '2026-05-22T10:00:00'
      })
      expect(p.id).toBe(5)
      expect(p.batchId).toBe('b1')
      expect(p.deviceId).toBe('d1')
      expect(p.vesselId).toBe('v1')
      expect(p.predictionType).toBe('fermentation_progress')
      expect(p.outcome).toBe('fermenting')
      expect(p.hoursLeft).toBe(24.5)
      expect(p.createdAt).toBe('2026-05-22T10:00:00')
    })

    it('should default null hoursLeft to null', () => {
      const p = new Prediction({ hoursLeft: null })
      expect(p.hoursLeft).toBeNull()
    })
  })

  describe('fromJson', () => {
    it('should create a Prediction from JSON', () => {
      const json = {
        id: 10,
        batchId: 'b2',
        deviceId: 'd2',
        vesselId: 'v2',
        predictionType: 'battery_low',
        outcome: 'battery_ok',
        hoursLeft: 0.2,
        createdAt: '2026-05-22T12:00:00'
      }
      const p = Prediction.fromJson(json)
      expect(p.id).toBe(10)
      expect(p.batchId).toBe('b2')
      expect(p.deviceId).toBe('d2')
      expect(p.vesselId).toBe('v2')
      expect(p.predictionType).toBe('battery_low')
      expect(p.outcome).toBe('battery_ok')
      expect(p.hoursLeft).toBe(0.2)
      expect(p.createdAt).toBe('2026-05-22T12:00:00')
    })

    it('should default missing fields', () => {
      const p = Prediction.fromJson({})
      expect(p.id).toBe(0)
      expect(p.batchId).toBe('')
      expect(p.deviceId).toBe('')
      expect(p.vesselId).toBe('')
      expect(p.predictionType).toBe('')
      expect(p.outcome).toBe('')
      expect(p.hoursLeft).toBeNull()
      expect(p.createdAt).toBe('')
    })
  })

  describe('toJson', () => {
    it('should serialize mutable fields only', () => {
      const p = new Prediction({
        id: 1,
        batchId: 'b1',
        deviceId: 'd1',
        vesselId: 'v1',
        predictionType: 'fermentation_progress',
        outcome: 'fermenting',
        hoursLeft: 10.0,
        createdAt: '2026-05-22T10:00:00'
      })
      const json = p.toJson()
      expect(json.batchId).toBe('b1')
      expect(json.deviceId).toBe('d1')
      expect(json.vesselId).toBe('v1')
      expect(json.predictionType).toBe('fermentation_progress')
      expect(json.outcome).toBe('fermenting')
      expect(json.hoursLeft).toBe(10.0)
      expect(json.id).toBeUndefined()
      expect(json.createdAt).toBeUndefined()
    })
  })

  describe('compare', () => {
    it('should return true for identical predictions', () => {
      const a = new Prediction({
        id: 1,
        batchId: 'b1',
        deviceId: 'd1',
        vesselId: 'v1',
        predictionType: 'fermentation_progress',
        outcome: 'fermenting',
        hoursLeft: 5.0,
        createdAt: '2026-05-22T10:00:00'
      })
      const b = new Prediction({
        id: 1,
        batchId: 'b1',
        deviceId: 'd1',
        vesselId: 'v1',
        predictionType: 'fermentation_progress',
        outcome: 'fermenting',
        hoursLeft: 5.0,
        createdAt: '2026-05-22T10:00:00'
      })
      expect(Prediction.compare(a, b)).toBe(true)
    })

    it('should return false when hoursLeft differs', () => {
      const a = new Prediction({
        id: 1,
        batchId: 'b1',
        outcome: 'fermenting',
        hoursLeft: 5.0,
        createdAt: '2026-05-22T10:00:00'
      })
      const b = new Prediction({
        id: 1,
        batchId: 'b1',
        outcome: 'fermenting',
        hoursLeft: 3.0,
        createdAt: '2026-05-22T10:00:00'
      })
      expect(Prediction.compare(a, b)).toBe(false)
    })

    it('should return false when predictionType differs', () => {
      const a = new Prediction({
        id: 1,
        predictionType: 'fermentation_progress',
        outcome: 'fermenting'
      })
      const b = new Prediction({ id: 1, predictionType: 'battery_low', outcome: 'fermenting' })
      expect(Prediction.compare(a, b)).toBe(false)
    })
  })

  describe('setters', () => {
    it('should update all fields via setters', () => {
      const p = new Prediction()
      p.id = 7
      p.batchId = 'batch-x'
      p.deviceId = 'dev-x'
      p.vesselId = 'ves-x'
      p.predictionType = 'keg_empty'
      p.outcome = 'keg_ok'
      p.hoursLeft = 0.0
      p.createdAt = '2026-05-22T15:00:00'
      expect(p.id).toBe(7)
      expect(p.batchId).toBe('batch-x')
      expect(p.deviceId).toBe('dev-x')
      expect(p.vesselId).toBe('ves-x')
      expect(p.predictionType).toBe('keg_empty')
      expect(p.outcome).toBe('keg_ok')
      expect(p.hoursLeft).toBe(0.0)
      expect(p.createdAt).toBe('2026-05-22T15:00:00')
    })
  })
})
