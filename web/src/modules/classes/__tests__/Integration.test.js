/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { describe, expect, it } from 'vitest'
import {
  INTEGRATION_TYPE_BREWFATHER_FORWARD,
  INTEGRATION_TYPE_CUSTOM_FORWARD,
  INTEGRATION_TYPE_ISPINDEL_FORWARD,
  Integration,
  integrationTypeOptionsFor,
  MEASUREMENT_GRAVITY,
  MEASUREMENT_POUR,
  MEASUREMENT_PRESSURE,
  MEASUREMENT_TEMP
} from '@/modules/classes'

describe('Integration', () => {
  it('applies safe defaults when constructed with no data', () => {
    const integration = new Integration()
    expect(integration.toJson()).toEqual({
      name: '',
      measurement: MEASUREMENT_GRAVITY,
      type: INTEGRATION_TYPE_ISPINDEL_FORWARD,
      enabled: true,
      config: { url: '' }
    })
    expect(integration.consecutiveFailures).toBe(0)
    expect(integration.version).toBe(1)
  })

  it('uses configured values and preserves failure metadata during deserialization', () => {
    const integration = Integration.fromJson({
      id: 'id-1', name: 'Forwarder', measurement: 'pressure', type: 'custom_forward',
      enabled: false,
      config: { url: 'https://example.test', method: 'PUT', headers: { token: 'secret' }, template: 'p=${pressure}' },
      createdAt: 'created', updatedAt: 'updated', consecutiveFailures: 3,
      lastSuccessAt: 'success', lastFailureAt: 'failure', lastFailureCode: 'timeout',
      disabledReason: 'paused after repeated failures', version: 7
    })

    expect(integration.id).toBe('id-1')
    expect(integration.createdAt).toBe('created')
    expect(integration.updatedAt).toBe('updated')
    expect(integration.consecutiveFailures).toBe(3)
    expect(integration.lastSuccessAt).toBe('success')
    expect(integration.lastFailureAt).toBe('failure')
    expect(integration.lastFailureCode).toBe('timeout')
    expect(integration.disabledReason).toBe('paused after repeated failures')
    expect(integration.version).toBe(7)
    expect(integration.toJson().config).toEqual({
      url: 'https://example.test', method: 'PUT', headers: { token: 'secret' }, template: 'p=${pressure}'
    })
  })

  it('omits custom-only config from built-in forwarders', () => {
    const integration = new Integration({
      type: INTEGRATION_TYPE_ISPINDEL_FORWARD,
      config: { url: 'https://example.test', method: 'PUT', headers: { token: 'secret' }, template: 'ignored' }
    })
    expect(integration.toJson().config).toEqual({ url: 'https://example.test' })
  })

  it('supports editing the mutable fields', () => {
    const integration = new Integration()
    integration.name = 'New name'
    integration.measurement = 'temperature'
    integration.type = INTEGRATION_TYPE_CUSTOM_FORWARD
    integration.enabled = false
    integration.config = { url: 'https://new.test', method: 'POST', headers: {}, template: null }

    expect(integration.name).toBe('New name')
    expect(integration.measurement).toBe('temperature')
    expect(integration.type).toBe(INTEGRATION_TYPE_CUSTOM_FORWARD)
    expect(integration.enabled).toBe(false)
    expect(integration.config.url).toBe('https://new.test')
  })

  it('tolerates absent config and metadata fields from older API payloads', () => {
    const integration = Integration.fromJson({ id: 'old-id', config: null })
    expect(integration.id).toBe('old-id')
    expect(integration.config).toEqual({ url: '', method: 'POST', headers: {}, template: null })
    expect(integration.lastFailureCode).toBeNull()
    expect(integration.disabledReason).toBeNull()
  })

  it('names the Brewfather type for what it sends, its custom stream', () => {
    const labels = integrationTypeOptionsFor(MEASUREMENT_GRAVITY).map((option) => option.label)
    expect(labels).toContain('Brewfather custom stream')
    expect(labels).not.toContain('Brewfather forward')
    expect(
      integrationTypeOptionsFor(MEASUREMENT_GRAVITY).find((option) => option.value === INTEGRATION_TYPE_BREWFATHER_FORWARD)
        ?.label
    ).toBe('Brewfather custom stream')
  })

  it('offers pressure and temperature Brewfather custom stream and Custom, pour only Custom', () => {
    const labels = (measurement) =>
      integrationTypeOptionsFor(measurement).map((option) => option.label)
    expect(labels(MEASUREMENT_GRAVITY)).toEqual([
      'iSpindel forward',
      'Brewfather custom stream',
      'Custom'
    ])
    expect(labels(MEASUREMENT_PRESSURE)).toEqual(['Brewfather custom stream', 'Custom'])
    expect(labels(MEASUREMENT_TEMP)).toEqual(['Brewfather custom stream', 'Custom'])
    expect(labels(MEASUREMENT_POUR)).toEqual(['Custom'])
  })
})
