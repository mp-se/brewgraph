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
import { useTapStore } from '@/modules/tapStore'

vi.mock('@/ui', async (importActual) => {
  const actual = await importActual()
  return { ...actual, logDebug: vi.fn(), logInfo: vi.fn(), logError: vi.fn() }
})

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
    fetchTimout: 30000,
    updatedTapData: 0
  }
}))

const TAP = {
  id: 't1',
  name: 'Left Tap',
  tapNumber: 1,
  location: 'Kegerator A',
  notes: null,
  token: null,
  createdAt: '2026-05-01T00:00:00',
  updatedAt: '2026-05-01T00:00:00'
}

const makePage = (items, pages = 1) => ({
  items,
  pages,
  total: items.length,
  page: 1,
  page_size: 100
})

describe('useTapStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    global.fetch = vi.fn()
  })

  it('should have empty taps array initially', () => {
    const store = useTapStore()
    expect(store.taps).toEqual([])
  })

  describe('getTapList', () => {
    it('fetches all taps from a single page', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(makePage([TAP]))
      })

      const store = useTapStore()
      const result = await store.getTapList()

      expect(result).not.toBeNull()
      expect(store.taps.length).toBe(1)
      expect(store.taps[0].id).toBe('t1')
    })

    it('fetches all taps across multiple pages', async () => {
      const page1 = { items: [TAP], pages: 2, total: 2, page: 1, page_size: 1 }
      const page2 = {
        items: [{ ...TAP, id: 't2', name: 'Right Tap' }],
        pages: 2,
        total: 2,
        page: 2,
        page_size: 1
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

      const store = useTapStore()
      const result = await store.getTapList()

      expect(result).not.toBeNull()
      expect(store.taps.length).toBe(2)
      expect(global.fetch).toHaveBeenCalledTimes(2)
    })

    it('returns null on fetch error', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 500 })

      const store = useTapStore()
      const result = await store.getTapList()

      expect(result).toBeNull()
    })

    it('returns null on network rejection', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const store = useTapStore()
      const result = await store.getTapList()

      expect(result).toBeNull()
    })
  })

  describe('getTap', () => {
    it('fetches a tap by id', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(TAP)
      })

      const store = useTapStore()
      const result = await store.getTap('t1')

      expect(result).not.toBeNull()
      expect(result.id).toBe('t1')
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/taps/t1',
        expect.any(Object)
      )
    })

    it('returns null on non-ok response', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 404 })

      const store = useTapStore()
      const result = await store.getTap('t1')

      expect(result).toBeNull()
    })

    it('returns null on network rejection', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const store = useTapStore()
      const result = await store.getTap('t1')

      expect(result).toBeNull()
    })

    it('returns null for empty id', async () => {
      const store = useTapStore()
      const result = await store.getTap('')

      expect(result).toBeNull()
      expect(global.fetch).not.toHaveBeenCalled()
    })

    it('returns null for undefined id', async () => {
      const store = useTapStore()
      const result = await store.getTap(undefined)

      expect(result).toBeNull()
    })
  })

  describe('addTap', () => {
    it('creates a new tap and returns it', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: vi.fn().mockResolvedValueOnce({ ...TAP, id: 't2' })
      })

      const store = useTapStore()
      const tap = { toJson: () => ({ ...TAP, id: '' }) }
      const result = await store.addTap(tap)

      expect(result).not.toBeNull()
      expect(result.id).toBe('t2')
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/taps',
        expect.objectContaining({ method: 'POST' })
      )
    })

    it('returns null when status is not 201', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 400 })

      const store = useTapStore()
      const tap = { toJson: () => ({}) }
      const result = await store.addTap(tap)

      expect(result).toBeNull()
    })

    it('returns null on network rejection', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const store = useTapStore()
      const tap = { toJson: () => ({}) }
      const result = await store.addTap(tap)

      expect(result).toBeNull()
    })
  })

  describe('updateTap', () => {
    it('updates a tap and returns the updated object', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce({ ...TAP, name: 'Right Tap' })
      })

      const store = useTapStore()
      const tap = { id: 't1', toJson: () => ({ ...TAP, name: 'Right Tap' }) }
      const result = await store.updateTap(tap)

      expect(result).not.toBeNull()
      expect(result.name).toBe('Right Tap')
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/taps/t1',
        expect.objectContaining({ method: 'PATCH' })
      )
    })

    it('returns null when status is not 200', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 422 })

      const store = useTapStore()
      const tap = { id: 't1', toJson: () => ({}) }
      const result = await store.updateTap(tap)

      expect(result).toBeNull()
    })

    it('returns null on network rejection', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const store = useTapStore()
      const tap = { id: 't1', toJson: () => ({}) }
      const result = await store.updateTap(tap)

      expect(result).toBeNull()
    })
  })

  describe('deleteTap', () => {
    it('deletes a tap and returns true on 204', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: true, status: 204 })

      const store = useTapStore()
      const result = await store.deleteTap('t1')

      expect(result).toBe(true)
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/taps/t1',
        expect.objectContaining({ method: 'DELETE' })
      )
    })

    it('returns false when status is not 204', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 404 })

      const store = useTapStore()
      const result = await store.deleteTap('t1')

      expect(result).toBe(false)
    })

    it('returns false on network rejection', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const store = useTapStore()
      const result = await store.deleteTap('t1')

      expect(result).toBe(false)
    })
  })

  describe('processEvent', () => {
    it('removes tap on delete event', async () => {
      const store = useTapStore()
      store.taps = [
        { id: 't1', name: 'Left Tap' },
        { id: 't2', name: 'Right Tap' }
      ]

      await store.processEvent('delete', 't1')

      expect(store.taps.length).toBe(1)
      expect(store.taps[0].id).toBe('t2')
    })

    it('updates existing tap on update event', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce({ ...TAP, id: 't1', name: 'Updated Tap' })
      })

      const store = useTapStore()
      store.taps = [{ id: 't1', name: 'Left Tap' }]

      await store.processEvent('update', 't1')

      expect(store.taps.length).toBe(1)
      expect(store.taps[0].name).toBe('Updated Tap')
    })

    it('adds tap if not in list on update event', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce({ ...TAP, id: 't99', name: 'New Tap' })
      })

      const store = useTapStore()
      store.taps = []

      await store.processEvent('update', 't99')

      expect(store.taps.length).toBe(1)
    })

    it('adds tap on create event', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce({ ...TAP, id: 't3', name: 'New Tap' })
      })

      const store = useTapStore()
      store.taps = []

      await store.processEvent('create', 't3')

      expect(store.taps.length).toBe(1)
      expect(store.taps[0].id).toBe('t3')
    })

    it('handles fetch failure gracefully on update event', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const store = useTapStore()
      store.taps = [{ id: 't1', name: 'Left Tap' }]

      await store.processEvent('update', 't1')

      expect(store.taps.length).toBe(1)
    })

    it('handles fetch failure gracefully on create event', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const store = useTapStore()
      store.taps = []

      await store.processEvent('create', 't99')

      expect(store.taps.length).toBe(0)
    })
  })

  describe('tapList getter', () => {
    it('returns the taps array via getter', () => {
      const store = useTapStore()
      store.taps = [{ id: 't1', name: 'Left Tap' }]

      expect(store.tapList.length).toBe(1)
      expect(store.tapList[0].id).toBe('t1')
    })
  })
})
