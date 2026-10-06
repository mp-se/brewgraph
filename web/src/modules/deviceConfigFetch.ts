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

import { logDebug } from '@/ui'
import { logError } from '@/ui'
import { detectDeviceType, detectMdns, detectPlatform } from '@/modules/detect'
import {
  DEVICE_TYPE_GRAVITYMON,
  DEVICE_TYPE_GRAVITYMON_GW,
  DEVICE_TYPE_KEGMON,
  DEVICE_TYPE_CHAMBER_CONTROLLER,
  DEVICE_TYPE_PRESSUREMON
} from '@/modules/classes'

/**
 * A config-fetch strategy describes how the espframework config-fetch
 * protocol (spec-devices.md §"Config fetch protocol") applies to a given
 * device type / firmware generation. Every registered strategy today speaks
 * the same v1 protocol — GET status → GET config[Bearer id] → GET
 * feature[Bearer id] → optional GET format[Bearer id] — so the only thing
 * that currently varies is whether the format step exists.
 *
 * This is a registry, not a branch inside the fetch function, so a future
 * firmware generation is a new entry here rather than another device-type
 * check inline (same import-time registration pattern as the ingest handler
 * registry — spec-extension-points.md §6.1/§6.2).
 */
export interface DeviceConfigFetchStrategy {
  /** GET {url}api/format is only meaningful on Gravitymon firmware today. */
  fetchFormat: boolean
}

const CONFIG_FETCH_STRATEGIES: Record<string, DeviceConfigFetchStrategy> = {
  [DEVICE_TYPE_GRAVITYMON]: { fetchFormat: true },
  [DEVICE_TYPE_GRAVITYMON_GW]: { fetchFormat: false },
  [DEVICE_TYPE_PRESSUREMON]: { fetchFormat: false },
  [DEVICE_TYPE_KEGMON]: { fetchFormat: false },
  [DEVICE_TYPE_CHAMBER_CONTROLLER]: { fetchFormat: false }
}

/** Returns the fetch strategy for a device type, or null if unregistered. */
export function getConfigFetchStrategy(deviceType: string): DeviceConfigFetchStrategy | null {
  if (Object.prototype.hasOwnProperty.call(CONFIG_FETCH_STRATEGIES, deviceType)) {
    logDebug('deviceConfigFetch.getConfigFetchStrategy()', deviceType)
    return CONFIG_FETCH_STRATEGIES[deviceType]
  }
  return null
}

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v)

const parseOrKeep = (s: string): unknown => {
  try {
    return JSON.parse(s)
  } catch {
    return s
  }
}

/**
 * Peel one storage layer off a stored device config, or return it unchanged.
 *
 * The API keeps `config` in the standard `{kind, data}` envelope, and anything it
 * cannot store as an object — a firmware answering with text, or a config that
 * arrived as a JSON string (BrewLogger imports, restored backups) — as
 * `{raw: "<text>"}` inside that envelope.
 */
function unwrapConfigLayer(value: unknown): unknown {
  if (typeof value === 'string') return parseOrKeep(value)
  if (!isRecord(value)) return value
  if ('kind' in value && 'data' in value) return value.data
  const keys = Object.keys(value)
  if (keys.length === 1 && typeof value.raw === 'string') return parseOrKeep(value.raw)
  return value
}

/**
 * The device's own configuration as display text: every envelope and `raw`
 * wrapper removed, pretty-printed when it is JSON. Layers can nest — a config
 * stringified into a backup and restored comes back as an envelope holding
 * `raw` text of the previous envelope — so unwrap until nothing changes.
 */
export function deviceConfigText(stored: unknown): string {
  if (stored === null || stored === undefined || stored === '') return ''
  let value: unknown = stored
  for (let depth = 0; depth < 10; depth++) {
    const next = unwrapConfigLayer(value)
    if (next === value) break
    value = next
  }
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2)
}

/** Fetches and applies the espframework v1 configuration protocol to a device. */
type ConfigFetchDevice = {
  url: string
  mdns?: string
  chipFamily?: string
  deviceType?: string
  deviceColor?: string
  config?: unknown
}

type ProxyRequest = (
  method: 'GET',
  url: string,
  authorization: string,
  body: string,
  options?: { noErrorNotify?: boolean }
) => Promise<unknown>

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

export async function fetchDeviceConfigV1(
  device: ConfigFetchDevice,
  proxyRequest: ProxyRequest,
  onError: (message: string) => void
): Promise<boolean> {
  try {
    const data: Record<string, unknown> = {}

    const status = await proxyRequest('GET', device.url + 'api/status', '', '')
    logDebug('DeviceView.fetchConfigEspFwkV1()', '/status', status)
    if (!isObject(status)) return false
    data.status = status
    device.mdns = detectMdns(status)
    device.chipFamily = detectPlatform(status)
    device.deviceType = detectDeviceType(status)

    const authorization = 'Authorization: Bearer ' + status.id
    const config = await proxyRequest('GET', device.url + 'api/config', authorization, '')
    logDebug('DeviceView.fetchConfigEspFwkV1()', '/config', config)
    if (!isObject(config)) return false
    data.config = config

    const feature = await proxyRequest(
      'GET',
      device.url + 'api/feature',
      authorization,
      '',
      { noErrorNotify: true }
    )
    logDebug('DeviceView.fetchConfigEspFwkV1()', '/feature', feature)
    if (isObject(feature)) {
      data.feature = feature
      device.chipFamily = detectPlatform(feature)
    }

    if (typeof config.ble_tilt_color === 'string') device.deviceColor = config.ble_tilt_color

    if (getConfigFetchStrategy(device.deviceType)?.fetchFormat) {
      const format = await proxyRequest('GET', device.url + 'api/format', authorization, '')
      logDebug('DeviceView.fetchConfigEspFwkV1()', '/format', format)
      data.format = format
    }

    device.config = { fetchedAt: new Date().toISOString(), ...data }
    return true
  } catch (err) {
    logError('DeviceView.fetchConfigEspFwkV1()', err)
    onError('Error when trying to retrive data from device')
    return false
  }
}
