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
 * Client-side Integration payload preview — plain TypeScript, framework-free
 * (architecture.md §7: the one piece of frontend logic vendored as a single file into
 * both products instead of duplicated by hand).
 *
 * Mirrors `api/oss/jobs/gravity_forward.py`'s `_ispindel_payload`/`_brewfather_payload`/
 * `_render_template` (and its pressure/pour/temp siblings' `_template_values`) exactly,
 * so the preview never disagrees with what the backend actually sends. Renders against
 * one fixed, deterministic dummy reading per measurement — never "now" or random. Never
 * touches `config.url`: this is a pure computation, no network call.
 */

export type Measurement = 'gravity' | 'pressure' | 'pour' | 'temp'

// Must stay identical to _DUMMY_READINGS in api/oss/services/integration.py: "Send test payload"
// sends this same reading through the real server-side builders.
export const DUMMY_READINGS = {
  gravity: {
    gravity: 1.042,
    temperature: 20.5,
    angle: 45.2,
    velocity: 0.15,
    battery: 3.98,
    rssi: -62,
    deviceName: 'Fermenter 1',
    deviceId: '00000000-0000-0000-0000-000000000001',
    chipId: 'a1b2c3',
    batchId: '00000000-0000-0000-0000-000000000002',
    timestamp: '2026-01-01T12:00:00+00:00'
  },
  pressure: {
    pressure: 12.5,
    temperature: 4.0,
    battery: 3.98,
    rssi: -62,
    deviceName: 'Fermenter 1',
    deviceId: '00000000-0000-0000-0000-000000000001',
    chipId: 'a1b2c3',
    batchId: '00000000-0000-0000-0000-000000000002',
    timestamp: '2026-01-01T12:00:00+00:00'
  },
  temp: {
    temperature: 18.5,
    tempType: 'beer',
    battery: 3.98,
    rssi: -62,
    deviceName: 'Fermenter 1',
    deviceId: '00000000-0000-0000-0000-000000000001',
    chipId: 'a1b2c3',
    batchId: '00000000-0000-0000-0000-000000000002',
    timestamp: '2026-01-01T12:00:00+00:00'
  },
  pour: {
    pourAmount: 0.33,
    volumeRemaining: 12.4,
    tapId: '00000000-0000-0000-0000-000000000003',
    tapName: 'Tap 1',
    vesselId: '00000000-0000-0000-0000-000000000004',
    batchId: '00000000-0000-0000-0000-000000000002',
    timestamp: '2026-01-01T12:00:00+00:00'
  }
} as const

export const TEMPLATE_TOKENS_BY_MEASUREMENT: Record<Measurement, readonly string[]> = {
  gravity: [
    'gravity',
    'temperature',
    'angle',
    'velocity',
    'battery',
    'rssi',
    'deviceName',
    'deviceId',
    'chipId',
    'batchId',
    'timestamp'
  ],
  pressure: [
    'pressure',
    'temperature',
    'battery',
    'rssi',
    'deviceName',
    'deviceId',
    'chipId',
    'batchId',
    'timestamp'
  ],
  temp: [
    'temperature',
    'tempType',
    'battery',
    'rssi',
    'deviceName',
    'deviceId',
    'chipId',
    'batchId',
    'timestamp'
  ],
  pour: ['pourAmount', 'volumeRemaining', 'tapId', 'tapName', 'vesselId', 'batchId', 'timestamp']
}

/**
 * A complete JSON request body to start a `custom_forward` template from, per measurement: every
 * token the measurement offers, so the user deletes what they do not want instead of looking up
 * what exists. After the `${key}` substitution it is valid JSON (number tokens are not quoted,
 * string tokens are), so it also fits a JSON stream such as Brewfather's custom stream.
 */
export const TEMPLATE_EXAMPLES: Record<Measurement, string> = {
  gravity: `{
  "name": "\${deviceName}",
  "deviceId": "\${deviceId}",
  "chipId": "\${chipId}",
  "batchId": "\${batchId}",
  "gravity": \${gravity},
  "temperature": \${temperature},
  "angle": \${angle},
  "velocity": \${velocity},
  "battery": \${battery},
  "rssi": \${rssi},
  "timestamp": "\${timestamp}"
}`,
  pressure: `{
  "name": "\${deviceName}",
  "deviceId": "\${deviceId}",
  "chipId": "\${chipId}",
  "batchId": "\${batchId}",
  "pressure": \${pressure},
  "temperature": \${temperature},
  "battery": \${battery},
  "rssi": \${rssi},
  "timestamp": "\${timestamp}"
}`,
  temp: `{
  "name": "\${deviceName}",
  "deviceId": "\${deviceId}",
  "chipId": "\${chipId}",
  "batchId": "\${batchId}",
  "temperature": \${temperature},
  "tempType": "\${tempType}",
  "battery": \${battery},
  "rssi": \${rssi},
  "timestamp": "\${timestamp}"
}`,
  pour: `{
  "tapId": "\${tapId}",
  "tapName": "\${tapName}",
  "vesselId": "\${vesselId}",
  "batchId": "\${batchId}",
  "pourAmount": \${pourAmount},
  "volumeRemaining": \${volumeRemaining},
  "timestamp": "\${timestamp}"
}`
}

export type TemplateToken = (typeof TEMPLATE_TOKENS_BY_MEASUREMENT)[Measurement][number]

export interface IntegrationConfigInput {
  url: string
  method?: 'POST' | 'GET'
  headers?: Record<string, string>
  template?: string | null
}

export interface IntegrationPreview {
  method: string
  headers: Record<string, string>
  /** An object when the request body is JSON (`bodyIsJson`), otherwise raw text
   * (a `custom_forward` GET query string, or a `custom_forward` POST template
   * that didn't parse as JSON). */
  body: unknown
  bodyIsJson: boolean
}

// The reading does not store how often the device reports, so the iSpindel payload carries a
// fixed interval; 900 s is what external services expect. Mirrors
// ISPINDEL_FORWARD_INTERVAL_SECONDS in oss/jobs/gravity_forward.py.
const ISPINDEL_FORWARD_INTERVAL_SECONDS = 900

function ispindelPayload(reading: typeof DUMMY_READINGS.gravity): Record<string, unknown> {
  // Mirrors _ispindel_payload() in oss/jobs/gravity_forward.py: the original iSpindel format,
  // `ID` is the chip id, never a token. The server leaves out a key whose value is missing;
  // the dummy reading has every value, so nothing is left out here.
  return {
    name: reading.deviceName,
    ID: reading.chipId,
    angle: reading.angle,
    temperature: reading.temperature,
    temp_units: 'C',
    battery: reading.battery,
    gravity: reading.gravity,
    interval: ISPINDEL_FORWARD_INTERVAL_SECONDS,
    RSSI: reading.rssi
  }
}

function brewfatherPayload(reading: typeof DUMMY_READINGS.gravity): Record<string, unknown> {
  // Mirrors _brewfather_payload() in oss/jobs/gravity_forward.py: Brewfather's custom stream
  // format. battery/angle/rssi are sent only when the reading has them; the dummy reading does.
  // The name gets `[SG]` appended unless it has it: that tells Brewfather the gravity is SG.
  const name = reading.deviceName || ''
  return {
    name: name.includes('[SG]') ? name : name + '[SG]',
    temp: reading.temperature,
    temp_unit: 'C',
    gravity: reading.gravity,
    gravity_unit: 'G',
    battery: reading.battery,
    angle: reading.angle,
    rssi: reading.rssi
  }
}

function brewfatherPressurePayload(
  reading: typeof DUMMY_READINGS.pressure
): Record<string, unknown> {
  // Mirrors _brewfather_payload() in oss/jobs/pressure_forward.py: the device name as is (no
  // `[SG]`), pressure in kPa (`KPA`), and the reading's own temperature. The server leaves out
  // a key whose value is missing; the dummy reading has every value.
  return {
    name: reading.deviceName,
    pressure: reading.pressure,
    pressure_unit: 'KPA',
    temp: reading.temperature,
    temp_unit: 'C',
    battery: reading.battery,
    rssi: reading.rssi
  }
}

function brewfatherTempPayload(reading: typeof DUMMY_READINGS.temp): Record<string, unknown> {
  // Mirrors _brewfather_payload() in oss/jobs/temp_forward.py: the device name as is (no `[SG]`)
  // and the temperature in Celsius.
  return {
    name: reading.deviceName,
    temp: reading.temperature,
    temp_unit: 'C',
    battery: reading.battery,
    rssi: reading.rssi
  }
}

function brewfatherPayloadFor(
  measurement: Measurement,
  deviceName?: string
): Record<string, unknown> {
  if (measurement === 'pressure') {
    return brewfatherPressurePayload(dummyReading('pressure', deviceName))
  }
  if (measurement === 'temp') return brewfatherTempPayload(dummyReading('temp', deviceName))
  return brewfatherPayload(dummyReading('gravity', deviceName))
}

/** The measurement's dummy reading, with `deviceName` in place of the fixed `Fermenter 1` when
 * given and not blank. A pour carries no device, so it is returned unchanged. */
function dummyReading<M extends Measurement>(
  measurement: M,
  deviceName?: string
): (typeof DUMMY_READINGS)[M] {
  const reading = DUMMY_READINGS[measurement]
  const name = deviceName?.trim()
  return name && 'deviceName' in reading ? { ...reading, deviceName: name } : reading
}

/**
 * Plain `${key}` string substitution — deliberately not a template engine, mirroring
 * `_render_template()`/`_template_values()` in `oss/jobs/gravity_forward.py` and its
 * pressure/pour/temp siblings (the string is user-supplied and rendered server-side on
 * every forward, so it stays a fixed-token string replace). Token set and dummy values
 * both depend on `measurement` — defaults to `gravity` for existing callers. The server renders a
 * missing number as `null` and missing text as an empty string; the dummy readings are
 * complete, so the preview never needs that case.
 */
export function renderTemplate(
  template: string,
  measurement: Measurement = 'gravity',
  deviceName?: string
): string {
  const values = dummyReading(measurement, deviceName) as Record<string, unknown>
  let result = template
  for (const key of TEMPLATE_TOKENS_BY_MEASUREMENT[measurement]) {
    result = result.split(`\${${key}}`).join(String(values[key]))
  }
  return result
}

/**
 * Render the request BrewGraph would send for this integration `measurement`/`type`/
 * `config`, against that measurement's fixed dummy reading. Pure client-side, no
 * network call, never reads `config.url`. Mirrors `_forward()`/`_post_built_in()`/
 * `_post_custom()` in `oss/jobs/gravity_forward.py` and the pressure/temp siblings'
 * `_brewfather_payload()` (ispindel_forward is gravity-only).
 */
export function previewIntegration(
  type: string,
  config: IntegrationConfigInput,
  measurement: Measurement = 'gravity',
  deviceName?: string
): IntegrationPreview {
  if (type === 'custom_forward') {
    const rendered = renderTemplate(config.template ?? '', measurement, deviceName)
    const headers = { ...(config.headers ?? {}) }
    const method = config.method ?? 'POST'

    if (method === 'GET') {
      return { method, headers, body: rendered, bodyIsJson: false }
    }

    try {
      return { method, headers, body: JSON.parse(rendered), bodyIsJson: true }
    } catch {
      return { method, headers, body: rendered, bodyIsJson: false }
    }
  }

  const payload =
    type === 'ispindel_forward'
      ? ispindelPayload(dummyReading('gravity', deviceName))
      : brewfatherPayloadFor(measurement, deviceName)
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: payload,
    bodyIsJson: true
  }
}
