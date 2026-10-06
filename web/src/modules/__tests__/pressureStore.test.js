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
import { usePressureStore } from '@/modules/pressureStore'

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
vi.mock('@/modules/pinia', () => ({
  global: {
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
}))

describe('usePressureStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    global.fetch = vi.fn()
  })

  it('should have empty pressure array initially', () => {
    const store = usePressureStore()
    expect(store.pressure).toEqual([])
  })

  describe('getPressureListForBatch Action', () => {
    it('should fetch pressure data for batch', async () => {
      const store = usePressureStore()
      const mockData = {
        items: [
          {
            id: 1,
            temperature: 20.5,
            pressure: 15.2,
            created: '2024-01-15T10:00:00',
            batchId: 1,
            active: true
          }
        ],
        hasMore: false,
        nextCursor: null
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockData)
      })

      const result = await store.getPressureListForBatch(1)

      expect(result).toBeTruthy()
      expect(store.pressure.length).toBe(1)
    })

    it('should return null on fetch error', async () => {
      const store = usePressureStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Error'))

      const result = await store.getPressureListForBatch(1)

      expect(result).toBeNull()
    })

    it('should handle non-ok response', async () => {
      const store = usePressureStore()
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 404
      })

      const result = await store.getPressureListForBatch(1)

      expect(result).toBeNull()
    })
  })

  describe('updatePressure Action', () => {
    it('should update pressure successfully', async () => {
      const store = usePressureStore()
      const pressureToUpdate = {
        id: 1,
        toJson: () => ({ id: 1, pressure: 15.2 })
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 200
      })

      const result = await store.updatePressure(pressureToUpdate)

      expect(result).toBe(true)
    })

    it('should return false if update status is not 200', async () => {
      const store = usePressureStore()
      const pressureToUpdate = {
        id: 1,
        toJson: () => ({ id: 1 })
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 400
      })

      const result = await store.updatePressure(pressureToUpdate)

      expect(result).toBe(false)
    })

    it('should return false on update error', async () => {
      const store = usePressureStore()
      const pressureToUpdate = {
        id: 1,
        toJson: () => ({ id: 1 })
      }

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Error'))

      const result = await store.updatePressure(pressureToUpdate)

      expect(result).toBe(false)
    })
  })

  describe('getLatestPressure Action', () => {
    it('should fetch latest pressure readings successfully', async () => {
      const store = usePressureStore()
      const mockPressure = [
        { id: 1, pressure: 15.2, temperature: 20, batchId: 1, createdAt: '2026-05-01' }
      ]
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockPressure)
      })
      const result = await store.getLatestPressure(5)
      expect(result).toBeTruthy()
      expect(result.length).toBe(1)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('batches/pressure/latest'),
        expect.objectContaining({ method: 'GET' })
      )
    })

    it('should use default limit when not provided', async () => {
      const store = usePressureStore()
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce([])
      })
      const result = await store.getLatestPressure()
      expect(result).not.toBeNull()
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('limit=5'),
        expect.any(Object)
      )
    })

    it('should return null on non-ok response in getLatestPressure', async () => {
      const store = usePressureStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 500 })
      const result = await store.getLatestPressure()
      expect(result).toBeNull()
    })

    it('should return null on fetch error in getLatestPressure', async () => {
      const store = usePressureStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))
      const result = await store.getLatestPressure()
      expect(result).toBeNull()
    })
  })

  describe('getPressureListForBatch pagination', () => {
    it('should fetch pressure across multiple pages', async () => {
      const store = usePressureStore()
      const item = { id: 1, pressure: 15.2, temperature: 20, batchId: 1, createdAt: '2026-05-01' }
      const page1 = { items: [item], hasMore: true, nextCursor: 'cursor1' }
      const page2 = { items: [{ ...item, id: 2 }], hasMore: false, nextCursor: null }
      global.fetch = vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: vi.fn().mockResolvedValueOnce(page1)
        })
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: vi.fn().mockResolvedValueOnce(page2)
        })
      const result = await store.getPressureListForBatch(1)
      expect(result).not.toBeNull()
      expect(store.pressure.length).toBe(2)
      expect(global.fetch).toHaveBeenCalledTimes(2)
    })
  })
})
