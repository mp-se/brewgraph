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
import { useGravityStore } from '@/modules/gravityStore'

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

describe('useGravityStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    global.fetch = vi.fn()
  })

  it('should have empty gravity array initially', () => {
    const store = useGravityStore()
    expect(store.gravity).toEqual([])
  })

  describe('getGravityListForBatch Action', () => {
    it('should fetch gravity data for batch', async () => {
      const store = useGravityStore()
      const mockData = {
        items: [
          {
            id: 1,
            temperature: 20.5,
            gravity: 1.05,
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

      const result = await store.getGravityListForBatch(1)

      expect(result).toBeTruthy()
      expect(store.gravity.length).toBe(1)
    })

    it('should return null on fetch error in getGravityListForBatch', async () => {
      const store = useGravityStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Error'))

      const result = await store.getGravityListForBatch(1)

      expect(result).toBeNull()
    })

    it('should handle non-ok response in getGravityListForBatch', async () => {
      const store = useGravityStore()
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 404
      })

      const result = await store.getGravityListForBatch(1)

      expect(result).toBeNull()
    })
  })

  describe('updateGravity Action', () => {
    it('should update gravity successfully', async () => {
      const store = useGravityStore()
      const gravityToUpdate = {
        id: 1,
        toJson: () => ({ id: 1, gravity: 1.05 })
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 200
      })

      const result = await store.updateGravity(gravityToUpdate)

      expect(result).toBe(true)
    })

    it('should return false if update status is not 200', async () => {
      const store = useGravityStore()
      const gravityToUpdate = {
        id: 1,
        toJson: () => ({ id: 1 })
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 400
      })

      const result = await store.updateGravity(gravityToUpdate)

      expect(result).toBe(false)
    })

    it('should return false on update error', async () => {
      const store = useGravityStore()
      const gravityToUpdate = {
        id: 1,
        toJson: () => ({ id: 1 })
      }

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Error'))

      const result = await store.updateGravity(gravityToUpdate)

      expect(result).toBe(false)
    })
  })

  describe('getLatestGravity Action', () => {
    it('should fetch latest gravity readings successfully', async () => {
      const store = useGravityStore()
      const mockGravity = [
        { id: 1, gravity: 1.05, temperature: 20, batchId: 1, createdAt: '2026-05-01' }
      ]
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockGravity)
      })
      const result = await store.getLatestGravity(5)
      expect(result).toBeTruthy()
      expect(result.length).toBe(1)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('batches/gravity/latest'),
        expect.objectContaining({ method: 'GET' })
      )
    })

    it('should use default limit when not provided', async () => {
      const store = useGravityStore()
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce([])
      })
      const result = await store.getLatestGravity()
      expect(result).not.toBeNull()
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('limit=5'),
        expect.any(Object)
      )
    })

    it('should return null on non-ok response in getLatestGravity', async () => {
      const store = useGravityStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 500 })
      const result = await store.getLatestGravity()
      expect(result).toBeNull()
    })

    it('should return null on fetch error in getLatestGravity', async () => {
      const store = useGravityStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))
      const result = await store.getLatestGravity()
      expect(result).toBeNull()
    })
  })

  describe('getGravityListForBatch pagination', () => {
    it('should fetch gravity across multiple pages', async () => {
      const store = useGravityStore()
      const item = { id: 1, gravity: 1.05, temperature: 20, batchId: 1, createdAt: '2026-05-01' }
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
      const result = await store.getGravityListForBatch(1)
      expect(result).not.toBeNull()
      expect(store.gravity.length).toBe(2)
      expect(global.fetch).toHaveBeenCalledTimes(2)
    })
  })
})
