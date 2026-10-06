/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  parseFermentationStepsForEditor,
  stepsInCelsius,
  serializeFermentationSteps,
  fermentationStepsPayload,
  persistFermentationSteps,
  hasActiveFermentationStepNow
} from '@/modules/fermentationStepEditor'

// Mock pinia and utils
vi.mock('@/ui', () => ({
  logDebug: vi.fn()
}))

vi.mock('@/modules/pinia', () => {
  const mockDeviceStore = {
    deleteFermentationSteps: vi.fn(),
    addFermentationSteps: vi.fn()
  }
  return {
    config: { isTempF: false },
    deviceStore: mockDeviceStore
  }
})

vi.mock('@/modules/utils', () => ({
  tempToF: (celsius) => celsius * 9/5 + 32,
  tempToC: (fahrenheit) => (fahrenheit - 32) * 5/9
}))

describe('fermentationStepEditor', () => {
  describe('parseFermentationStepsForEditor', () => {
    it('should parse array of fermentation steps', () => {
      const steps = [
        { order: 0, name: 'Primary', type: 'Hold', temp: 18, days: 14, date: '' },
        { order: 1, name: 'Secondary', type: 'Hold', temp: 16, days: 10, date: '' }
      ]

      const result = parseFermentationStepsForEditor(steps)

      expect(result).toHaveLength(2)
      expect(result[0].name).toBe('Primary')
      expect(result[0].temp).toBe(18)
    })

    it('should parse JSON string of fermentation steps', () => {
      const steps = JSON.stringify([
        { order: 0, name: 'Primary', type: 'Hold', temp: 18, days: 14, date: '' }
      ])

      const result = parseFermentationStepsForEditor(steps)

      expect(result).toHaveLength(1)
      expect(result[0].name).toBe('Primary')
    })

    it('should return empty array for null input', () => {
      const result = parseFermentationStepsForEditor(null)

      expect(result).toEqual([])
    })

    it('should return empty array for undefined input', () => {
      const result = parseFermentationStepsForEditor(undefined)

      expect(result).toEqual([])
    })

    it('should return empty array for invalid JSON string', () => {
      const result = parseFermentationStepsForEditor('invalid json {')

      expect(result).toEqual([])
    })

    it('should return empty array for non-array JSON', () => {
      const result = parseFermentationStepsForEditor('{"invalid": "object"}')

      expect(result).toEqual([])
    })

    it('should use default values for missing fields', () => {
      const steps = [
        { order: 0 } // Missing name, type, temp, days, date
      ]

      const result = parseFermentationStepsForEditor(steps)

      expect(result[0].name).toBe('Step 1')
      expect(result[0].type).toBe('Hold')
      expect(result[0].temp).toBe(20)
      expect(result[0].days).toBe(1)
      expect(result[0].date).toBe('')
    })
  })

  describe('fermentationStepsPayload', () => {
    it('should create payload with proper field mapping', () => {
      const steps = [
        { order: 0, name: 'Primary', type: 'Hold', temp: 18, days: 14, date: '' }
      ]

      const result = fermentationStepsPayload('batch123', steps)

      expect(result).toHaveLength(1)
      expect(result[0].batchId).toBe('batch123')
      expect(result[0].order).toBe(0)
      expect(result[0].name).toBe('Primary')
      expect(result[0].type).toBe('Hold')
      expect(result[0].temp).toBe(18)
      expect(result[0].days).toBe(14)
      expect(result[0].date).toBeNull()
    })

    it('keeps valid dates and normalizes blank dates to null', () => {
      const result = fermentationStepsPayload('batch123', [
        { date: '2026-08-30' },
        { date: '   ' }
      ])

      expect(result.map((step) => step.date)).toEqual(['2026-08-30', null])
    })

    it('should use defaults for missing fields', () => {
      const steps = [{}]

      const result = fermentationStepsPayload('batch123', steps)

      expect(result[0]).toHaveProperty('batchId', 'batch123')
      expect(result[0]).toHaveProperty('order', 0)
      expect(result[0]).toHaveProperty('type', '')
      expect(result[0]).toHaveProperty('name', 'Step 1')
      expect(result[0]).toHaveProperty('temp', 20)
      expect(result[0]).toHaveProperty('days', 1)
      expect(result[0]).toHaveProperty('control', 'fridge')
    })

    it('should handle empty steps array', () => {
      const result = fermentationStepsPayload('batch123', [])

      expect(result).toEqual([])
    })

    it('should map multiple steps correctly', () => {
      const steps = [
        { order: 0, name: 'Primary', type: 'Hold', temp: 18, days: 14, date: '' },
        { order: 1, name: 'Secondary', type: 'Hold', temp: 16, days: 10, date: '' }
      ]

      const result = fermentationStepsPayload('batch123', steps)

      expect(result).toHaveLength(2)
      expect(result[0].order).toBe(0)
      expect(result[1].order).toBe(1)
    })
  })

  describe('persistFermentationSteps', () => {
    beforeEach(() => {
      vi.clearAllMocks()
    })

    it('should return false if delete fails', async () => {
      const { deviceStore } = await import('@/modules/pinia')
      deviceStore.deleteFermentationSteps.mockResolvedValueOnce(false)

      const result = await persistFermentationSteps('batch123', [])

      expect(result).toBe(false)
      expect(deviceStore.addFermentationSteps).not.toHaveBeenCalled()
    })

    it('should return true if no steps to add', async () => {
      const { deviceStore } = await import('@/modules/pinia')
      deviceStore.deleteFermentationSteps.mockResolvedValueOnce(true)

      const result = await persistFermentationSteps('batch123', [])

      expect(result).toBe(true)
    })

    it('should add steps if deletion succeeds', async () => {
      const { deviceStore } = await import('@/modules/pinia')
      deviceStore.deleteFermentationSteps.mockResolvedValueOnce(true)
      deviceStore.addFermentationSteps.mockResolvedValueOnce(true)

      const steps = [
        { order: 0, name: 'Primary', type: 'Hold', temp: 18, days: 14, date: '' }
      ]

      const result = await persistFermentationSteps('batch123', steps)

      expect(deviceStore.addFermentationSteps).toHaveBeenCalled()
      expect(result).toBe(true)
    })

    it('should return false if adding steps fails', async () => {
      const { deviceStore } = await import('@/modules/pinia')
      deviceStore.deleteFermentationSteps.mockResolvedValueOnce(true)
      deviceStore.addFermentationSteps.mockResolvedValueOnce(false)

      const steps = [
        { order: 0, name: 'Primary', type: 'Hold', temp: 18, days: 14, date: '' }
      ]

      const result = await persistFermentationSteps('batch123', steps)

      expect(result).toBe(false)
    })
  })

  describe('stepsInCelsius', () => {
    it('should return empty array for null input', () => {
      const result = stepsInCelsius(null)

      expect(result).toEqual([])
    })

    it('should return empty array for non-array input', () => {
      const result = stepsInCelsius({ invalid: 'object' })

      expect(result).toEqual([])
    })

    it('should handle multiple steps', () => {
      const steps = [
        { order: 0, name: 'Primary', temp: 18, days: 14, date: '' },
        { order: 1, name: 'Secondary', temp: 16, days: 10, date: '' }
      ]

      const result = stepsInCelsius(steps)

      expect(result).toHaveLength(2)
    })
  })

  describe('serializeFermentationSteps', () => {
    it('should serialize steps to JSON string', () => {
      const steps = [
        { order: 0, name: 'Primary', type: 'Hold', temp: 18, days: 14, date: '' }
      ]

      const result = serializeFermentationSteps(steps)

      const parsed = JSON.parse(result)
      expect(parsed).toHaveLength(1)
      expect(parsed[0].name).toBe('Primary')
      expect(parsed[0].temp).toBe(18)
    })

    it('should return empty string when steps array is empty', () => {
      const result = serializeFermentationSteps([])

      expect(result).toBe('')
    })

    it('should add default values to steps', () => {
      const steps = [
        { order: 0, name: 'Primary', temp: 18, days: 14, date: '' }
      ]

      const result = serializeFermentationSteps(steps)

      const parsed = JSON.parse(result)
      expect(parsed[0].type).toBe('')
      expect(parsed[0].control).toBe('fridge')
    })

    it('should handle missing fields with defaults', () => {
      const steps = [{}]

      const result = serializeFermentationSteps(steps)

      const parsed = JSON.parse(result)
      expect(parsed[0].order).toBe(0)
      expect(parsed[0].name).toBe('Step 1')
      expect(parsed[0].type).toBe('')
      expect(parsed[0].temp).toBe(20)
      expect(parsed[0].days).toBe(1)
    })

    it('should handle multiple steps serialization', () => {
      const steps = [
        { order: 0, name: 'Primary', type: 'Hold', temp: 18, days: 14, date: '' },
        { order: 1, name: 'Secondary', type: 'Hold', temp: 16, days: 10, date: '' }
      ]

      const result = serializeFermentationSteps(steps)

      const parsed = JSON.parse(result)
      expect(parsed).toHaveLength(2)
      expect(parsed[0].name).toBe('Primary')
      expect(parsed[1].name).toBe('Secondary')
    })

    it('should include all required fields in serialized output', () => {
      const steps = [
        { order: 0, name: 'Primary', type: 'Hold', temp: 18, days: 14, date: '2024-01-01', control: 'chamber' }
      ]

      const result = serializeFermentationSteps(steps)

      const parsed = JSON.parse(result)
      expect(parsed[0]).toHaveProperty('order')
      expect(parsed[0]).toHaveProperty('type')
      expect(parsed[0]).toHaveProperty('name')
      expect(parsed[0]).toHaveProperty('temp')
      expect(parsed[0]).toHaveProperty('days')
      expect(parsed[0]).toHaveProperty('date')
      expect(parsed[0]).toHaveProperty('control')
    })
  })

  describe('hasActiveFermentationStepNow', () => {
    it('should return true if today is within step date range', () => {
      const today = new Date()
      const dateStr = today.toISOString().split('T')[0]

      const steps = [
        { date: dateStr, days: 5 }
      ]

      const result = hasActiveFermentationStepNow(steps)

      expect(result).toBe(true)
    })

    it('should return false if today is before step date', () => {
      const tomorrow = new Date()
      tomorrow.setDate(tomorrow.getDate() + 1)
      const dateStr = tomorrow.toISOString().split('T')[0]

      const steps = [
        { date: dateStr, days: 5 }
      ]

      const result = hasActiveFermentationStepNow(steps)

      expect(result).toBe(false)
    })

    it('should return false if today is after step date range', () => {
      const yesterday = new Date()
      yesterday.setDate(yesterday.getDate() - 10)
      const dateStr = yesterday.toISOString().split('T')[0]

      const steps = [
        { date: dateStr, days: 5 }
      ]

      const result = hasActiveFermentationStepNow(steps)

      expect(result).toBe(false)
    })

    it('should return false for non-array input', () => {
      const result = hasActiveFermentationStepNow(null)

      expect(result).toBe(false)
    })

    it('should return false for invalid date format', () => {
      const steps = [
        { date: 'invalid-date', days: 5 }
      ]

      const result = hasActiveFermentationStepNow(steps)

      expect(result).toBe(false)
    })

    it('should return false for empty steps array', () => {
      const result = hasActiveFermentationStepNow([])

      expect(result).toBe(false)
    })

    it('should handle steps with missing days field', () => {
      const today = new Date()
      const dateStr = today.toISOString().split('T')[0]

      const steps = [
        { date: dateStr }
      ]

      const result = hasActiveFermentationStepNow(steps)

      expect(result).toBe(true) // Default days is 1
    })

    it('should check all steps in array', () => {
      const yesterday = new Date()
      yesterday.setDate(yesterday.getDate() - 1)
      const dateStr = yesterday.toISOString().split('T')[0]

      const tomorrow = new Date()
      tomorrow.setDate(tomorrow.getDate() + 1)
      const futureDateStr = tomorrow.toISOString().split('T')[0]

      const steps = [
        { date: dateStr, days: 1 }, // Passed
        { date: futureDateStr, days: 5 } // Future
      ]

      const result = hasActiveFermentationStepNow(steps)

      expect(result).toBe(false)
    })

    it('should handle invalid JSON dates', () => {
      const steps = [
        { date: '2024-13-45', days: 5 } // Invalid month/day
      ]

      const result = hasActiveFermentationStepNow(steps)

      expect(result).toBe(false)
    })

    it('should handle missing date property', () => {
      const steps = [
        { days: 5 }
      ]

      const result = hasActiveFermentationStepNow(steps)

      expect(result).toBe(false)
    })

    it('should handle non-string date', () => {
      const steps = [
        { date: 12345, days: 5 }
      ]

      const result = hasActiveFermentationStepNow(steps)

      expect(result).toBe(false)
    })

    it('should return true for multi-day steps including today', () => {
      const today = new Date()
      today.setDate(today.getDate() - 2) // Start 2 days ago
      const dateStr = today.toISOString().split('T')[0]

      const steps = [
        { date: dateStr, days: 5 } // 5-day step starting 2 days ago
      ]

      const result = hasActiveFermentationStepNow(steps)

      expect(result).toBe(true)
    })

    it('should return false for object without date field', () => {
      const steps = [
        { name: 'Step 1', temp: 20 }
      ]

      const result = hasActiveFermentationStepNow(steps)

      expect(result).toBe(false)
    })
  })
})
