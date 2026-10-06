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

import { describe, it, expect, vi } from 'vitest'
import {
  LowPassFilter,
  mapGravityData,
  mapBatteryData,
  mapTemperatureData,
  mapAlcoholData,
  mapChamberData,
  mapGravityVelocityData,
  applyLowPass
} from '@/modules/gravityChartData'

// Mock dependencies
vi.mock('@/modules/pinia', () => ({
  config: {
    isGravitySG: true,
    isTempC: true
  }
}))

vi.mock('@/modules/utils', () => ({
  gravityToPlato: (sg) => (sg - 1) * 1000 / 4,
  tempToF: (celsius) => celsius * 9/5 + 32,
  abv: (og, fg) => (og - fg) * 131.25
}))

describe('gravityChartData', () => {
  describe('LowPassFilter', () => {
    it('should initialize with window size', () => {
      const filter = new LowPassFilter(5)

      expect(filter.windowSize).toBe(5)
      expect(filter.data).toEqual([])
    })

    it('should return average of all values when window not full', () => {
      const filter = new LowPassFilter(5)

      const result1 = filter.process(10)
      expect(result1).toBe(10)

      const result2 = filter.process(20)
      expect(result2).toBe(15)

      const result3 = filter.process(30)
      expect(result3).toBe(20)
    })

    it('should maintain sliding window size', () => {
      const filter = new LowPassFilter(3)

      filter.process(10)
      filter.process(20)
      filter.process(30)
      expect(filter.data).toHaveLength(3)

      filter.process(40)
      expect(filter.data).toHaveLength(3)
      expect(filter.data).toEqual([20, 30, 40])
    })

    it('should calculate correct moving average', () => {
      const filter = new LowPassFilter(3)

      filter.process(10)
      filter.process(20)
      const result = filter.process(30)

      expect(result).toBe(20) // (10 + 20 + 30) / 3
    })
  })

  describe('mapGravityData', () => {
    it('should map gravity list to chart points with SG', async () => {
      const { config } = await import('@/modules/pinia')
      config.isGravitySG = true

      const gList = [
        { created: '2024-01-01T10:00:00Z', gravity: 1.050 },
        { created: '2024-01-01T11:00:00Z', gravity: 1.045 }
      ]

      const result = mapGravityData(gList)

      expect(result).toHaveLength(2)
      expect(result[0].x).toBe('2024-01-01T10:00:00Z')
      expect(result[0].y).toBe(1.05)
      expect(result[1].y).toBe(1.045)
    })

    it('should convert gravity to Plato when isGravitySG is false', async () => {
      const { config } = await import('@/modules/pinia')
      config.isGravitySG = false

      const gList = [
        { created: '2024-01-01T10:00:00Z', gravity: 1.050 }
      ]

      const result = mapGravityData(gList)

      expect(result[0].y).toBeCloseTo(12.5, 1) // (1.050 - 1) * 1000 / 4
    })

    it('should handle empty list', () => {
      const result = mapGravityData([])

      expect(result).toEqual([])
    })

    it('should handle single point', async () => {
      const { config } = await import('@/modules/pinia')
      config.isGravitySG = true

      const gList = [{ created: '2024-01-01T10:00:00Z', gravity: 1.050 }]

      const result = mapGravityData(gList)

      expect(result).toHaveLength(1)
      expect(result[0].y).toBe(1.05)
    })
  })

  describe('mapBatteryData', () => {
    it('should map battery data to chart points', () => {
      const gList = [
        { created: '2024-01-01T10:00:00Z', battery: 4.15 },
        { created: '2024-01-01T11:00:00Z', battery: 4.10 }
      ]

      const result = mapBatteryData(gList)

      expect(result).toHaveLength(2)
      expect(result[0].x).toBe('2024-01-01T10:00:00Z')
      expect(result[0].y).toBe(4.15)
      expect(result[1].y).toBe(4.1)
    })

    it('should round to 2 decimal places', () => {
      const gList = [
        { created: '2024-01-01T10:00:00Z', battery: 4.123456 }
      ]

      const result = mapBatteryData(gList)

      expect(result[0].y).toBe(4.12)
    })

    it('should handle empty list', () => {
      const result = mapBatteryData([])

      expect(result).toEqual([])
    })
  })

  describe('mapTemperatureData', () => {
    it('should map temperature data in Celsius', async () => {
      const { config } = await import('@/modules/pinia')
      config.isTempC = true

      const gList = [
        { created: '2024-01-01T10:00:00Z', temperature: 18.5 },
        { created: '2024-01-01T11:00:00Z', temperature: 19.0 }
      ]

      const result = mapTemperatureData(gList)

      expect(result).toHaveLength(2)
      expect(result[0].y).toBe(18.5)
      expect(result[1].y).toBe(19.0)
    })

    it('should convert temperature to Fahrenheit when isTempC is false', async () => {
      const { config } = await import('@/modules/pinia')
      config.isTempC = false

      const gList = [
        { created: '2024-01-01T10:00:00Z', temperature: 20 }
      ]

      const result = mapTemperatureData(gList)

      expect(result[0].y).toBeCloseTo(68, 0) // 20C = 68F
    })

    it('should skip null temperature readings', async () => {
      const { config } = await import('@/modules/pinia')
      config.isTempC = true

      const gList = [
        { created: '2024-01-01T10:00:00Z', temperature: 18.5 },
        { created: '2024-01-01T11:00:00Z', temperature: null },
        { created: '2024-01-01T12:00:00Z', temperature: 19.0 }
      ]

      const result = mapTemperatureData(gList)

      expect(result).toHaveLength(2)
    })

    it('should handle empty list', () => {
      const result = mapTemperatureData([])

      expect(result).toEqual([])
    })
  })

  describe('mapAlcoholData', () => {
    it('should calculate ABV from OG and current gravity', () => {
      const gList = [
        { created: '2024-01-01T10:00:00Z', gravity: 1.050 },
        { created: '2024-01-01T11:00:00Z', gravity: 1.040 },
        { created: '2024-01-01T12:00:00Z', gravity: 1.010 }
      ]

      const result = mapAlcoholData(gList)

      expect(result).toHaveLength(3)
      expect(result[0].y).toBe(0) // OG, so no alcohol yet
      expect(result[2].y).toBeCloseTo(5.25, 1) // (1.050 - 1.010) * 131.25
    })

    it('should use highest gravity as OG', () => {
      const gList = [
        { created: '2024-01-01T10:00:00Z', gravity: 1.010 },
        { created: '2024-01-01T11:00:00Z', gravity: 1.050 },
        { created: '2024-01-01T12:00:00Z', gravity: 1.030 }
      ]

      const result = mapAlcoholData(gList)

      // OG should be 1.050 (highest)
      expect(result[1].y).toBe(0) // At OG
    })

    it('should handle empty list', () => {
      const result = mapAlcoholData([])

      expect(result).toEqual([])
    })

    it('should handle single point', () => {
      const gList = [{ created: '2024-01-01T10:00:00Z', gravity: 1.050 }]

      const result = mapAlcoholData(gList)

      expect(result).toHaveLength(1)
      expect(result[0].y).toBe(0)
    })
  })

  describe('mapChamberData', () => {
    it('should map chamber temperature data in Celsius', async () => {
      const { config } = await import('@/modules/pinia')
      config.isTempC = true

      const gList = [
        { created: '2024-01-01T10:00:00Z', chamberTemperature: 18.5 },
        { created: '2024-01-01T11:00:00Z', chamberTemperature: 18.5 }
      ]

      const result = mapChamberData(gList)

      expect(result).toHaveLength(2)
      expect(result[0].y).toBe('18.50')
    })

    it('should convert chamber temperature to Fahrenheit when isTempC is false', async () => {
      const { config } = await import('@/modules/pinia')
      config.isTempC = false

      const gList = [
        { created: '2024-01-01T10:00:00Z', chamberTemperature: 20 }
      ]

      const result = mapChamberData(gList)

      expect(result[0].y).toBe('68.00')
    })

    it('should skip null chamber temperature readings', async () => {
      const { config } = await import('@/modules/pinia')
      config.isTempC = true

      const gList = [
        { created: '2024-01-01T10:00:00Z', chamberTemperature: 18.5 },
        { created: '2024-01-01T11:00:00Z', chamberTemperature: null },
        { created: '2024-01-01T12:00:00Z', chamberTemperature: 19.0 }
      ]

      const result = mapChamberData(gList)

      expect(result).toHaveLength(2)
    })

    it('should handle empty list', () => {
      const result = mapChamberData([])

      expect(result).toEqual([])
    })

    it('skips a chamber reading that becomes null after the initial filter', () => {
      let reads = 0
      const reading = {
        created: '2024-01-01T10:00:00Z',
        get chamberTemperature() {
          reads += 1
          return reads === 1 ? 20 : null
        }
      }

      expect(mapChamberData([reading])).toEqual([])
    })
  })

  describe('mapGravityVelocityData', () => {
    it('should calculate velocity from hourly slots', () => {
      const now = Date.now()
      const oneHourAgo = now - 3600000

      const gList = [
        { created: new Date(oneHourAgo).toISOString(), gravity: 1.050, velocity: null },
        { created: new Date(now).toISOString(), gravity: 1.045, velocity: null }
      ]

      const result = mapGravityVelocityData(gList)

      expect(result).toHaveProperty('velocity')
      expect(result).toHaveProperty('development')
    })

    it('should include development velocity series', () => {
      const gList = [
        { created: '2024-01-01T10:00:00Z', gravity: 1.050, velocity: -0.1 },
        { created: '2024-01-01T11:00:00Z', gravity: 1.045, velocity: -0.1 }
      ]

      const result = mapGravityVelocityData(gList)

      expect(result.development).toHaveLength(2)
      expect(result.development[0].y).toBe(-0.1)
    })

    it('should skip null development velocities', () => {
      const gList = [
        { created: '2024-01-01T10:00:00Z', gravity: 1.050, velocity: -0.1 },
        { created: '2024-01-01T11:00:00Z', gravity: 1.045, velocity: null }
      ]

      const result = mapGravityVelocityData(gList)

      expect(result.development).toHaveLength(1)
    })

    it('should handle empty list', () => {
      const result = mapGravityVelocityData([])

      expect(result.velocity).toEqual([])
      expect(result.development).toEqual([])
    })
  })

  describe('applyLowPass', () => {
    it('should apply low-pass filter to chart data', () => {
      const input = [
        { x: '2024-01-01T10:00:00Z', y: 1.050 },
        { x: '2024-01-01T11:00:00Z', y: 1.045 },
        { x: '2024-01-01T12:00:00Z', y: 1.040 }
      ]

      const result = applyLowPass(input, 2)

      expect(result).toHaveLength(3)
      expect(result[0].y).toBe(1.05) // (1.050) / 1
      expect(result[1].y).toBeCloseTo(1.0475, 4) // (1.050 + 1.045) / 2
    })

    it('should preserve x values', () => {
      const input = [
        { x: 'time1', y: 10 },
        { x: 'time2', y: 20 }
      ]

      const result = applyLowPass(input, 2)

      expect(result[0].x).toBe('time1')
      expect(result[1].x).toBe('time2')
    })

    it('should handle empty list', () => {
      const result = applyLowPass([], 5)

      expect(result).toEqual([])
    })

    it('should handle single point', () => {
      const input = [{ x: 'time1', y: 10 }]

      const result = applyLowPass(input, 5)

      expect(result).toHaveLength(1)
      expect(result[0].y).toBe(10)
    })

    it('should use specified window size', () => {
      const input = [
        { x: 'time1', y: 10 },
        { x: 'time2', y: 20 },
        { x: 'time3', y: 30 },
        { x: 'time4', y: 40 }
      ]

      const result = applyLowPass(input, 2)

      expect(result).toHaveLength(4)
      // With window size 2, third point should be (20 + 30) / 2
      expect(result[2].y).toBe(25)
    })
  })
})
