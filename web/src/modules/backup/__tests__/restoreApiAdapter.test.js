/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFetch } from '@/modules/apiClient'
import { apiDelete, apiGet, apiPatch, apiPost, fetchAllIds } from '../restoreApiAdapter'

vi.mock('@/modules/apiClient', () => ({ apiFetch: vi.fn() }))

const response = (data, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: vi.fn().mockResolvedValue(data)
})

describe('restoreApiAdapter', () => {
  beforeEach(() => vi.clearAllMocks())

  it('sends each HTTP method with the explicit restore credentials and no timeout', async () => {
    apiFetch.mockResolvedValue(response([]))

    await apiGet('/devices', 'restore-token')
    await apiPost('/devices', 'restore-token', { name: 'sensor' })
    await apiPatch('/devices/1', 'restore-token', { name: 'updated' })
    await apiDelete('/devices/1', 'restore-token')

    expect(apiFetch).toHaveBeenNthCalledWith(1, 'GET', '/devices', undefined, {
      baseURL: '', token: 'restore-token', timeout: false
    })
    expect(apiFetch).toHaveBeenNthCalledWith(2, 'POST', '/devices', { name: 'sensor' }, {
      baseURL: '', token: 'restore-token', timeout: false
    })
    expect(apiFetch).toHaveBeenNthCalledWith(3, 'PATCH', '/devices/1', { name: 'updated' }, {
      baseURL: '', token: 'restore-token', timeout: false
    })
    expect(apiFetch).toHaveBeenNthCalledWith(4, 'DELETE', '/devices/1', undefined, {
      baseURL: '', token: 'restore-token', timeout: false
    })
  })

  it('collects ids from a plain-array response', async () => {
    apiFetch.mockResolvedValueOnce(response([{ id: 'one' }, { id: 2 }]))

    expect(await fetchAllIds('/devices', 'token')).toEqual(['one', 2])
    expect(apiFetch).toHaveBeenCalledWith(
      'GET', '/devices?pageSize=200', undefined,
      { baseURL: '', token: 'token', timeout: false }
    )
  })

  it('follows paginated object responses and defaults missing pages to one', async () => {
    apiFetch
      .mockResolvedValueOnce(response({ items: [{ id: 1 }], pages: 2 }))
      .mockResolvedValueOnce(response({ items: [{ id: 2 }] }))
    expect(await fetchAllIds('/batches', 'token')).toEqual([1, 2])
    expect(apiFetch).toHaveBeenNthCalledWith(
      2, 'GET', '/batches?page=2&pageSize=200', undefined,
      { baseURL: '', token: 'token', timeout: false }
    )

    apiFetch.mockResolvedValueOnce(response({ items: [{ id: 3 }] }))
    expect(await fetchAllIds('/batches', 'token')).toEqual([3])
  })

  it('treats missing items in a paginated response as an empty list', async () => {
    apiFetch.mockResolvedValueOnce(response({ pages: 1 }))
    expect(await fetchAllIds('/taps', 'token')).toEqual([])

    apiFetch
      .mockResolvedValueOnce(response({ items: [{ id: 1 }], pages: 2 }))
      .mockResolvedValueOnce(response({}))
    expect(await fetchAllIds('/taps', 'token')).toEqual([1])
  })

  it('keeps ids from earlier pages if a later page fails', async () => {
    apiFetch
      .mockResolvedValueOnce(response({ items: [{ id: 1 }], pages: 3 }))
      .mockResolvedValueOnce(response({ items: [{ id: 2 }] }))
      .mockResolvedValueOnce(response(null, 503))

    expect(await fetchAllIds('/vessels', 'token')).toEqual([1, 2])
  })

  it('throws when the first collection request fails', async () => {
    apiFetch.mockResolvedValueOnce(response(null, 503))
    await expect(fetchAllIds('/devices', 'token')).rejects.toThrow('GET /devices failed: 503')
  })
})
