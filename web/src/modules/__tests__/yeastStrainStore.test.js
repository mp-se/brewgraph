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
import { useYeastStrainStore } from '@/modules/yeastStrainStore'

// Mock apiClient
vi.mock('@/modules/apiClient', () => ({
  apiJson: vi.fn(),
  apiOk: vi.fn()
}))

// Mock logger
vi.mock('@/ui', () => ({
  logDebug: vi.fn(),
  logInfo: vi.fn(),
  logError: vi.fn()
}))

describe('useYeastStrainStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('Initial State', () => {
    it('should have empty strains array initially', () => {
      const store = useYeastStrainStore()
      expect(store.strains).toEqual([])
    })

    it('should have loaded flag as false initially', () => {
      const store = useYeastStrainStore()
      expect(store.loaded).toBe(false)
    })
  })

  describe('load action', () => {
    it('should load yeast strains from API', async () => {
      const { apiJson } = await import('@/modules/apiClient')
      const store = useYeastStrainStore()
      const mockStrains = [
        {
          id: '1',
          productId: 'WLP001',
          name: 'California Ale',
          laboratory: 'White Labs',
          type: 'Ale',
          form: 'Liquid',
          attenuationMin: 73,
          attenuationMax: 80,
          flocculation: 'Medium',
          tempMinC: 16,
          tempMaxC: 24,
          alcoholTolerance: '14%',
          notes: 'Clean, balanced flavor profile',
          bestFor: 'Pale Ales'
        },
        {
          id: '2',
          productId: 'WLP002',
          name: 'English Ale',
          laboratory: 'White Labs',
          type: 'Ale',
          form: 'Liquid',
          attenuationMin: 63,
          attenuationMax: 70,
          flocculation: 'High',
          tempMinC: 14,
          tempMaxC: 22,
          alcoholTolerance: '12%',
          notes: 'Complex ester profile',
          bestFor: 'Cask Ales'
        }
      ]

      apiJson.mockResolvedValueOnce(mockStrains)

      const result = await store.load()

      expect(apiJson).toHaveBeenCalledWith(
        'GET',
        'yeast-strains',
        undefined,
        { busy: false }
      )
      expect(result).toBe(true)
      expect(store.strains).toEqual(mockStrains)
      expect(store.loaded).toBe(true)
    })

    it('should return true if already loaded', async () => {
      const { apiJson } = await import('@/modules/apiClient')
      const store = useYeastStrainStore()
      const mockStrains = [
        {
          id: '1',
          productId: 'WLP001',
          name: 'California Ale',
          laboratory: 'White Labs',
          type: 'Ale',
          form: 'Liquid',
          attenuationMin: 73,
          attenuationMax: 80,
          flocculation: 'Medium',
          tempMinC: 16,
          tempMaxC: 24,
          alcoholTolerance: '14%',
          notes: 'Clean',
          bestFor: 'Pale Ales'
        }
      ]

      apiJson.mockResolvedValueOnce(mockStrains)

      // First load
      await store.load()
      expect(apiJson).toHaveBeenCalledTimes(1)

      // Second load should return early
      const result = await store.load()
      expect(result).toBe(true)
      expect(apiJson).toHaveBeenCalledTimes(1) // No additional call
    })

    it('should return false when API returns non-array', async () => {
      const { apiJson } = await import('@/modules/apiClient')
      const store = useYeastStrainStore()
      apiJson.mockResolvedValueOnce(null)

      const result = await store.load()

      expect(result).toBe(false)
      expect(store.loaded).toBe(false)
    })

    it('should return false when API returns invalid data', async () => {
      const { apiJson } = await import('@/modules/apiClient')
      const store = useYeastStrainStore()
      apiJson.mockResolvedValueOnce({ invalid: 'data' })

      const result = await store.load()

      expect(result).toBe(false)
      expect(store.loaded).toBe(false)
    })

    it('should handle empty array from API', async () => {
      const { apiJson } = await import('@/modules/apiClient')
      const store = useYeastStrainStore()
      apiJson.mockResolvedValueOnce([])

      const result = await store.load()

      expect(result).toBe(true)
      expect(store.strains).toEqual([])
      expect(store.loaded).toBe(true)
    })
  })

  describe('search action', () => {
    beforeEach(() => {
      const store = useYeastStrainStore()
      store.strains = [
        {
          id: '1',
          productId: 'WLP001',
          name: 'California Ale',
          laboratory: 'White Labs',
          type: 'Ale',
          form: 'Liquid',
          attenuationMin: 73,
          attenuationMax: 80,
          flocculation: 'Medium',
          tempMinC: 16,
          tempMaxC: 24,
          alcoholTolerance: '14%',
          notes: 'Clean',
          bestFor: 'Pale Ales'
        },
        {
          id: '2',
          productId: 'WLP002',
          name: 'English Ale',
          laboratory: 'White Labs',
          type: 'Ale',
          form: 'Liquid',
          attenuationMin: 63,
          attenuationMax: 70,
          flocculation: 'High',
          tempMinC: 14,
          tempMaxC: 22,
          alcoholTolerance: '12%',
          notes: 'Complex',
          bestFor: 'Cask Ales'
        },
        {
          id: '3',
          productId: 'US05',
          name: 'Safale US-05',
          laboratory: 'Fermentis',
          type: 'Ale',
          form: 'Dry',
          attenuationMin: 80,
          attenuationMax: 90,
          flocculation: 'Medium',
          tempMinC: 15,
          tempMaxC: 24,
          alcoholTolerance: '11%',
          notes: 'Clean',
          bestFor: 'American Ales'
        }
      ]
      store.loaded = true
    })

    it('should return first 50 results when query is empty', () => {
      const store = useYeastStrainStore()
      const result = store.search('')

      expect(result).toHaveLength(3)
      expect(result).toEqual(store.strains.slice(0, 50))
    })

    it('should return first 50 results when query is whitespace', () => {
      const store = useYeastStrainStore()
      const result = store.search('   ')

      expect(result).toHaveLength(3)
      expect(result).toEqual(store.strains.slice(0, 50))
    })

    it('should search by name', () => {
      const store = useYeastStrainStore()
      const result = store.search('california')

      expect(result).toHaveLength(1)
      expect(result[0].name).toBe('California Ale')
    })

    it('should search by productId', () => {
      const store = useYeastStrainStore()
      const result = store.search('WLP001')

      expect(result).toHaveLength(1)
      expect(result[0].productId).toBe('WLP001')
    })

    it('should search by laboratory', () => {
      const store = useYeastStrainStore()
      const result = store.search('fermentis')

      expect(result).toHaveLength(1)
      expect(result[0].laboratory).toBe('Fermentis')
    })

    it('should be case-insensitive', () => {
      const store = useYeastStrainStore()
      const result1 = store.search('CALIFORNIA')
      const result2 = store.search('california')

      expect(result1).toEqual(result2)
      expect(result1).toHaveLength(1)
    })

    it('should return partial matches', () => {
      const store = useYeastStrainStore()
      const result = store.search('ale')

      expect(result.length).toBeGreaterThan(0)
      expect(result.every((s) => s.name.toLowerCase().includes('ale') || 
                                 s.productId.toLowerCase().includes('ale') ||
                                 s.laboratory.toLowerCase().includes('ale'))).toBe(true)
    })

    it('should limit results to 50', () => {
      const store = useYeastStrainStore()
      // Add 60 strains
      for (let i = 0; i < 60; i++) {
        store.strains.push({
          id: `${100 + i}`,
          productId: `PROD${i}`,
          name: `Strain ${i}`,
          laboratory: 'Lab',
          type: 'Ale',
          form: 'Liquid',
          attenuationMin: 70,
          attenuationMax: 80,
          flocculation: 'Medium',
          tempMinC: 16,
          tempMaxC: 24,
          alcoholTolerance: '10%',
          notes: 'Test',
          bestFor: 'Test'
        })
      }

      const result = store.search('strain')

      expect(result).toHaveLength(50)
    })

    it('should return empty array when no match found', () => {
      const store = useYeastStrainStore()
      const result = store.search('nonexistent')

      expect(result).toEqual([])
    })
  })
})
