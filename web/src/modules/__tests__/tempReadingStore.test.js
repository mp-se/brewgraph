/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useTempReadingStore } from '@/modules/tempReadingStore'

const { globalMock } = vi.hoisted(() => ({
  globalMock: {
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

vi.mock('@/ui', () => ({ logDebug: vi.fn(), logError: vi.fn(), logInfo: vi.fn() }))
vi.mock('@/modules/pinia', () => ({ global: globalMock }))

const page = (items, hasMore = false, nextCursor = null) => ({
  items,
  hasMore,
  nextCursor
})

describe('useTempReadingStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    globalMock.disabled = false
    global.fetch = vi.fn()
  })

  it('starts with an empty reading list', () => {
    expect(useTempReadingStore().readings).toEqual([])
  })

  it('loads all cursor pages and clears the busy state', async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => page([{ id: 1, temperature: 18.5 }], true, 'next-page')
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => page([{ id: 2, temperature: 19.25 }])
      })
    const store = useTempReadingStore()

    const readings = await store.getTempListForBatch('batch-1', 25)

    expect(readings.map((reading) => reading.id)).toEqual([1, 2])
    expect(store.readings).toEqual(readings)
    expect(global.fetch).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining('batches/batch-1/temp?limit=25'),
      expect.objectContaining({ method: 'GET' })
    )
    expect(global.fetch).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('cursor=next-page'),
      expect.objectContaining({ method: 'GET' })
    )
    expect(globalMock.disabled).toBe(false)
  })

  it('uses the default page limit', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => page([])
    })

    expect(await useTempReadingStore().getTempListForBatch('batch-1')).toEqual([])
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('limit=500'),
      expect.any(Object)
    )
  })

  it('returns null and clears busy state when an API request fails', async () => {
    global.fetch.mockResolvedValueOnce({ ok: false, status: 503 })

    expect(await useTempReadingStore().getTempListForBatch('batch-1')).toBeNull()
    expect(globalMock.disabled).toBe(false)
  })

  it('returns null and clears busy state when the network rejects', async () => {
    global.fetch.mockRejectedValueOnce(new Error('network error'))

    expect(await useTempReadingStore().getTempListForBatch('batch-1')).toBeNull()
    expect(globalMock.disabled).toBe(false)
  })
})
