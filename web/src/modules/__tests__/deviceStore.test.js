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

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useDeviceStore } from '@/modules/deviceStore'

// Mock logger
vi.mock('@/ui', async (importActual) => {
  const actual = await importActual()
  return {
    ...actual,
    logDebug: vi.fn(),
    logInfo: vi.fn(),
    logError: vi.fn()
  }
})

// Mock pinia global object
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
    fetchTimout: 30000,
    updatedDeviceData: 0
  }
}))

describe('useDeviceStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    global.fetch = vi.fn()
  })

  it('should have empty devices array initially', () => {
    const store = useDeviceStore()
    expect(store.devices).toEqual([])
  })

  it('should have deviceList getter', () => {
    const store = useDeviceStore()
    expect(store.deviceList).toEqual([])
  })

  it('should fetch all devices via getDeviceList', async () => {
    const store = useDeviceStore()
    const mockDevices = [
      {
        id: 1,
        chipId: 'chip1',
        chipFamily: 'ESP32',
        software: 'gravitymon',
        mdns: 'device1.local',
        config: 'config1',
        deviceColor: 'red',
        url: 'http://192.168.1.1',
        description: 'Device 1',
        collectLogs: false
      }
    ]

    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: vi
        .fn()
        .mockResolvedValueOnce({ items: mockDevices, pages: 1, total: 1, page: 1, page_size: 100 })
    })

    const result = await store.getDeviceList()

    expect(result).toBeTruthy()
    expect(store.devices.length).toBe(1)
  })

  it('should fetch devices across multiple pages', async () => {
    const store = useDeviceStore()
    const device = {
      id: 'd1',
      chipId: 'chip1',
      chipFamily: 'ESP32',
      software: 'gravitymon',
      mdns: '',
      config: '',
      deviceColor: 'white',
      url: '',
      description: '',
      collectLogs: false
    }
    const page1 = { items: [device], pages: 2, total: 2, page: 1, page_size: 1 }
    const page2 = {
      items: [{ ...device, id: 'd2', chipId: 'chip2' }],
      pages: 2,
      total: 2,
      page: 2,
      page_size: 1
    }

    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: vi.fn().mockResolvedValueOnce(page1) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: vi.fn().mockResolvedValueOnce(page2) })

    const result = await store.getDeviceList()

    expect(result).not.toBeNull()
    expect(store.devices.length).toBe(2)
    expect(global.fetch).toHaveBeenCalledTimes(2)
  })

  it('should handle fetch error in getDeviceList', async () => {
    const store = useDeviceStore()
    global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

    const result = await store.getDeviceList()

    expect(result).toBeNull()
  })

  it('should fetch device by ID', async () => {
    const store = useDeviceStore()
    const mockData = {
      id: 1,
      chipId: 'chip1',
      chipFamily: 'ESP32',
      software: 'gravitymon',
      mdns: 'device1.local',
      config: '',
      deviceColor: 'white',
      url: '',
      description: 'Test Device',
      collectLogs: false
    }

    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValueOnce(mockData)
    })

    const result = await store.getDevice(1)

    expect(result).toBeTruthy()
  })

  it('should allow adding devices to array', () => {
    const store = useDeviceStore()
    store.devices.push({
      id: 1,
      chipId: 'chip1',
      chipFamily: 'ESP32',
      software: 'gravitymon',
      mdns: '',
      config: '',
      deviceColor: 'white',
      url: '',
      description: 'Device',
      collectLogs: false
    })

    expect(store.devices.length).toBe(1)
  })

  it('should allow clearing devices', () => {
    const store = useDeviceStore()
    store.devices = [{ id: 1 }]
    store.devices = []
    expect(store.devices.length).toBe(0)
  })

  it('should handle non-ok response in getDeviceList', async () => {
    const store = useDeviceStore()
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 404
    })

    const result = await store.getDeviceList()

    expect(result).toBeNull()
  })

  it('should handle invalid device ID in getDevice', async () => {
    const store = useDeviceStore()

    const resultUndefined = await store.getDevice(undefined)
    expect(resultUndefined).toBeNull()

    const resultNull = await store.getDevice(null)
    expect(resultNull).toBeNull()

    const resultZero = await store.getDevice(0)
    expect(resultZero).toBeNull()
  })

  it('should handle fetch error in getDevice', async () => {
    const store = useDeviceStore()
    global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

    const result = await store.getDevice(1)

    expect(result).toBeNull()
  })

  it('should handle non-ok response in getDevice', async () => {
    const store = useDeviceStore()
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 404
    })

    const result = await store.getDevice(1)

    expect(result).toBeNull()
  })

  describe('updateDevice Action', () => {
    it('should update device successfully', async () => {
      const store = useDeviceStore()
      const deviceToUpdate = {
        id: 1,
        toJson: () => ({ id: 1, chipId: 'chip1' })
      }

      const mockUpdatedDevice = {
        id: 1,
        chipId: 'chip1',
        description: 'Updated'
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockUpdatedDevice)
      })

      const result = await store.updateDevice(deviceToUpdate)

      expect(result).toBeTruthy()
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/devices/1',
        expect.objectContaining({ method: 'PATCH' })
      )
    })

    it('should return null if update status is not 200', async () => {
      const store = useDeviceStore()
      const deviceToUpdate = {
        id: 1,
        toJson: () => ({ id: 1 })
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 400
      })

      const result = await store.updateDevice(deviceToUpdate)

      expect(result).toBeNull()
    })

    it('should return null on update error', async () => {
      const store = useDeviceStore()
      const deviceToUpdate = {
        id: 1,
        toJson: () => ({ id: 1 })
      }

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Update error'))

      const result = await store.updateDevice(deviceToUpdate)

      expect(result).toBeNull()
    })
  })

  describe('addDevice Action', () => {
    it('should add new device successfully', async () => {
      const store = useDeviceStore()
      const newDevice = {
        toJson: () => ({ chipId: 'newchip' })
      }

      const mockResponse = {
        id: 1,
        chipId: 'newchip'
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 201,
        json: vi.fn().mockResolvedValueOnce(mockResponse)
      })

      const result = await store.addDevice(newDevice)

      expect(result).toBeTruthy()
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/devices',
        expect.objectContaining({ method: 'POST' })
      )
    })

    it('should return null if add status is not 201', async () => {
      const store = useDeviceStore()
      const newDevice = {
        toJson: () => ({ chipId: 'newchip' })
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 400
      })

      const result = await store.addDevice(newDevice)

      expect(result).toBeNull()
    })

    it('should return null on add device error', async () => {
      const store = useDeviceStore()
      const newDevice = {
        toJson: () => ({ chipId: 'newchip' })
      }

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Add error'))

      const result = await store.addDevice(newDevice)

      expect(result).toBeNull()
    })
  })

  describe('deleteDevice Action', () => {
    it('should delete device successfully', async () => {
      const store = useDeviceStore()

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 204
      })

      const result = await store.deleteDevice(1)

      expect(result).toBe(true)
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/devices/1',
        expect.objectContaining({ method: 'DELETE' })
      )
    })

    it('should return false if delete status is not 204', async () => {
      const store = useDeviceStore()

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 404
      })

      const result = await store.deleteDevice(1)

      expect(result).toBe(false)
    })

    it('should return false on delete device error', async () => {
      const store = useDeviceStore()

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Delete error'))

      const result = await store.deleteDevice(1)

      expect(result).toBe(false)
    })
  })

  describe('processEvent Action', () => {
    it('should delete device by id on delete event', () => {
      const store = useDeviceStore()
      store.devices = [
        { id: 1, chipId: 'chip1' },
        { id: 2, chipId: 'chip2' }
      ]

      store.processEvent('delete', 1)

      expect(store.devices.length).toBe(1)
      expect(store.devices[0].id).toBe(2)
    })

    it('should update device by id on update event', async () => {
      const store = useDeviceStore()
      store.devices = [
        { id: 1, chipId: 'chip1' },
        { id: 2, chipId: 'chip2' }
      ]

      const mockDevice = {
        id: 1,
        chipId: 'chip1_updated'
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockDevice)
      })

      await store.processEvent('update', 1)

      expect(store.devices.length).toBe(2)
      const updated = store.devices.find((d) => d.id === 1)
      expect(updated.id).toBe(1)
    })

    it('should create new device on create event', async () => {
      const store = useDeviceStore()
      store.devices = [{ id: 1, chipId: 'chip1' }]

      const mockDevice = {
        id: 2,
        chipId: 'chip2'
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockDevice)
      })

      await store.processEvent('create', 2)

      expect(store.devices.length).toBe(2)
      const created = store.devices.find((d) => d.id === 2)
      expect(created.id).toBe(2)
    })

    it('should not create device if fetch fails', async () => {
      const store = useDeviceStore()
      store.devices = [{ id: 1, chipId: 'chip1' }]

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Fetch error'))

      await store.processEvent('create', 2)

      expect(store.devices.length).toBe(1)
    })

    it('should not update device if fetch fails', async () => {
      const store = useDeviceStore()
      store.devices = [{ id: 1, chipId: 'chip1' }]

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Fetch error'))

      await store.processEvent('update', 1)

      expect(store.devices.length).toBe(1)
    })
  })

  describe('proxyRequest Action', () => {
    it('should make a proxy request successfully', async () => {
      const store = useDeviceStore()
      const mockResponse = { status: 'success', data: 'test' }

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockResponse)
      })

      const result = await store.proxyRequest('GET', 'http://device.local/api/status', {}, null)

      expect(result).toEqual(mockResponse)
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/devices/proxy-fetch',
        expect.objectContaining({ method: 'POST' })
      )
    })

    it('should return null if proxy request fails with non-200 status', async () => {
      const store = useDeviceStore()

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 500
      })

      const result = await store.proxyRequest('GET', 'http://device.local/api/status', {}, null)

      expect(result).toBeNull()
    })

    it('should return null on proxy request error', async () => {
      const store = useDeviceStore()

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const result = await store.proxyRequest(
        'POST',
        'http://device.local/api/config',
        { 'Content-Type': 'application/json' },
        '{"key":"value"}'
      )

      expect(result).toBeNull()
    })

    it('should handle proxy request with various HTTP methods', async () => {
      const store = useDeviceStore()
      const mockResponse = { success: true }

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockResponse)
      })

      const result = await store.proxyRequest(
        'DELETE',
        'http://device.local/api/resource',
        {},
        null
      )

      expect(result).toEqual(mockResponse)
    })
  })

  describe('regenerateToken Action', () => {
    it('should regenerate token successfully', async () => {
      const store = useDeviceStore()

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 200,
        json: vi.fn().mockResolvedValueOnce({ token: 'new-token-123' })
      })

      const result = await store.regenerateToken(1)

      expect(result).toBe('new-token-123')
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/devices/1/token',
        expect.objectContaining({ method: 'POST' })
      )
    })

    it('should return null if status is not 200', async () => {
      const store = useDeviceStore()

      global.fetch = vi.fn().mockResolvedValueOnce({ status: 400 })

      const result = await store.regenerateToken(1)

      expect(result).toBeNull()
    })

    it('should return null on error', async () => {
      const store = useDeviceStore()

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Error'))

      const result = await store.regenerateToken(1)

      expect(result).toBeNull()
    })
  })

  describe('getLatestGravity Action', () => {
    it('should fetch latest gravity successfully', async () => {
      const store = useDeviceStore()
      const mockGravity = {
        id: 1,
        gravity: 1.05,
        temperature: 20,
        batchId: 'b1',
        deviceId: 'd1',
        createdAt: '2026-05-01'
      }
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockGravity)
      })
      const result = await store.getLatestGravity('d1')
      expect(result).toBeTruthy()
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/devices/d1/gravity/latest',
        expect.any(Object)
      )
    })

    it('should return null when gravity returns 404', async () => {
      const store = useDeviceStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 404 })
      const result = await store.getLatestGravity('d1')
      expect(result).toBeNull()
    })

    it('should return null on non-ok non-404 response in getLatestGravity', async () => {
      const store = useDeviceStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 500 })
      const result = await store.getLatestGravity('d1')
      expect(result).toBeNull()
    })

    it('should return null on fetch error in getLatestGravity', async () => {
      const store = useDeviceStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))
      const result = await store.getLatestGravity('d1')
      expect(result).toBeNull()
    })
  })

  describe('getLatestPressure Action', () => {
    it('should fetch latest pressure successfully', async () => {
      const store = useDeviceStore()
      const mockPressure = {
        id: 1,
        pressure: 15.2,
        temperature: 20,
        batchId: 'b1',
        deviceId: 'd1',
        createdAt: '2026-05-01'
      }
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockPressure)
      })
      const result = await store.getLatestPressure('d1')
      expect(result).toBeTruthy()
    })

    it('should return null when pressure returns 404', async () => {
      const store = useDeviceStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 404 })
      const result = await store.getLatestPressure('d1')
      expect(result).toBeNull()
    })

    it('should return null on non-ok non-404 response in getLatestPressure', async () => {
      const store = useDeviceStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 500 })
      const result = await store.getLatestPressure('d1')
      expect(result).toBeNull()
    })

    it('should return null on fetch error in getLatestPressure', async () => {
      const store = useDeviceStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))
      const result = await store.getLatestPressure('d1')
      expect(result).toBeNull()
    })
  })

  describe('getFermentationSteps Action', () => {
    it('should fetch fermentation steps successfully', async () => {
      const store = useDeviceStore()
      const mockSteps = [{ temperature: 18, duration: 7 }]
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockSteps)
      })
      const result = await store.getFermentationSteps('b1')
      expect(result).toEqual(mockSteps)
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/batches/b1/fermentation-steps',
        expect.any(Object)
      )
    })

    it('should return null on non-200 status in getFermentationSteps', async () => {
      const store = useDeviceStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 404 })
      const result = await store.getFermentationSteps('b1')
      expect(result).toBeNull()
    })

    it('should return null on fetch error in getFermentationSteps', async () => {
      const store = useDeviceStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))
      const result = await store.getFermentationSteps('b1')
      expect(result).toBeNull()
    })
  })

  describe('addFermentationSteps Action', () => {
    it('should add fermentation steps successfully', async () => {
      const store = useDeviceStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: true, status: 201 })
      const result = await store.addFermentationSteps('b1', [{ temperature: 18, duration: 7 }])
      expect(result).not.toBe(false)
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/batches/b1/fermentation-steps',
        expect.objectContaining({ method: 'POST' })
      )
    })

    it('should return false on non-201 status in addFermentationSteps', async () => {
      const store = useDeviceStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 400 })
      const result = await store.addFermentationSteps('b1', [])
      expect(result).toBe(false)
    })

    it('should return false on fetch error in addFermentationSteps', async () => {
      const store = useDeviceStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))
      const result = await store.addFermentationSteps('b1', [])
      expect(result).toBe(false)
    })
  })

  describe('deleteFermentationSteps Action', () => {
    it('should delete fermentation steps successfully', async () => {
      const store = useDeviceStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: true, status: 204 })
      const result = await store.deleteFermentationSteps('b1')
      expect(result).not.toBe(false)
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/batches/b1/fermentation-steps',
        expect.objectContaining({ method: 'DELETE' })
      )
    })

    it('should return false on non-204 status in deleteFermentationSteps', async () => {
      const store = useDeviceStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 404 })
      const result = await store.deleteFermentationSteps('b1')
      expect(result).toBe(false)
    })

    it('should return false on fetch error in deleteFermentationSteps', async () => {
      const store = useDeviceStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))
      const result = await store.deleteFermentationSteps('b1')
      expect(result).toBe(false)
    })
  })

  describe('searchNetwork Action', () => {
    it('should search network and return results', async () => {
      const store = useDeviceStore()
      const mockDevices = [{ name: 'device1', ip: '192.168.1.100' }]
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockDevices)
      })
      const result = await store.searchNetwork()
      expect(result).toEqual(mockDevices)
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/devices/mdns',
        expect.objectContaining({ method: 'GET' })
      )
    })

    it('should return null on non-ok response in searchNetwork', async () => {
      const store = useDeviceStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 500 })
      const result = await store.searchNetwork()
      expect(result).toBeNull()
    })

    it('should return null on fetch error in searchNetwork', async () => {
      const store = useDeviceStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))
      const result = await store.searchNetwork()
      expect(result).toBeNull()
    })
  })
})
