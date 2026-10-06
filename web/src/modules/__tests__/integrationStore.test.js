/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useIntegrationStore } from '@/modules/integrationStore'
import { Integration } from '@/modules/classes'

vi.mock('@/ui', () => ({ logDebug: vi.fn(), logError: vi.fn(), logInfo: vi.fn() }))

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
    fetchTimout: 30000
  }
}))

const integrationJson = (overrides = {}) => ({
  id: 'integration-1',
  name: 'Forward gravity',
  measurement: 'gravity',
  type: 'custom_forward',
  enabled: true,
  config: { url: 'https://example.test/ingest', method: 'POST', headers: {}, template: null },
  ...overrides
})

describe('useIntegrationStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    global.fetch = vi.fn()
  })

  it('loads and exposes integrations', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true, status: 200, json: async () => [integrationJson()] })
    const store = useIntegrationStore()

    const result = await store.getIntegrationList()

    expect(result).toHaveLength(1)
    expect(store.integrationList[0].name).toBe('Forward gravity')
    expect(result[0].name).toBe('Forward gravity')
  })

  it('returns null if the list request fails', async () => {
    global.fetch.mockResolvedValueOnce({ ok: false, status: 500 })
    expect(await useIntegrationStore().getIntegrationList()).toBeNull()
  })

  it('creates and appends an integration', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => integrationJson()
    })
    const store = useIntegrationStore()

    const result = await store.addIntegration(new Integration({ name: 'Forward gravity' }))

    expect(result?.name).toBe('Forward gravity')
    expect(store.integrations).toHaveLength(1)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8080/api/integrations',
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('returns null when creation fails', async () => {
    global.fetch.mockResolvedValueOnce({ ok: false, status: 422 })
    expect(await useIntegrationStore().addIntegration(new Integration())).toBeNull()
  })

  it('updates an existing integration in place', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => integrationJson({ name: 'Updated' })
    })
    const store = useIntegrationStore()
    store.integrations = [Integration.fromJson(integrationJson())]

    const updated = await store.updateIntegration('integration-1', { enabled: false })

    expect(updated?.name).toBe('Updated')
    expect(store.integrations[0].name).toBe('Updated')
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8080/api/integrations/integration-1',
      expect.objectContaining({ method: 'PATCH' })
    )
  })

  it('returns the updated integration even when it was not already in state', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => integrationJson()
    })
    const store = useIntegrationStore()

    expect(await store.updateIntegration('integration-1', {})).not.toBeNull()
    expect(store.integrations).toEqual([])
  })

  it('returns null when update fails', async () => {
    global.fetch.mockResolvedValueOnce({ ok: false, status: 409 })
    expect(await useIntegrationStore().updateIntegration('integration-1', {})).toBeNull()
  })

  it('deletes an integration from state after a successful response', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true, status: 204 })
    const store = useIntegrationStore()
    store.integrations = [Integration.fromJson(integrationJson())]

    expect(await store.deleteIntegration('integration-1')).toBe(true)
    expect(store.integrations).toEqual([])
  })

  it('leaves state unchanged when deletion fails', async () => {
    global.fetch.mockResolvedValueOnce({ ok: false, status: 404 })
    const store = useIntegrationStore()
    store.integrations = [Integration.fromJson(integrationJson())]

    expect(await store.deleteIntegration('integration-1')).toBe(false)
    expect(store.integrations).toHaveLength(1)
  })

  it('reports the test outcome and refreshes integrations', async () => {
    global.fetch
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ outcome: 'delivered' }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [integrationJson()] })

    expect(await useIntegrationStore().testIntegration('integration-1')).toBe('delivered')
    expect(global.fetch).toHaveBeenCalledTimes(2)
  })

  it('returns a null outcome for a successful test with no outcome field', async () => {
    global.fetch
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })

    expect(await useIntegrationStore().testIntegration('integration-1')).toBeNull()
  })

  it('returns null and does not refresh when the test request fails', async () => {
    global.fetch.mockResolvedValueOnce({ ok: false, status: 502 })

    expect(await useIntegrationStore().testIntegration('integration-1')).toBeNull()
    expect(global.fetch).toHaveBeenCalledTimes(1)
  })
})
