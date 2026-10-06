/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

/*
 * useEventStream is the only real-time path in the product — SSE, no WebSocket —
 * and it is hand-rolled: `fetch` + `ReadableStream` rather than native
 * `EventSource`, because EventSource cannot send an Authorization header. That
 * means this file owns its own stream buffering, event parsing, back-off and
 * reconnection, which is exactly the code that fails *silently*: the UI simply
 * stops updating, with no error and no failed request to notice.
 *
 * Only `connect`, `disconnect` and `connected` are exported, so everything here
 * drives the composable through its public surface and observes the effects on
 * the mocked stores — `handleEvent`/`dispatch` are reached by feeding bytes into
 * the stream, never by calling internals.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

vi.mock('@/ui', () => ({
  logDebug: vi.fn(),
  logInfo: vi.fn()
}))

// The composable imports these bindings directly (not via a store factory), so
// they are mocked as plain objects with spies rather than through setActivePinia.
vi.mock('@/modules/pinia', () => ({
  global: {
    apiURL: 'http://localhost:8080/api/',
    baseURL: 'http://localhost:8080/',
    token: 'Bearer test',
    restoreInProgress: false,
    updatedGravityData: 0,
    updatedPressureData: 0,
    updatedPourData: 0
  },
  batchStore: { processEvent: vi.fn() },
  deviceStore: { processEvent: vi.fn() },
  tapStore: { processEvent: vi.fn() },
  vesselStore: { processEvent: vi.fn() }
}))

import { useEventStream } from '../useEventStream'
import { global as g, batchStore, deviceStore, tapStore, vesselStore } from '@/modules/pinia'

/**
 * A stream whose reads resolve only when the test says so.
 *
 * Returning an already-resolved read would race the composable to `done` before
 * assertions could observe `connected`, so each `read()` parks until `emit()` or
 * `finish()` is called.
 */
function makeStream({ status = 200, ok = true, withBody = true } = {}) {
  let pending = null
  const encoder = new TextEncoder()
  const reader = {
    read: () =>
      new Promise((resolve) => {
        pending = resolve
      })
  }
  return {
    response: { status, ok, body: withBody ? { getReader: () => reader } : null },
    async emit(text) {
      pending({ done: false, value: encoder.encode(text) })
      await tick()
    },
    async finish() {
      pending({ done: true, value: undefined })
      await tick()
    }
  }
}

/** Flush pending microtasks and any timer due now (back-off sleeps included). */
const tick = async (ms = 0) => {
  await vi.advanceTimersByTimeAsync(ms)
}

/** One well-formed SSE block, as the server writes it. */
const block = (payload) => `data: ${JSON.stringify(payload)}\n\n`

describe('useEventStream', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    g.token = 'Bearer test'
    g.restoreInProgress = false
    g.updatedGravityData = 0
    g.updatedPressureData = 0
    g.updatedPourData = 0
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('initial state', () => {
    it('starts disconnected', () => {
      expect(useEventStream().connected.value).toBe(false)
    })
  })

  describe('connect', () => {
    it('does not open a stream when no token is present', async () => {
      g.token = ''
      global.fetch = vi.fn()

      const { connect, connected } = useEventStream()
      await connect()
      await tick()

      expect(global.fetch).not.toHaveBeenCalled()
      expect(connected.value).toBe(false)
    })

    it('sends the Authorization header to the events endpoint', async () => {
      const stream = makeStream()
      global.fetch = vi.fn().mockResolvedValue(stream.response)

      const { connect, disconnect } = useEventStream()
      connect()
      await tick()

      expect(global.fetch).toHaveBeenCalledTimes(1)
      const [url, opts] = global.fetch.mock.calls[0]
      expect(url).toBe('http://localhost:8080/events')
      expect(opts.headers.Authorization).toBe('Bearer test')

      disconnect()
    })

    it('reports connected once the response is accepted', async () => {
      const stream = makeStream()
      global.fetch = vi.fn().mockResolvedValue(stream.response)

      const { connect, connected, disconnect } = useEventStream()
      connect()
      await tick()

      expect(connected.value).toBe(true)

      disconnect()
    })
  })

  describe('event dispatch', () => {
    /** Bring a stream up and hand back its emitter. */
    async function connected() {
      const stream = makeStream()
      global.fetch = vi.fn().mockResolvedValue(stream.response)
      const es = useEventStream()
      es.connect()
      await tick()
      return { stream, es }
    }

    it.each([
      ['device', () => deviceStore.processEvent],
      ['batch', () => batchStore.processEvent],
      ['tap', () => tapStore.processEvent],
      ['vessel', () => vesselStore.processEvent]
    ])('routes a %s event to its store with method and id', async (table, spy) => {
      const { stream, es } = await connected()

      await stream.emit(block({ method: 'update', table, id: 'abc-123' }))

      expect(spy()).toHaveBeenCalledWith('update', 'abc-123')
      es.disconnect()
    })

    it.each([
      ['gravity', 'updatedGravityData'],
      ['pressure', 'updatedPressureData'],
      ['pour', 'updatedPourData']
    ])('increments the %s counter rather than calling a store', async (table, counter) => {
      const { stream, es } = await connected()

      await stream.emit(block({ method: 'create', table, id: null }))

      expect(g[counter]).toBe(1)
      expect(batchStore.processEvent).not.toHaveBeenCalled()
      es.disconnect()
    })

    it('passes an empty string when the event carries a null id', async () => {
      const { stream, es } = await connected()

      await stream.emit(block({ method: 'delete', table: 'device', id: null }))

      expect(deviceStore.processEvent).toHaveBeenCalledWith('delete', '')
      es.disconnect()
    })

    it('ignores restore echo events so progress updates do not redraw entity lists', async () => {
      const { stream, es } = await connected()
      g.restoreInProgress = true

      await stream.emit(
        block({ method: 'delete', table: 'device', id: 'device-1' }) +
          block({ method: 'create', table: 'batch', id: 'batch-1' }) +
          block({ method: 'create', table: 'gravity', id: null })
      )

      expect(deviceStore.processEvent).not.toHaveBeenCalled()
      expect(batchStore.processEvent).not.toHaveBeenCalled()
      expect(g.updatedGravityData).toBe(0)
      es.disconnect()
    })

    it('ignores a table it does not know without disturbing the stream', async () => {
      const { stream, es } = await connected()

      await stream.emit(block({ method: 'update', table: 'not_a_table', id: '1' }))
      await stream.emit(block({ method: 'update', table: 'batch', id: 'after' }))

      // The unknown event must not have aborted the reader — the next one lands.
      expect(batchStore.processEvent).toHaveBeenCalledWith('update', 'after')
      es.disconnect()
    })

    it('skips heartbeat comment lines', async () => {
      // Documentation rather than a guard, and deliberately kept as such: a
      // heartbeat is excluded three times over — it fails `startsWith(':')`, it
      // fails `startsWith('data:')`, and its payload is not JSON. Mutation testing
      // confirmed no single change to the source can make this fail. It earns its
      // place by pinning the intent for a future rewrite of the line filter, not by
      // detecting a regression today.
      const { stream, es } = await connected()

      await stream.emit(': heartbeat\n\n')

      expect(batchStore.processEvent).not.toHaveBeenCalled()
      expect(deviceStore.processEvent).not.toHaveBeenCalled()
      es.disconnect()
    })

    it('survives malformed JSON and keeps processing later events', async () => {
      const { stream, es } = await connected()

      await stream.emit('data: {not valid json\n\n')
      await stream.emit(block({ method: 'update', table: 'batch', id: 'ok' }))

      expect(batchStore.processEvent).toHaveBeenCalledTimes(1)
      expect(batchStore.processEvent).toHaveBeenCalledWith('update', 'ok')
      es.disconnect()
    })

    it('reassembles an event split across two chunks', async () => {
      const { stream, es } = await connected()
      const [head, tail] = ['data: {"method":"update","tab', 'le":"tap","id":"split"}\n\n']

      await stream.emit(head)
      expect(tapStore.processEvent).not.toHaveBeenCalled() // still buffered

      await stream.emit(tail)

      expect(tapStore.processEvent).toHaveBeenCalledWith('update', 'split')
      es.disconnect()
    })

    it('handles two events delivered in a single chunk', async () => {
      const { stream, es } = await connected()

      await stream.emit(
        block({ method: 'create', table: 'batch', id: 'one' }) +
          block({ method: 'delete', table: 'batch', id: 'two' })
      )

      expect(batchStore.processEvent).toHaveBeenCalledTimes(2)
      expect(batchStore.processEvent).toHaveBeenNthCalledWith(1, 'create', 'one')
      expect(batchStore.processEvent).toHaveBeenNthCalledWith(2, 'delete', 'two')
      es.disconnect()
    })
  })

  describe('failure handling', () => {
    it.each([401, 403])('stops permanently on %d rather than retrying', async (status) => {
      global.fetch = vi.fn().mockResolvedValue({ status, ok: false, body: null })

      const { connect, connected } = useEventStream()
      connect()
      await tick()

      expect(connected.value).toBe(false)

      // Well past the 1 s base back-off: an auth failure must not come back.
      await tick(30_000)
      expect(global.fetch).toHaveBeenCalledTimes(1)
    })

    it('retries after back-off when the server rejects the connection', async () => {
      const stream = makeStream()
      global.fetch = vi
        .fn()
        .mockResolvedValueOnce({ status: 500, ok: false, body: null })
        .mockResolvedValue(stream.response)

      const { connect, connected, disconnect } = useEventStream()
      connect()
      await tick()

      expect(connected.value).toBe(false)
      expect(global.fetch).toHaveBeenCalledTimes(1)

      await tick(1_000) // BASE_BACKOFF_MS

      expect(global.fetch).toHaveBeenCalledTimes(2)
      expect(connected.value).toBe(true)

      disconnect()
    })

    it('reconnects after the stream ends cleanly', async () => {
      const first = makeStream()
      const second = makeStream()
      global.fetch = vi
        .fn()
        .mockResolvedValueOnce(first.response)
        .mockResolvedValue(second.response)

      const { connect, connected, disconnect } = useEventStream()
      connect()
      await tick()

      await first.finish()
      expect(connected.value).toBe(false)

      await tick(1_000)

      expect(global.fetch).toHaveBeenCalledTimes(2)
      expect(connected.value).toBe(true)

      disconnect()
    })
  })

  describe('disconnect', () => {
    it('clears connected and aborts the in-flight request', async () => {
      const stream = makeStream()
      global.fetch = vi.fn().mockResolvedValue(stream.response)

      const { connect, connected, disconnect } = useEventStream()
      connect()
      await tick()
      const { signal } = global.fetch.mock.calls[0][1]
      expect(signal.aborted).toBe(false)

      disconnect()

      expect(connected.value).toBe(false)
      expect(signal.aborted).toBe(true)
    })

    it('does not reconnect after being disconnected', async () => {
      const stream = makeStream()
      global.fetch = vi.fn().mockResolvedValue(stream.response)

      const { connect, disconnect } = useEventStream()
      connect()
      await tick()
      disconnect()

      // Long enough for several back-off cycles had the loop kept running.
      await tick(30_000)

      expect(global.fetch).toHaveBeenCalledTimes(1)
    })
  })
})
