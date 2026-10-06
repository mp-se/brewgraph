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
import { useVesselStore } from '@/modules/vesselStore'

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
    updatedVesselData: 0
  }
}))

const VESSEL = {
  id: 'v1',
  batchId: 'b1',
  vesselType: 'keg',
  name: 'Keg 1',
  fillDate: '2026-05-01',
  totalVolume: 19.0,
  volumeRemaining: 19.0,
  status: 'filled',
  tapId: null,
  bottleVolume: null,
  bottleCount: null,
  bottlesRemaining: null,
  location: '',
  notes: '',
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

describe('useVesselStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    global.fetch = vi.fn()
  })

  it('should have empty vessels array initially', () => {
    const store = useVesselStore()
    expect(store.vessels).toEqual([])
  })

  it('lists only unassigned kegs and leaves the current list intact', async () => {
    const store = useVesselStore()
    store.vessels = [{ id: 'existing' }]
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValueOnce(
        makePage([
          { ...VESSEL, id: 'empty-keg', status: 'empty', batchId: null },
          { ...VESSEL, id: 'assigned-keg', status: 'empty', batchId: 'b1' },
          { ...VESSEL, id: 'empty-fermenter', status: 'empty', vesselType: 'fermenter', batchId: null }
        ])
      )
    })

    const empty = await store.listEmptyKegs()

    expect(empty.map((vessel) => vessel.id)).toEqual(['empty-keg'])
    expect(store.vessels).toEqual([{ id: 'existing' }])
    expect(global.fetch.mock.calls[0][0]).toContain('status=empty')
  })

  describe('getVesselList', () => {
    it('fetches all vessels from a single page', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(makePage([VESSEL]))
      })

      const store = useVesselStore()
      const result = await store.getVesselList()

      expect(result).not.toBeNull()
      expect(store.vessels.length).toBe(1)
      expect(store.vessels[0].id).toBe('v1')
    })

    it('fetches all vessels across multiple pages', async () => {
      const page1 = { items: [VESSEL], pages: 2, total: 2, page: 1, page_size: 1 }
      const page2 = {
        items: [{ ...VESSEL, id: 'v2', name: 'Keg 2' }],
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

      const store = useVesselStore()
      const result = await store.getVesselList()

      expect(result).not.toBeNull()
      expect(store.vessels.length).toBe(2)
      expect(global.fetch).toHaveBeenCalledTimes(2)
    })

    it('returns null on fetch error', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 500 })

      const store = useVesselStore()
      const result = await store.getVesselList()

      expect(result).toBeNull()
    })

    it('applies batchId and status query params when provided', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(makePage([VESSEL]))
      })

      const store = useVesselStore()
      await store.getVesselList('b1', 'filled')

      const calledUrl = global.fetch.mock.calls[0][0]
      expect(calledUrl).toContain('batchId=b1')
      expect(calledUrl).toContain('status=filled')
    })

    it('returns null on network rejection', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const store = useVesselStore()
      const result = await store.getVesselList()

      expect(result).toBeNull()
    })
  })

  describe('getVessel', () => {
    it('fetches a vessel by id', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(VESSEL)
      })

      const store = useVesselStore()
      const result = await store.getVessel('v1')

      expect(result).not.toBeNull()
      expect(result.id).toBe('v1')
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/vessels/v1',
        expect.any(Object)
      )
    })

    it('returns null on non-ok response', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 404 })

      const store = useVesselStore()
      const result = await store.getVessel('v1')

      expect(result).toBeNull()
    })

    it('returns null on network rejection', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const store = useVesselStore()
      const result = await store.getVessel('v1')

      expect(result).toBeNull()
    })

    it('returns null for empty id', async () => {
      const store = useVesselStore()
      const result = await store.getVessel('')

      expect(result).toBeNull()
      expect(global.fetch).not.toHaveBeenCalled()
    })
  })

  describe('addVessel', () => {
    it('creates a new vessel and returns it', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: vi.fn().mockResolvedValueOnce({ ...VESSEL, id: 'v2' })
      })

      const store = useVesselStore()
      const vessel = { toJson: () => ({ ...VESSEL, id: '' }) }
      const result = await store.addVessel(vessel)

      expect(result).not.toBeNull()
      expect(result.id).toBe('v2')
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/vessels',
        expect.objectContaining({ method: 'POST' })
      )
    })

    it('returns null when status is not 201', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 400 })

      const store = useVesselStore()
      const vessel = { toJson: () => ({}) }
      const result = await store.addVessel(vessel)

      expect(result).toBeNull()
    })

    it('returns null on network rejection', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const store = useVesselStore()
      const vessel = { toJson: () => ({}) }
      const result = await store.addVessel(vessel)

      expect(result).toBeNull()
    })
  })

  describe('updateVessel', () => {
    it('updates a vessel and returns the updated object', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce({ ...VESSEL, name: 'Keg Updated' })
      })

      const store = useVesselStore()
      const vessel = { id: 'v1', toJson: () => ({ ...VESSEL, name: 'Keg Updated' }) }
      const result = await store.updateVessel(vessel)

      expect(result).not.toBeNull()
      expect(result.name).toBe('Keg Updated')
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/vessels/v1',
        expect.objectContaining({ method: 'PATCH' })
      )
    })

    it('returns null when status is not 200', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 422 })

      const store = useVesselStore()
      const vessel = { id: 'v1', toJson: () => ({}) }
      const result = await store.updateVessel(vessel)

      expect(result).toBeNull()
    })

    it('returns null on network rejection', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const store = useVesselStore()
      const vessel = { id: 'v1', toJson: () => ({}) }
      const result = await store.updateVessel(vessel)

      expect(result).toBeNull()
    })
  })

  describe('deleteVessel', () => {
    it('deletes a vessel and returns true on 204', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: true, status: 204 })

      const store = useVesselStore()
      const result = await store.deleteVessel('v1')

      expect(result).toBe(true)
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/vessels/v1',
        expect.objectContaining({ method: 'DELETE' })
      )
    })

    it('returns false when status is not 204', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 404 })

      const store = useVesselStore()
      const result = await store.deleteVessel('v1')

      expect(result).toBe(false)
    })

    it('returns false on network rejection', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const store = useVesselStore()
      const result = await store.deleteVessel('v1')

      expect(result).toBe(false)
    })
  })
  // regenerateToken was removed: vessels have no token. Integration/QR flows use the tap
  // token, which survives keg swaps — see spec-data-model.md §5.11.

  describe('assignTap', () => {
    it('assigns a tap to a vessel and returns updated vessel', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce({ ...VESSEL, tapId: 't1' })
      })

      const store = useVesselStore()
      const result = await store.assignTap('v1', 't1')

      expect(result).not.toBeNull()
      expect(result.tapId).toBe('t1')
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('vessels/v1'),
        expect.objectContaining({ method: 'PATCH' })
      )
    })

    it('sends only tapId in the body, so unrelated fields are left alone', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(VESSEL)
      })

      const store = useVesselStore()
      await store.assignTap('v1', 't2')

      // The server reads exclude_unset, so anything sent here is an assertion about
      // that field. Sending the whole vessel would let a stale value overwrite a
      // concurrent edit — and a stale null would silently unassign the batch.
      const body = JSON.parse(global.fetch.mock.calls[0][1].body)
      expect(body).toEqual({ tapId: 't2' })
    })

    it('returns null when status is not 200', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 400 })

      const store = useVesselStore()
      const result = await store.assignTap('v1', 't1')

      expect(result).toBeNull()
    })

    it('returns null on network rejection', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const store = useVesselStore()
      const result = await store.assignTap('v1', 't1')

      expect(result).toBeNull()
    })
  })

  describe('assignBatch', () => {
    it('assigns or clears a batch with a narrow payload', async () => {
      global.fetch = vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: vi.fn().mockResolvedValueOnce({ ...VESSEL, batchId: 'b2' })
        })
        .mockResolvedValueOnce({ ok: false, status: 409 })

      const store = useVesselStore()
      const assigned = await store.assignBatch('v1', 'b2')
      const rejected = await store.assignBatch('v1', null)

      expect(assigned.batchId).toBe('b2')
      expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual({ batchId: 'b2' })
      expect(rejected).toBeNull()
    })
  })

  describe('processEvent', () => {
    it('removes vessel on delete event', async () => {
      const store = useVesselStore()
      store.vessels = [
        { id: 'v1', name: 'Keg 1' },
        { id: 'v2', name: 'Keg 2' }
      ]

      await store.processEvent('delete', 'v1')

      expect(store.vessels.length).toBe(1)
      expect(store.vessels[0].id).toBe('v2')
    })

    it('does not modify vessels for invalid id on delete', async () => {
      const store = useVesselStore()
      store.vessels = [{ id: 'v1', name: 'Keg 1' }]

      await store.processEvent('delete', '')

      expect(store.vessels.length).toBe(1)
    })

    it('updates existing vessel on update event', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce({ ...VESSEL, id: 'v1', name: 'Keg Updated' })
      })

      const store = useVesselStore()
      store.vessels = [{ id: 'v1', name: 'Keg 1' }]

      await store.processEvent('update', 'v1')

      expect(store.vessels.length).toBe(1)
      expect(store.vessels[0].name).toBe('Keg Updated')
    })

    it('adds vessel if not in list on update event', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce({ ...VESSEL, id: 'v99', name: 'New Keg' })
      })

      const store = useVesselStore()
      store.vessels = []

      await store.processEvent('update', 'v99')

      expect(store.vessels.length).toBe(1)
    })

    it('adds vessel on create event', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce({ ...VESSEL, id: 'v3', name: 'New Keg' })
      })

      const store = useVesselStore()
      store.vessels = []

      await store.processEvent('create', 'v3')

      expect(store.vessels.length).toBe(1)
      expect(store.vessels[0].id).toBe('v3')
    })

    it('handles fetch failure gracefully on update event', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const store = useVesselStore()
      store.vessels = [{ id: 'v1', name: 'Keg 1' }]

      await store.processEvent('update', 'v1')

      expect(store.vessels.length).toBe(1)
    })

    it('handles fetch failure gracefully on create event', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const store = useVesselStore()
      store.vessels = []

      await store.processEvent('create', 'v99')

      expect(store.vessels.length).toBe(0)
    })
  })

  describe('vesselList getter', () => {
    it('returns the vessels array via getter', () => {
      const store = useVesselStore()
      store.vessels = [{ id: 'v1', name: 'Keg 1' }]

      expect(store.vesselList.length).toBe(1)
      expect(store.vesselList[0].id).toBe('v1')
    })
  })
})
