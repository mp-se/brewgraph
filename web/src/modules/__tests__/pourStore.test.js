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
import { usePourStore } from '@/modules/pourStore'

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

describe('usePourStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    global.fetch = vi.fn()
  })

  it('should have empty pours array initially', () => {
    const store = usePourStore()
    expect(store.pours).toEqual([])
  })

  describe('listPours Action', () => {
    it('should fetch pours for vessel (single page)', async () => {
      const store = usePourStore()
      const mockData = {
        items: [
          { id: 'p1', pourAmount: 0.5, volumeRemaining: 18.5, createdAt: '2026-05-01T10:00:00' }
        ],
        has_more: false,
        next_cursor: null
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockData)
      })

      const result = await store.listPours('v1')

      expect(result).toBeTruthy()
      expect(store.pours.length).toBe(1)
    })

    it('should fetch pours across multiple pages', async () => {
      const store = usePourStore()
      const pour = {
        id: 'p1',
        pourAmount: 0.5,
        volumeRemaining: 18.5,
        createdAt: '2026-05-01T10:00:00'
      }
      const page1 = { items: [pour], has_more: true, next_cursor: '2026-05-01T10:00:00' }
      const page2 = {
        items: [{ ...pour, id: 'p2', createdAt: '2026-05-01T09:00:00' }],
        has_more: false,
        next_cursor: null
      }

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

      const result = await store.listPours('v1')

      expect(result).not.toBeNull()
      expect(store.pours.length).toBe(2)
      expect(global.fetch).toHaveBeenCalledTimes(2)
    })

    it('should return null on fetch error', async () => {
      const store = usePourStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Error'))

      const result = await store.listPours('v1')

      expect(result).toBeNull()
    })

    it('should handle non-ok response', async () => {
      const store = usePourStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 404 })

      const result = await store.listPours('v1')

      expect(result).toBeNull()
    })
  })

  describe('recordPour Action', () => {
    it('should record pour successfully', async () => {
      const store = usePourStore()
      const mockResponse = {
        id: 1,
        pourAmount: 500,
        notes: '',
        created: '2024-01-15T10:00:00'
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 201,
        json: vi.fn().mockResolvedValueOnce(mockResponse)
      })

      const result = await store.recordPour(10, 500, '')

      expect(result).toBeTruthy()
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/vessels/10/pours',
        expect.objectContaining({ method: 'POST' })
      )
    })

    it('should return null if status is not 201', async () => {
      const store = usePourStore()

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 400
      })

      const result = await store.recordPour(10, 500)

      expect(result).toBeNull()
    })

    it('should return null on error', async () => {
      const store = usePourStore()

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Error'))

      const result = await store.recordPour(10, 500)

      expect(result).toBeNull()
    })
  })

  describe('getLatestPour Action', () => {
    it('should fetch latest pours successfully', async () => {
      const store = usePourStore()
      const mockPours = [
        { id: 'p1', pourAmount: 0.5, volumeRemaining: 18.5, createdAt: '2026-05-01T10:00:00' }
      ]
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockPours)
      })
      const result = await store.getLatestPour(5)
      expect(result).toBeTruthy()
      expect(store.pours.length).toBe(1)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('vessels/pours/latest'),
        expect.objectContaining({ method: 'GET' })
      )
    })

    it('should use default limit of 5 when none provided', async () => {
      const store = usePourStore()
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce([])
      })
      const result = await store.getLatestPour()
      expect(result).not.toBeNull()
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('limit=5'),
        expect.any(Object)
      )
    })

    it('should return null on fetch error in getLatestPour', async () => {
      const store = usePourStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))
      const result = await store.getLatestPour()
      expect(result).toBeNull()
    })

    it('should return null on non-ok response in getLatestPour', async () => {
      const store = usePourStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 500 })
      const result = await store.getLatestPour()
      expect(result).toBeNull()
    })
  })

  describe('recordBottlePour Action', () => {
    it('should record bottle pour successfully', async () => {
      const store = usePourStore()
      const mockResponse = {
        id: 2,
        bottleCount: 12,
        createdAt: '2026-05-01T10:00:00'
      }
      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 201,
        json: vi.fn().mockResolvedValueOnce(mockResponse)
      })
      const result = await store.recordBottlePour('v1', 12)
      expect(result).toBeTruthy()
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/vessels/v1/pours/bottles',
        expect.objectContaining({ method: 'POST' })
      )
    })

    it('should return null if status is not 201', async () => {
      const store = usePourStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ status: 400 })
      const result = await store.recordBottlePour('v1', 12)
      expect(result).toBeNull()
    })

    it('should return null on fetch error in recordBottlePour', async () => {
      const store = usePourStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))
      const result = await store.recordBottlePour('v1', 12)
      expect(result).toBeNull()
    })
  })
})
