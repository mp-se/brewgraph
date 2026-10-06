/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import { describe, it, expect, vi } from 'vitest'

vi.mock('@/ui', () => ({
  logDebug: vi.fn()
}))

import { getConfigFetchStrategy, deviceConfigText } from '../deviceConfigFetch'

const envelope = (data) => ({
  schemaVersion: 1,
  kind: 'device-config',
  data,
  source: 'proxy_fetch',
  capturedAt: '2026-09-27T00:00:00Z'
})

describe('deviceConfigText', () => {
  const deviceJson = { mdns: 'gravmon', ble_tilt_color: 'red', config: { id: 'abc' } }
  const pretty = JSON.stringify(deviceJson, null, 2)

  it('returns an empty string when there is no config', () => {
    expect(deviceConfigText(null)).toBe('')
    expect(deviceConfigText(undefined)).toBe('')
    expect(deviceConfigText('')).toBe('')
  })

  it('shows the payload of a plain envelope', () => {
    expect(deviceConfigText(envelope(deviceJson))).toBe(pretty)
  })

  it('unpacks JSON the API stored as raw text', () => {
    expect(deviceConfigText(envelope({ raw: JSON.stringify(deviceJson) }))).toBe(pretty)
  })

  it('unpacks nested layers from a stringified envelope that was restored', () => {
    const restored = envelope({ raw: JSON.stringify(envelope(deviceJson)) })
    expect(deviceConfigText(restored)).toBe(pretty)
  })

  it('shows raw text that is not JSON as-is', () => {
    expect(deviceConfigText(envelope({ raw: 'ssid=brew&pass=x' }))).toBe('ssid=brew&pass=x')
  })

  it('keeps a device config that merely has a raw field among others', () => {
    const cfg = { raw: 'x', mdns: 'gravmon' }
    expect(deviceConfigText(envelope(cfg))).toBe(JSON.stringify(cfg, null, 2))
  })
})

describe('getConfigFetchStrategy', () => {
  it('returns fetchFormat=true for gravitymon', () => {
    expect(getConfigFetchStrategy('gravitymon')).toEqual({ fetchFormat: true })
  })

  it('returns fetchFormat=false for gravitymon_gateway', () => {
    expect(getConfigFetchStrategy('gravitymon_gateway')).toEqual({ fetchFormat: false })
  })

  it('returns fetchFormat=false for pressuremon', () => {
    expect(getConfigFetchStrategy('pressuremon')).toEqual({ fetchFormat: false })
  })

  it('returns fetchFormat=false for kegmon', () => {
    expect(getConfigFetchStrategy('kegmon')).toEqual({ fetchFormat: false })
  })

  it('returns fetchFormat=false for chamber_controller', () => {
    expect(getConfigFetchStrategy('chamber_controller')).toEqual({ fetchFormat: false })
  })

  it('returns null for an unregistered device type (e.g. ispindel, which never fetches config)', () => {
    expect(getConfigFetchStrategy('ispindel')).toBeNull()
  })

  it('returns null for an unknown device type', () => {
    expect(getConfigFetchStrategy('not_a_real_type')).toBeNull()
  })
})
