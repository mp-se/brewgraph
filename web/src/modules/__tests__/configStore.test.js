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

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useConfigStore } from '@/modules/configStore'

// Mock logger
vi.mock('@/ui', async (importActual) => {
  const actual = await importActual()
  return {
    ...actual,
    logDebug: vi.fn(),
    logInfo: vi.fn(),
    logError: vi.fn()
  }
})

// Mock pinia global object
vi.mock('@/modules/pinia', () => {
  const global = {
    disabled: false,
    acquireBusy() {
      this.disabled = true
      let released = false
      return () => { if (!released) { released = true; this.disabled = false } }
    },
    baseURL: 'http://localhost:8080/',
    apiURL: 'http://localhost:8080/api/',
    token: 'Bearer test',
    fetchTimout: 30000
  }
  return {
    global,
    saveConfigState: vi.fn()
  }
})

describe('useConfigStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // Reset fetch mock
    global.fetch = vi.fn()
  })

  describe('Initial State', () => {
    it('should have default config values', () => {
      const store = useConfigStore()
      expect(store.id).toBe('')
      expect(store.temperatureFormat).toBe('')
      expect(store.pressureFormat).toBe('')
      expect(store.gravityFormat).toBe('')
      expect(store.volumeFormat).toBe('')
    })
  })

  describe('Temperature Format Getters', () => {
    it('should determine if temperature is Celsius', () => {
      const store = useConfigStore()
      store.temperatureFormat = 'C'
      expect(store.isTempC).toBe(true)
      expect(store.isTempF).toBe(false)
    })

    it('should determine if temperature is Fahrenheit', () => {
      const store = useConfigStore()
      store.temperatureFormat = 'F'
      expect(store.isTempF).toBe(true)
      expect(store.isTempC).toBe(false)
    })

    it('should return temperature unit', () => {
      const store = useConfigStore()
      store.temperatureFormat = 'C'
      expect(store.tempUnit).toBe('C')
    })
  })

  describe('Gravity Format Getters', () => {
    it('should determine if gravity is SG', () => {
      const store = useConfigStore()
      store.gravityFormat = 'SG'
      expect(store.isGravitySG).toBe(true)
      expect(store.isGravityP).toBe(false)
    })

    it('should determine if gravity is P', () => {
      const store = useConfigStore()
      store.gravityFormat = 'P'
      expect(store.isGravityP).toBe(true)
      expect(store.isGravitySG).toBe(false)
    })
  })

  describe('Volume Format Getters', () => {
    it('should determine if volume is metric', () => {
      const store = useConfigStore()
      store.volumeFormat = 'metric'
      expect(store.isVolumeMetric).toBe(true)
      expect(store.isVolumeUs).toBe(false)
      expect(store.isVolumeUk).toBe(false)
    })

    it('should determine if volume is US', () => {
      const store = useConfigStore()
      store.volumeFormat = 'US'
      expect(store.isVolumeUs).toBe(true)
      expect(store.isVolumeMetric).toBe(false)
      expect(store.isVolumeUk).toBe(false)
    })

    it('should determine if volume is UK', () => {
      const store = useConfigStore()
      store.volumeFormat = 'UK'
      expect(store.isVolumeUk).toBe(true)
      expect(store.isVolumeMetric).toBe(false)
      expect(store.isVolumeUs).toBe(false)
    })
  })

  describe('Pressure Format Getters', () => {
    it('should determine if pressure is BAR', () => {
      const store = useConfigStore()
      store.pressureFormat = 'BAR'
      expect(store.isPressureBAR).toBe(true)
      expect(store.isPressureKPA).toBe(false)
      expect(store.isPressurePSI).toBe(false)
    })

    it('should determine if pressure is KPA', () => {
      const store = useConfigStore()
      store.pressureFormat = 'KPA'
      expect(store.isPressureKPA).toBe(true)
      expect(store.isPressureBAR).toBe(false)
      expect(store.isPressurePSI).toBe(false)
    })

    it('should determine if pressure is PSI', () => {
      const store = useConfigStore()
      store.pressureFormat = 'PSI'
      expect(store.isPressurePSI).toBe(true)
      expect(store.isPressureBAR).toBe(false)
      expect(store.isPressureKPA).toBe(false)
    })
  })

  describe('load Action', () => {
    it('should load config successfully', async () => {
      const store = useConfigStore()
      const mockResponse = {
        id: 1,
        temperatureFormat: 'C',
        pressureFormat: 'BAR',
        gravityFormat: 'SG',
        volumeFormat: 'L'
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        json: vi.fn().mockResolvedValueOnce(mockResponse)
      })

      const result = await store.load()

      expect(result).toBe(true)
      expect(store.temperatureFormat).toBe('C')
      expect(store.pressureFormat).toBe('BAR')
      expect(store.gravityFormat).toBe('SG')
      expect(store.volumeFormat).toBe('L')
    })

    it('should handle fetch error', async () => {
      const store = useConfigStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const result = await store.load()

      expect(result).toBe(false)
    })

    it('should handle JSON parse error', async () => {
      const store = useConfigStore()
      global.fetch = vi.fn().mockResolvedValueOnce({
        json: vi.fn().mockRejectedValueOnce(new Error('Invalid JSON'))
      })

      const result = await store.load()

      expect(result).toBe(false)
    })
  })

  describe('save Action', () => {
    it('should save config successfully', async () => {
      const store = useConfigStore()
      store.temperatureFormat = 'F'
      store.pressureFormat = 'PSI'
      store.gravityFormat = 'P'
      store.volumeFormat = 'US'

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 200
      })

      const result = await store.save()

      expect(result).toBe(true)
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/tenant/settings',
        expect.objectContaining({
          method: 'PATCH',
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          })
        })
      )
    })

    it('should handle non-200 response status', async () => {
      const store = useConfigStore()

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 400
      })

      const result = await store.save()

      expect(result).toBe(false)
    })

    it('should handle fetch error during save', async () => {
      const store = useConfigStore()

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const result = await store.save()

      expect(result).toBe(false)
    })
  })

  describe('State Mutations', () => {
    it('should allow setting config values', () => {
      const store = useConfigStore()
      store.temperatureFormat = 'C'
      store.pressureFormat = 'BAR'
      store.gravityFormat = 'SG'
      store.volumeFormat = 'L'

      expect(store.temperatureFormat).toBe('C')
      expect(store.pressureFormat).toBe('BAR')
      expect(store.gravityFormat).toBe('SG')
      expect(store.volumeFormat).toBe('L')
    })
  })
})
