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

/*
 * useEventStream — fetch-based Server-Sent Events composable.
 *
 * Replaces the previous WebSocket transport (`GET /api/system/ws`) with a
 * plain authenticated GET against `/events`.
 * Note the path sits OUTSIDE `/api`, so the URL is built from `baseURL`, not
 * `apiURL` (which appends `api/`) — see docs/spec-api.md. Uses `fetch` +
 * `ReadableStream` instead of native `EventSource` so the same `Authorization`
 * header used everywhere else in this app (see apiClient.ts) can be attached —
 * `EventSource` does not support custom headers.
 *
 * Reconnects automatically on network errors with exponential back-off
 * (1 s → 2 s … capped at 10 s).
 */
import { ref } from 'vue'
import { logDebug, logInfo } from '@/ui'
import { global, batchStore, deviceStore, tapStore, vesselStore } from '@/modules/pinia'
import { apiFetch } from '@/modules/apiClient'

type SseEvent = { method: string; table: string; id: string | null }

const BASE_BACKOFF_MS = 1_000
const MAX_BACKOFF_MS = 10_000

export function useEventStream() {
  const connected = ref(false)
  let abortController: AbortController | null = null
  let backoffMs = BASE_BACKOFF_MS
  let stopped = false

  function handleEvent(raw: string) {
    // SSE spec: each event block is separated by \n\n
    // Lines starting with ":" are comments (heartbeats) — skip them.
    for (const line of raw.split('\n')) {
      if (line.startsWith(':') || !line.startsWith('data:')) continue
      const json = line.slice('data:'.length).trim()
      if (!json) continue
      try {
        const event = JSON.parse(json) as SseEvent
        dispatch(event)
      } catch {
        // Malformed SSE data — ignore
      }
    }
  }

  function dispatch(ev: SseEvent) {
    logDebug('useEventStream.dispatch()', ev)
    // A restore refreshes the four entity lists once after its writes complete.
    // Applying every echo event meanwhile causes repeated list fetches and
    // shared busy-state changes, which visibly redraws the whole application.
    if (global.restoreInProgress) return
    const id = ev.id ?? ''
    if (ev.table == 'device') {
      deviceStore.processEvent(ev.method, id)
    } else if (ev.table == 'batch') {
      batchStore.processEvent(ev.method, id)
    } else if (ev.table == 'tap') {
      tapStore.processEvent(ev.method, id)
    } else if (ev.table == 'vessel') {
      vesselStore.processEvent(ev.method, id)
    } else if (ev.table == 'gravity') {
      global.updatedGravityData += 1
    } else if (ev.table == 'pressure') {
      global.updatedPressureData += 1
    } else if (ev.table == 'pour') {
      global.updatedPourData += 1
    }
  }

  async function connect() {
    if (!global.token) {
      logInfo('useEventStream.connect()', 'No API key found, event stream connection skipped')
      return
    }
    stopped = false
    run()
  }

  async function run() {
    while (!stopped) {
      abortController = new AbortController()
      try {
        const url = global.baseURL + 'events'
        logInfo('useEventStream.connect()', 'Event stream URL: ' + url)

        const response = await apiFetch('GET', 'events', undefined, {
          baseURL: global.baseURL,
          signal: abortController.signal
        })

        if (response.status === 401 || response.status === 403) {
          logInfo('useEventStream.connect()', 'Event stream authentication failed: ' + response.status)
          disconnect()
          return
        }

        if (!response.ok || !response.body) {
          throw new Error(`SSE connect failed: ${response.status}`)
        }

        connected.value = true
        backoffMs = BASE_BACKOFF_MS // reset on successful connect
        logInfo('useEventStream.connect()', 'Established event stream with server for notifications.')

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done || stopped) break
          buffer += decoder.decode(value, { stream: true })
          // Process complete event blocks (delimited by \n\n)
          const blocks = buffer.split('\n\n')
          buffer = blocks.pop() ?? '' // keep incomplete block in buffer
          for (const block of blocks) {
            if (block.trim()) handleEvent(block)
          }
        }
      } catch (err) {
        if (stopped) break
        const isAbort = err instanceof Error && (err.name === 'AbortError' || err.message.includes('abort'))
        if (!isAbort) {
          logInfo('useEventStream.connect()', `Event stream disconnected, retrying in ${backoffMs}ms: ${err}`)
        }
      } finally {
        connected.value = false
      }

      if (!stopped) {
        await sleep(backoffMs)
        backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF_MS)
      }
    }
  }

  function disconnect() {
    stopped = true
    abortController?.abort()
    connected.value = false
  }

  function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }

  return {
    connected,
    connect,
    disconnect
  }
}
