/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'

describe('useYeastStrains', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
  })

  describe('load function', () => {
    it('should populate strains from the API when not yet loaded', async () => {
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

      vi.doMock('@/modules/apiClient', () => ({
        apiJson: vi.fn().mockResolvedValueOnce(mockStrains)
      }))

      const { useYeastStrains } = await import('@/modules/useYeastStrains')
      const { strains, load } = useYeastStrains()

      await load()

      expect(strains.value).toHaveLength(1)
      expect(strains.value[0].productId).toBe('WLP001')
    })

    it('should not call the API a second time when already loaded', async () => {
      const mockApiJson = vi.fn().mockResolvedValue([
        {
          id: '1',
          productId: 'US05',
          name: 'Safale',
          laboratory: 'Fermentis',
          type: 'Ale',
          form: 'Dry',
          attenuationMin: 80,
          attenuationMax: 90,
          flocculation: 'Medium',
          tempMinC: 15,
          tempMaxC: 24,
          alcoholTolerance: '11%',
          notes: null,
          bestFor: null
        }
      ])

      vi.doMock('@/modules/apiClient', () => ({ apiJson: mockApiJson }))

      const { useYeastStrains } = await import('@/modules/useYeastStrains')
      const { load } = useYeastStrains()

      await load()
      await load()

      expect(mockApiJson).toHaveBeenCalledTimes(1)
    })

    it('should not update strains when the API returns a non-array value', async () => {
      vi.doMock('@/modules/apiClient', () => ({
        apiJson: vi.fn().mockResolvedValueOnce(null)
      }))

      const { useYeastStrains } = await import('@/modules/useYeastStrains')
      const { strains, load } = useYeastStrains()
      strains.value = []

      await load()

      expect(strains.value).toHaveLength(0)
    })
  })

  describe('search function', () => {
    it('should return first 50 results when query is empty', async () => {
      const { useYeastStrains } = await import('@/modules/useYeastStrains')

      const mockStrains = Array.from({ length: 10 }, (_, i) => ({
        id: `${i}`,
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
      }))

      const { search, strains } = useYeastStrains()
      strains.value = mockStrains

      const result = search('')

      expect(result).toHaveLength(10)
    })

    it('should return first 50 results when query is whitespace', async () => {
      const { useYeastStrains } = await import('@/modules/useYeastStrains')

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

      const { search, strains } = useYeastStrains()
      strains.value = mockStrains

      const result = search('   ')

      expect(result).toHaveLength(1)
    })

    it('should search by name case-insensitively', async () => {
      const { useYeastStrains } = await import('@/modules/useYeastStrains')

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

      const { search, strains } = useYeastStrains()
      strains.value = mockStrains

      const result = search('california')

      expect(result).toHaveLength(1)
      expect(result[0].name).toBe('California Ale')
    })

    it('should search by productId case-insensitively', async () => {
      const { useYeastStrains } = await import('@/modules/useYeastStrains')

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

      const { search, strains } = useYeastStrains()
      strains.value = mockStrains

      const result = search('wlp001')

      expect(result).toHaveLength(1)
      expect(result[0].productId).toBe('WLP001')
    })

    it('should search by laboratory case-insensitively', async () => {
      const { useYeastStrains } = await import('@/modules/useYeastStrains')

      const mockStrains = [
        {
          id: '1',
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

      const { search, strains } = useYeastStrains()
      strains.value = mockStrains

      const result = search('fermentis')

      expect(result).toHaveLength(1)
      expect(result[0].laboratory).toBe('Fermentis')
    })

    it('should return partial matches', async () => {
      const { useYeastStrains } = await import('@/modules/useYeastStrains')

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
        }
      ]

      const { search, strains } = useYeastStrains()
      strains.value = mockStrains

      const result = search('ale')

      expect(result.length).toBeGreaterThan(0)
    })

    it('should limit results to 50', async () => {
      const { useYeastStrains } = await import('@/modules/useYeastStrains')

      const mockStrains = Array.from({ length: 60 }, (_, i) => ({
        id: `${i}`,
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
      }))

      const { search, strains } = useYeastStrains()
      strains.value = mockStrains

      const result = search('strain')

      expect(result).toHaveLength(50)
    })

    it('should return empty array when no match', async () => {
      const { useYeastStrains } = await import('@/modules/useYeastStrains')

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

      const { search, strains } = useYeastStrains()
      strains.value = mockStrains

      const result = search('nonexistent')

      expect(result).toEqual([])
    })

    it('should handle empty strains array', async () => {
      const { useYeastStrains } = await import('@/modules/useYeastStrains')

      const { search, strains } = useYeastStrains()
      strains.value = []

      const result = search('')

      expect(result).toEqual([])
    })

    it('should handle search with special characters', async () => {
      const { useYeastStrains } = await import('@/modules/useYeastStrains')

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

      const { search, strains } = useYeastStrains()
      strains.value = mockStrains

      const result = search('!@#$')

      expect(result).toEqual([])
    })

    it('should handle multiple matching criteria', async () => {
      const { useYeastStrains } = await import('@/modules/useYeastStrains')

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
        }
      ]

      const { search, strains } = useYeastStrains()
      strains.value = mockStrains

      const result = search('WLP')

      expect(result).toHaveLength(2)
    })

    it('should handle case sensitivity in search', async () => {
      const { useYeastStrains } = await import('@/modules/useYeastStrains')

      const mockStrains = [
        {
          id: '1',
          productId: 'UPPERCASE',
          name: 'MixedCase Name',
          laboratory: 'lowercase lab',
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

      const { search, strains } = useYeastStrains()
      strains.value = mockStrains

      const resultUpper = search('UPPERCASE')
      const resultLower = search('uppercase')
      const resultMixed = search('UppErCase')

      expect(resultUpper).toHaveLength(1)
      expect(resultLower).toHaveLength(1)
      expect(resultMixed).toHaveLength(1)
    })

    it('should handle very long search query', async () => {
      const { useYeastStrains } = await import('@/modules/useYeastStrains')

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

      const { search, strains } = useYeastStrains()
      strains.value = mockStrains

      const longQuery = 'a'.repeat(500)
      const result = search(longQuery)

      expect(result).toEqual([])
    })
  })
})
