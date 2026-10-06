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
import { useDashboardStore } from '@/modules/dashboardStore'

// Mock apiClient
vi.mock('@/modules/apiClient', () => ({
  apiJson: vi.fn(),
  apiOk: vi.fn()
}))

// Mock logger
vi.mock('@/ui', () => ({
  logDebug: vi.fn(),
  logInfo: vi.fn(),
  logError: vi.fn()
}))

describe('useDashboardStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('Initial State', () => {
    it('should have null data initially', () => {
      const store = useDashboardStore()
      expect(store.data).toBeNull()
    })

    it('should have empty arrays for all getters initially', () => {
      const store = useDashboardStore()
      expect(store.batches).toEqual([])
      expect(store.devices).toEqual([])
      expect(store.taps).toEqual([])
      expect(store.vessels).toEqual([])
      expect(store.readyBatches).toEqual([])
      expect(store.readyVessels).toEqual([])
    })
  })

  describe('Getters', () => {
    it('returns ready batches and vessels when the dashboard data includes them', () => {
      const store = useDashboardStore()
      const readyBatches = [{ id: 'b1', name: 'Ready batch', kind: 'batch', readyDate: null }]
      const readyVessels = [{ id: 'v1', name: 'Ready keg', kind: 'vessel', readyDate: null }]
      store.data = {
        devices: [], batches: [], taps: [], vessels: [], readyBatches, readyVessels
      }

      expect(store.readyBatches).toEqual(readyBatches)
      expect(store.readyVessels).toEqual(readyVessels)
    })

    it('should return batches from data when available', () => {
      const store = useDashboardStore()
      const mockBatches = [
        {
          id: 'batch1',
          name: 'Test Batch',
          status: 'fermenting',
          brewDate: '2024-01-01',
          dayCount: 5,
          og: 1.050,
          fg: null,
          currentGravity: 1.030,
          currentPressure: null,
          currentTemp: 18.5,
          battery: 100,
          rssi: -50,
          lastReadingAt: '2024-01-06T10:00:00Z',
          gravityCount: 10,
          pressureCount: 0,
          predictions: []
        }
      ]
      store.data = {
        devices: [],
        batches: mockBatches,
        taps: [],
        vessels: []
      }
      expect(store.batches).toEqual(mockBatches)
    })

    it('should return devices from data when available', () => {
      const store = useDashboardStore()
      const mockDevices = [
        {
          id: 'device1',
          name: 'Tilt',
          chipFamily: 'ESP32',
          software: '1.0.0',
          batchId: 'batch1',
          batchRole: 'gravity',
          vesselId: null,
          status: 'active',
          lastSeenAt: '2024-01-06T10:00:00Z',
          latestReading: {
            gravity: 1.050,
            pressure: null,
            temperature: 18.5,
            battery: 100,
            rssi: -50,
            recordedAt: '2024-01-06T10:00:00Z'
          },
          predictions: []
        }
      ]
      store.data = {
        devices: mockDevices,
        batches: [],
        taps: [],
        vessels: []
      }
      expect(store.devices).toEqual(mockDevices)
    })

    it('should return taps from data when available', () => {
      const store = useDashboardStore()
      const mockTaps = [
        {
          id: 'tap1',
          name: 'Tap 1',
          tapNumber: 1,
          location: 'Keggerator',
          vesselId: 'vessel1',
          vesselName: 'Keg 1',
          batchName: 'Test Batch',
          batchId: 'batch1',
          volumeRemaining: 15.0
        }
      ]
      store.data = {
        devices: [],
        batches: [],
        taps: mockTaps,
        vessels: []
      }
      expect(store.taps).toEqual(mockTaps)
    })

    it('should return vessels from data when available', () => {
      const store = useDashboardStore()
      const mockVessels = [
        {
          id: 'vessel1',
          name: 'Keg 1',
          vesselType: 'keg',
          status: 'active',
          tapId: 'tap1',
          batchId: 'batch1',
          batchName: 'Test Batch',
          totalVolume: 20.0,
          volumeRemaining: 15.0,
          fillDate: '2024-01-01T00:00:00Z',
          predictions: []
        }
      ]
      store.data = {
        devices: [],
        batches: [],
        taps: [],
        vessels: mockVessels
      }
      expect(store.vessels).toEqual(mockVessels)
    })
  })

  describe('fetch action', () => {
    it('should fetch dashboard data', async () => {
      const { apiJson } = await import('@/modules/apiClient')
      const store = useDashboardStore()
      const mockData = {
        devices: [],
        batches: [],
        taps: [],
        vessels: []
      }

      apiJson.mockResolvedValueOnce(mockData)

      const result = await store.fetch()

      expect(result).toEqual(mockData)
      expect(store.data).toEqual(mockData)
    })

    it('should return null when API returns null', async () => {
      const { apiJson } = await import('@/modules/apiClient')
      const store = useDashboardStore()
      apiJson.mockResolvedValueOnce(null)

      const result = await store.fetch()

      expect(result).toBeNull()
      expect(store.data).toBeNull()
    })
  })

  describe('latestPredictionForBatch action', () => {
    it('should return the first prediction for a batch', () => {
      const store = useDashboardStore()
      const mockPredictions = [
        {
          id: 1,
          batchId: 'batch1',
          deviceId: 'device1',
          vesselId: null,
          predictionType: 'fermentation_complete',
          outcome: 'success',
          hoursLeft: 24,
          createdAt: '2024-01-06T10:00:00Z'
        },
        {
          id: 2,
          batchId: 'batch1',
          deviceId: 'device1',
          vesselId: null,
          predictionType: 'fermentation_complete',
          outcome: 'success',
          hoursLeft: 20,
          createdAt: '2024-01-06T14:00:00Z'
        }
      ]

      store.data = {
        devices: [],
        batches: [
          {
            id: 'batch1',
            name: 'Test Batch',
            status: 'fermenting',
            brewDate: '2024-01-01',
            dayCount: 5,
            og: 1.050,
            fg: null,
            currentGravity: 1.030,
            currentPressure: null,
            currentTemp: 18.5,
            battery: 100,
            rssi: -50,
            lastReadingAt: '2024-01-06T10:00:00Z',
            gravityCount: 10,
            pressureCount: 0,
            predictions: mockPredictions
          }
        ],
        taps: [],
        vessels: []
      }

      const result = store.latestPredictionForBatch('batch1')

      expect(result).toEqual(mockPredictions[0])
    })

    it('should return null when batch not found', () => {
      const store = useDashboardStore()
      store.data = {
        devices: [],
        batches: [],
        taps: [],
        vessels: []
      }

      const result = store.latestPredictionForBatch('unknown')

      expect(result).toBeNull()
    })

    it('should return null when batch has no predictions', () => {
      const store = useDashboardStore()
      store.data = {
        devices: [],
        batches: [
          {
            id: 'batch1',
            name: 'Test Batch',
            status: 'fermenting',
            brewDate: '2024-01-01',
            dayCount: 5,
            og: 1.050,
            fg: null,
            currentGravity: 1.030,
            currentPressure: null,
            currentTemp: 18.5,
            battery: 100,
            rssi: -50,
            lastReadingAt: '2024-01-06T10:00:00Z',
            gravityCount: 10,
            pressureCount: 0,
            predictions: []
          }
        ],
        taps: [],
        vessels: []
      }

      const result = store.latestPredictionForBatch('batch1')

      expect(result).toBeNull()
    })

    it('should return null when data is null', () => {
      const store = useDashboardStore()
      store.data = null

      const result = store.latestPredictionForBatch('batch1')

      expect(result).toBeNull()
    })
  })
})
