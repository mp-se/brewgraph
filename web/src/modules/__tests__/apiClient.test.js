/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

/*
 * apiClient is the only place that calls fetch, so the contract every caller relies on is pinned
 * here: each exported method sends the bearer token and reports a failed request the same way.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

vi.mock('@/ui', () => ({
  logDebug: vi.fn(),
  logError: vi.fn()
}))

vi.mock('@/modules/pinia', () => ({
  global: {
    apiURL: 'http://host/api/',
    baseURL: 'http://host/',
    token: 'Bearer test',
    fetchTimout: 5000,
    busyOperations: 0,
    get disabled() {
      return this.busyOperations > 0
    },
    acquireBusy() {
      this.busyOperations += 1
      let released = false
      return () => {
        if (released) return
        released = true
        this.busyOperations = Math.max(0, this.busyOperations - 1)
      }
    },
    messageError: ''
  }
}))

import { apiFetch, apiJson, apiOk } from '../apiClient'
import { global as g } from '@/modules/pinia'

const respond = (over = {}) => ({
  ok: true,
  status: 200,
  statusText: 'OK',
  json: async () => ({ a: 1 }),
  ...over
})

// Each method is called the same way so the shared guarantees are asserted once for all of them.
const methods = {
  apiFetch: (path) => apiFetch('GET', path),
  apiJson: (path) => apiJson('GET', path),
  apiOk: (path) => apiOk('GET', path)
}

describe('apiClient', () => {
  beforeEach(() => {
    g.busyOperations = 0
    g.messageError = ''
    global.fetch = vi.fn().mockResolvedValue(respond())
  })

  describe.each(Object.entries(methods))('%s', (name, call) => {
    it('sends the token to the api URL with a timeout', async () => {
      await call('batches')
      const [url, init] = global.fetch.mock.calls[0]
      expect(url).toBe('http://host/api/batches')
      expect(init.headers.Authorization).toBe('Bearer test')
      expect(init.signal).toBeInstanceOf(AbortSignal)
    })

    if (name === 'apiFetch') return // raw: status and body handling belong to the caller

    it('reports the server message and clears the busy flag on an error response', async () => {
      global.fetch.mockResolvedValue(
        respond({ ok: false, status: 400, json: async () => ({ message: 'Bad thing' }) })
      )
      await call('batches')
      expect(g.messageError).toBe('Bad thing')
      expect(g.disabled).toBe(false)
    })

    it('falls back to the status line when the error body is not JSON', async () => {
      global.fetch.mockResolvedValue(
        respond({
          ok: false,
          status: 500,
          statusText: 'Server Error',
          json: async () => {
            throw new Error('not json')
          }
        })
      )
      await call('batches')
      expect(g.messageError).toBe('500 Server Error')
    })

    it('reports a network failure with the method and path', async () => {
      global.fetch.mockRejectedValue(new Error('offline'))
      await call('batches')
      expect(g.messageError).toBe('GET batches failed')
      expect(g.disabled).toBe(false)
    })
  })

  it('apiJson returns the body on success and null on failure', async () => {
    expect(await apiJson('GET', 'x')).toEqual({ a: 1 })
    global.fetch.mockResolvedValue(respond({ ok: false, status: 500 }))
    expect(await apiJson('GET', 'x')).toBeNull()
  })

  it('apiOk returns whether the request succeeded', async () => {
    expect(await apiOk('DELETE', 'x')).toBe(true)
    global.fetch.mockResolvedValue(respond({ ok: false, status: 500 }))
    expect(await apiOk('DELETE', 'x')).toBe(false)
  })

  it('keeps the busy flag set until all overlapping API requests finish', async () => {
    const pendingResponses = []
    global.fetch = vi.fn(
      () =>
        new Promise((resolve) => {
          pendingResponses.push(resolve)
        })
    )

    const firstRequest = apiJson('GET', 'first')
    const secondRequest = apiOk('GET', 'second')
    expect(g.disabled).toBe(true)

    pendingResponses[0](respond())
    await firstRequest
    expect(g.disabled).toBe(true)

    pendingResponses[1](respond())
    await secondRequest
    expect(g.disabled).toBe(false)
  })

  it('sends a JSON body with a content type', async () => {
    await apiFetch('POST', 'x', { k: 1 })
    const [, init] = global.fetch.mock.calls[0]
    expect(init.method).toBe('POST')
    expect(init.body).toBe('{"k":1}')
    expect(init.headers['Content-Type']).toBe('application/json')
  })

  it('apiFetch takes a base URL, token and no timeout for the stream and backup callers', async () => {
    const signal = new AbortController().signal
    await apiFetch('GET', 'events', undefined, { baseURL: g.baseURL, signal })
    expect(global.fetch.mock.calls[0][0]).toBe('http://host/events')
    expect(global.fetch.mock.calls[0][1].signal).toBe(signal)

    await apiFetch('GET', 'http://other/api/x', undefined, {
      baseURL: '',
      token: 'Bearer other',
      timeout: false
    })
    const [url, init] = global.fetch.mock.calls[1]
    expect(url).toBe('http://other/api/x')
    expect(init.headers.Authorization).toBe('Bearer other')
    expect(init.signal).toBeUndefined()
  })
})
