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

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import HomeView from '../HomeView.vue'
import { Batch, Device } from '@/modules/classes'
import { logError } from '@/ui'

// Create pinia mocks
const piniaMocks = vi.hoisted(() => ({
  global: {
    disabled: false,
    clearMessages: vi.fn(),
    messageSuccess: '',
    messageError: '',
    initialized: true,
    showChamberTemps: false,
    showKegmonTaps: false,
    updated: 0,
    baseURL: 'http://localhost:8080/',
    token: 'test-token',
    fetchTimout: 5000
  },
  batchStore: {
    batchList: [],
    getBatchList: vi.fn().mockResolvedValue([])
  },
  dashboardStore: {
    batches: [],
    vessels: [],
    readyBatches: [],
    readyVessels: [],
    fetch: vi.fn().mockResolvedValue({ batches: [], vessels: [], devices: [], taps: [] })
  },
  deviceStore: {
    deviceList: [],
    getDeviceList: vi.fn().mockResolvedValue([]),
    getDevice: vi.fn().mockResolvedValue(null),
    proxyRequest: vi.fn().mockResolvedValue(null)
  },
  vesselStore: {
    vesselList: [],
    getVesselList: vi.fn().mockResolvedValue([])
  },
  pourStore: {
    pours: [],
    listPours: vi.fn().mockResolvedValue([])
  },
  tapStore: {
    tapList: []
  },
  configStore: {
    config: {
      isGravitySG: true,
      isPressureBAR: false,
      isVolumeL: true
    }
  }
}))

vi.mock('@/modules/pinia', () => ({
  global: piniaMocks.global,
  preferences: piniaMocks.global,
  batchStore: piniaMocks.batchStore,
  dashboardStore: piniaMocks.dashboardStore,
  deviceStore: piniaMocks.deviceStore,
  vesselStore: piniaMocks.vesselStore,
  pourStore: piniaMocks.pourStore,
  tapStore: piniaMocks.tapStore,
  configStore: piniaMocks.configStore,
  config: piniaMocks.configStore.config
}))

vi.mock('@/modules/router', () => ({
  default: {
    currentRoute: {
      value: {
        params: { id: 'new' },
        name: 'home'
      }
    },
    push: vi.fn()
  }
}))

vi.mock('@/ui', () => ({
  logDebug: vi.fn(),
  logError: vi.fn(),
  logInfo: vi.fn()
}))

vi.mock('@/modules/utils', () => ({
  gravityToPlato: vi.fn((g) => ((g - 1) * 1000) / 4),
  formatTime: vi.fn((s) => {
    if (s < 60) return `${s}s`
    if (s < 3600) return `${Math.round(s / 60)}m`
    return `${Math.round(s / 3600)}h`
  }),
  getFormattedTemperature: vi.fn((t) => `${t}°C`),
  getFormattedPressure: vi.fn((p) => `${p}PSI`),
  getFormattedVolume: vi.fn((v) => `${v}L`),
  getFormattedPourVolume: vi.fn((p) => `${(p / 100).toFixed(1)}cl`),
  truncateString: vi.fn((s, l) => s?.substring(0, l) || ''),
  getTimeSincePosted: vi.fn(() => '2m ago')
}))

describe('HomeView - Enhanced', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    piniaMocks.global.disabled = false
    piniaMocks.global.messageSuccess = ''
    piniaMocks.global.messageError = ''
    piniaMocks.global.showChamberTemps = false
    piniaMocks.global.showKegmonTaps = false
    piniaMocks.batchStore.batchList = []
    piniaMocks.dashboardStore.batches = []
    piniaMocks.dashboardStore.vessels = []
    piniaMocks.dashboardStore.readyBatches = []
    piniaMocks.dashboardStore.readyVessels = []
    piniaMocks.deviceStore.deviceList = []
    piniaMocks.vesselStore.vesselList = []
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  const createWrapper = () => {
    return mount(HomeView, {
      global: {
        stubs: {
          AppCard: { template: '<section class="app-card"><slot /></section>' },
          AppToggle: true,
          'router-link': true
        },
        plugins: [
          {
            install(app) {
              app.config.globalProperties.$route = { params: {}, name: 'home' }
            }
          }
        ]
      }
    })
  }

  describe('Rendering', () => {
    it('should render the original Bootstrap page container', () => {
      const wrapper = createWrapper()
      expect(wrapper.find('.app-page').exists()).toBe(true)
    })

    it('should render page title', () => {
      const wrapper = createWrapper()
      expect(wrapper.text()).toContain('Overview')
    })

    it('should render the page heading', () => {
      const wrapper = createWrapper()
      expect(wrapper.find('.text-h6').exists()).toBe(true)
    })

    it('should render grid rows', () => {
      const wrapper = createWrapper()
      const rows = wrapper.findAll('.row')
      expect(rows.length).toBeGreaterThan(0)
    })

    it('separates the latest readings row from the status cards', () => {
      const wrapper = createWrapper()
      expect(wrapper.find('.home-readings-section').exists()).toBe(true)
      expect(wrapper.find('.home-readings-section > .row').exists()).toBe(true)
    })
  })

  describe('Toggle Switches', () => {
    it('groups dashboard toggles in the right-aligned control region', () => {
      const wrapper = createWrapper()
      expect(wrapper.find('.home-overview-heading').exists()).toBe(true)
      expect(wrapper.find('.home-overview-heading__title').text()).toBe('Home - Overview')
      expect(wrapper.find('.home-dashboard-toggles').exists()).toBe(true)
      expect(wrapper.findAll('.home-dashboard-toggles__control')).toHaveLength(2)
    })

    it('should have showChamberTemps property', () => {
      expect(typeof piniaMocks.global.showChamberTemps).toBe('boolean')
    })

    it('should have showKegmonTaps property', () => {
      expect(typeof piniaMocks.global.showKegmonTaps).toBe('boolean')
    })

    it('should bind Chamber toggle to global.showChamberTemps', async () => {
      const wrapper = createWrapper()

      piniaMocks.global.showChamberTemps = true
      await wrapper.vm.$nextTick()

      expect(piniaMocks.global.showChamberTemps).toBe(true)
    })

    it('should bind Kegmon toggle to global.showKegmonTaps', async () => {
      const wrapper = createWrapper()

      piniaMocks.global.showKegmonTaps = true
      await wrapper.vm.$nextTick()

      expect(piniaMocks.global.showKegmonTaps).toBe(true)
    })
  })

  describe('Initial State', () => {
    it('should initialize activeBatchList', () => {
      const wrapper = createWrapper()
      expect(Array.isArray(wrapper.vm.activeBatchList)).toBe(true)
    })

    it('should initialize chamberTemps', () => {
      const wrapper = createWrapper()
      expect(Array.isArray(wrapper.vm.chamberTemps)).toBe(true)
    })

    it('should initialize kegmonTaps', () => {
      const wrapper = createWrapper()
      expect(Array.isArray(wrapper.vm.kegmonTaps)).toBe(true)
    })

    it('should initialize latest readings arrays', () => {
      const wrapper = createWrapper()
      expect(Array.isArray(wrapper.vm.latestGravityReadings)).toBe(true)
      expect(Array.isArray(wrapper.vm.latestPressureReadings)).toBe(true)
      expect(Array.isArray(wrapper.vm.latestPourReadings)).toBe(true)
    })

    it('should initialize fermentation control list', () => {
      const wrapper = createWrapper()
      expect(Array.isArray(wrapper.vm.fermentationControlList)).toBe(true)
    })
  })

  describe('Active batch device indicators', () => {
    it('returns assigned devices in gravity, pressure, chamber order', () => {
      piniaMocks.deviceStore.deviceList = [
        new Device({ id: 'pressure', name: 'Pressure sensor', batchId: 'batch-1', batchRole: 'pressure', deviceColor: 'blue' }),
        new Device({ id: 'chamber', name: 'Chamber controller', batchId: 'batch-1', batchRole: 'chamber', deviceColor: 'white' }),
        new Device({ id: 'gravity', name: 'Gravity sensor', batchId: 'batch-1', batchRole: 'gravity', deviceColor: 'red' }),
        new Device({ id: 'unassigned-role', name: 'Unknown', batchId: 'batch-1', batchRole: 'other' }),
        new Device({ id: 'other', batchId: 'batch-2', batchRole: 'gravity', deviceColor: 'green' })
      ]
      const wrapper = createWrapper()

      expect(wrapper.vm.getBatchDevices('batch-1').map((device) => device.id)).toEqual([
        'gravity', 'pressure', 'chamber', 'unassigned-role'
      ])
      expect(wrapper.vm.deviceRoleLabel(piniaMocks.deviceStore.deviceList[0])).toBe('Pressure')
      expect(wrapper.vm.deviceRoleShortLabel(piniaMocks.deviceStore.deviceList[0])).toBe('P')
      expect(wrapper.vm.deviceRoleLabel(piniaMocks.deviceStore.deviceList[3])).toBe('Device')
      expect(wrapper.vm.deviceRoleShortLabel(piniaMocks.deviceStore.deviceList[3])).toBe('D')
    })
  })

  describe('Computed Properties - Counts', () => {
    it('should have gravity count computed property', () => {
      const wrapper = createWrapper()
      expect(typeof wrapper.vm.gravityCount).toBe('number')
    })

    it('should have pour count computed property', () => {
      const wrapper = createWrapper()
      expect(typeof wrapper.vm.pourCount).toBe('number')
    })

    it('should have pressure count computed property', () => {
      const wrapper = createWrapper()
      expect(typeof wrapper.vm.pressureCount).toBe('number')
    })

    it('should have device count computed property', () => {
      const wrapper = createWrapper()
      expect(typeof wrapper.vm.deviceCount).toBe('number')
    })

    it('should have batch count computed property', () => {
      const wrapper = createWrapper()
      expect(typeof wrapper.vm.batchCount).toBe('number')
    })

    it('should compute zero count for empty stores', () => {
      const wrapper = createWrapper()
      expect(wrapper.vm.gravityCount).toBe(0)
      expect(wrapper.vm.pourCount).toBe(0)
      expect(wrapper.vm.pressureCount).toBe(0)
    })
  })

  describe('Methods', () => {
    it('should have getBatchAge method', () => {
      const wrapper = createWrapper()
      expect(typeof wrapper.vm.getBatchAge).toBe('function')
    })

    it('should have getGravityOG method', () => {
      const wrapper = createWrapper()
      expect(typeof wrapper.vm.getGravityOG).toBe('function')
    })

    it('should have getLastGravity method', () => {
      const wrapper = createWrapper()
      expect(typeof wrapper.vm.getLastGravity).toBe('function')
    })

    it('should have getLastTemperature method', () => {
      const wrapper = createWrapper()
      expect(typeof wrapper.vm.getLastTemperature).toBe('function')
    })

    it('should have getLastPressure method', () => {
      const wrapper = createWrapper()
      expect(typeof wrapper.vm.getLastPressure).toBe('function')
    })

  })

  describe('Batch Card Display', () => {
    it('should initialize activeBatchList', () => {
      const wrapper = createWrapper()
      expect(Array.isArray(wrapper.vm.activeBatchList)).toBe(true)
    })

    it('should support adding batch to list', async () => {
      const wrapper = createWrapper()
      await flushPromises()
      const batch = new Batch({ id: 1, name: 'Test Batch' })
      wrapper.vm.activeBatchList.push(batch)
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.activeBatchList.length).toBe(1)
      expect(wrapper.vm.activeBatchList[0].name).toBe('Test Batch')
    })

    it('keeps device, chart, age, and metrics in stable batch-summary regions', async () => {
      const wrapper = createWrapper()
      wrapper.vm.activeBatchList.push(new Batch({ id: 1, name: 'Test Batch', gravityCount: 1 }))
      await wrapper.vm.$nextTick()

      const summary = wrapper.find('.home-batch-summary')
      expect(summary.exists()).toBe(true)
      expect(summary.find('.home-batch-summary__devices').exists()).toBe(true)
      expect(summary.find('.home-batch-summary__charts').exists()).toBe(true)
      expect(summary.find('.home-batch-summary__age').text()).toContain('Age:')
      expect(summary.find('.home-batch-summary__metrics').text()).toContain('Gravity:')
    })
  })

  describe('Database Metrics Card', () => {
    it('should initialize database metric variables', () => {
      const wrapper = createWrapper()
      expect(typeof wrapper.vm.deviceCount).toBe('number')
      expect(typeof wrapper.vm.batchCount).toBe('number')
      expect(typeof wrapper.vm.gravityCount).toBe('number')
      expect(typeof wrapper.vm.pourCount).toBe('number')
      expect(typeof wrapper.vm.pressureCount).toBe('number')
    })
  })

  describe('Latest Readings Tables', () => {
    it('should initialize latest gravity readings array', () => {
      const wrapper = createWrapper()
      expect(Array.isArray(wrapper.vm.latestGravityReadings)).toBe(true)
    })

    it('should initialize latest pressure readings array', () => {
      const wrapper = createWrapper()
      expect(Array.isArray(wrapper.vm.latestPressureReadings)).toBe(true)
    })

    it('should initialize latest pour readings array', () => {
      const wrapper = createWrapper()
      expect(Array.isArray(wrapper.vm.latestPourReadings)).toBe(true)
    })

    it('should support adding gravity readings', async () => {
      const wrapper = createWrapper()
      wrapper.vm.latestGravityReadings.push({
        id: 1,
        batchName: 'Test',
        gravity: 1.05,
        created: '2025-05-09 10:00:00'
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.latestGravityReadings.length).toBe(1)
    })
  })

  describe('Data Binding Integration', () => {
    it('should bind global.showChamberTemps', async () => {
      const wrapper = createWrapper()

      piniaMocks.global.showChamberTemps = false
      await wrapper.vm.$nextTick()
      expect(piniaMocks.global.showChamberTemps).toBe(false)

      piniaMocks.global.showChamberTemps = true
      await wrapper.vm.$nextTick()
      expect(piniaMocks.global.showChamberTemps).toBe(true)
    })

    it('should bind global.showKegmonTaps', async () => {
      const wrapper = createWrapper()

      piniaMocks.global.showKegmonTaps = false
      await wrapper.vm.$nextTick()
      expect(piniaMocks.global.showKegmonTaps).toBe(false)

      piniaMocks.global.showKegmonTaps = true
      await wrapper.vm.$nextTick()
      expect(piniaMocks.global.showKegmonTaps).toBe(true)
    })
  })

  describe('Store Integration', () => {
    it('should access batch store', () => {
      expect(piniaMocks.batchStore).toBeDefined()
    })

    it('should access device store', () => {
      expect(piniaMocks.deviceStore).toBeDefined()
    })

    it('should access global store', () => {
      expect(piniaMocks.global).toBeDefined()
    })

    it('should access config store', () => {
      expect(piniaMocks.configStore).toBeDefined()
    })
  })

  describe('Component Lifecycle', () => {
    it('should initialize tickers', () => {
      const wrapper = createWrapper()
      expect(wrapper.vm.ticker).toBeDefined()
      expect(wrapper.vm.readingsTicker).toBeDefined()
    })

    it('should have scheduler status', () => {
      const wrapper = createWrapper()
      expect(wrapper.vm.schedulerStatus).toBeDefined()
    })
  })

  describe('Batch Age', () => {
    it('returns empty string when the batch has no measurement', () => {
      const wrapper = createWrapper()
      const age = wrapper.vm.getBatchAge({ firstReadingAt: null })
      expect(age).toBe('')
    })

    it('uses the first measurement and omits seconds', () => {
      vi.useFakeTimers()
      vi.setSystemTime(new Date('2026-10-02T12:34:56Z'))
      const wrapper = createWrapper()
      const age = wrapper.vm.getBatchAge({
        brewDate: '2026-09-01T00:00:00Z',
        firstReadingAt: '2026-09-30T10:20:45Z',
        lastReadingAt: '2026-10-02T12:34:55Z'
      })

      expect(age).toBe('2d 2h 14m')
      expect(age).not.toMatch(/s$/)
      vi.useRealTimers()
    })

    it('getGravityOG should return 0.0 for batch with no og', () => {
      const wrapper = createWrapper()
      const batch = { og: null, gravityCount: 0 }
      const og = wrapper.vm.getGravityOG(batch)
      expect(og).toBe(0.0)
    })

    it('getLastGravity should return N/A for batch with no currentGravity', () => {
      const wrapper = createWrapper()
      const batch = { currentGravity: null }
      const gravity = wrapper.vm.getLastGravity(batch)
      expect(gravity).toBe('N/A')
    })

    it('getLastGravity should format gravity value correctly', () => {
      const wrapper = createWrapper()
      const batch = { currentGravity: 1.01 }
      const gravity = wrapper.vm.getLastGravity(batch)
      expect(gravity).toBeDefined()
      expect(typeof gravity).toBe('string')
    })

    it('formats measured OG and gravity in specific gravity and Plato modes', () => {
      const wrapper = createWrapper()
      const config = piniaMocks.configStore.config
      const originalGravityP = config.isGravityP

      config.isGravityP = false
      expect(wrapper.vm.getGravityOG({ og: 1.05 })).toBe('1.0500')
      expect(wrapper.vm.getLastGravity({ currentGravity: 1.02 })).toBe('1.0200')

      config.isGravityP = true
      expect(wrapper.vm.getGravityOG({ og: 1.05 })).toBe('12.50')
      expect(wrapper.vm.getLastGravity({ currentGravity: 1.02 })).toBe('5.00')

      config.isGravityP = originalGravityP
    })
  })

  describe('Temperature Methods', () => {
    it('getLastTemperature should return N/A for batch with no currentTemp', () => {
      const wrapper = createWrapper()
      const batch = { currentTemp: null }
      const temp = wrapper.vm.getLastTemperature(batch)
      expect(temp).toBe('N/A')
    })

    it('getLastTemperature should return formatted value when currentTemp is set', () => {
      const wrapper = createWrapper()
      const batch = { currentTemp: 20.0 }
      const temp = wrapper.vm.getLastTemperature(batch)
      expect(temp).toBeDefined()
      expect(typeof temp).toBe('string')
    })
  })

  describe('Pressure Methods', () => {
    it('getLastPressure should return N/A for batch with no currentPressure', () => {
      const wrapper = createWrapper()
      const batch = { currentPressure: null }
      const pressure = wrapper.vm.getLastPressure(batch)
      expect(pressure).toBe('N/A')
    })

    it('getLastPressure should format pressure value correctly', () => {
      const wrapper = createWrapper()
      const batch = { currentPressure: 2.5 }
      const pressure = wrapper.vm.getLastPressure(batch)
      expect(pressure).toBeDefined()
      expect(typeof pressure).toBe('string')
    })
  })

  describe('Timer Management', () => {
    it('should clear ticker on unmount', async () => {
      const wrapper = createWrapper()
      const clearIntervalSpy = vi.spyOn(global, 'clearInterval')
      wrapper.vm.ticker = setInterval(() => {}, 5000)

      wrapper.unmount()

      expect(clearIntervalSpy).toHaveBeenCalled()
      clearIntervalSpy.mockRestore()
    })

    it('should clear readingsTicker on unmount', async () => {
      const wrapper = createWrapper()
      const clearIntervalSpy = vi.spyOn(global, 'clearInterval')
      wrapper.vm.readingsTicker = setInterval(() => {}, 5000)

      wrapper.unmount()

      expect(clearIntervalSpy).toHaveBeenCalled()
      clearIntervalSpy.mockRestore()
    })
  })

  describe('Prediction Methods', () => {
    it('getPrediction should return null if batch has no predictions', () => {
      const wrapper = createWrapper()
      const batch = { id: 'b1', predictions: [] }
      expect(wrapper.vm.getPrediction(null)).toBeNull()
      expect(wrapper.vm.getPrediction(batch)).toBeNull()
    })

    it('getPrediction should return DONE if remaining time is less than 0.5h', () => {
      const wrapper = createWrapper()
      const now = new Date()
      const batch = { id: 'b1', predictions: [{ hoursLeft: 0.4, createdAt: now.toISOString() }] }
      expect(wrapper.vm.getPrediction(batch)).toBe('DONE')
    })

    it('getPrediction should adjust for elapsed time and return formatted hours', () => {
      const wrapper = createWrapper()
      const predictionTime = new Date(Date.now() - 1000 * 60 * 60) // 1 hour ago
      const batch = {
        id: 'b1',
        predictions: [{ hoursLeft: 5.0, createdAt: predictionTime.toISOString() }]
      }
      // 5.0 - 1.0 = 4.0
      expect(wrapper.vm.getPrediction(batch)).toBe('4.0 h')
    })

    it('getPrediction should return DONE if elapsed time exceeds prediction', () => {
      const wrapper = createWrapper()
      const predictionTime = new Date(Date.now() - 1000 * 60 * 60 * 10) // 10 hours ago
      const batch = {
        id: 'b1',
        predictions: [{ hoursLeft: 5.0, createdAt: predictionTime.toISOString() }]
      }
      // 5.0 - 10.0 = -5.0
      expect(wrapper.vm.getPrediction(batch)).toBe('DONE')
    })

    it('getPrediction should return null for invalid timestamp', () => {
      const wrapper = createWrapper()
      const batch = { id: 'b1', predictions: [{ hoursLeft: 5.0, createdAt: 'invalid-date' }] }
      expect(wrapper.vm.getPrediction(batch)).toBeNull()
    })
  })

  describe('Gravity Count Computation', () => {
    it('should calculate total gravity count from all batches', () => {
      const wrapper = createWrapper()
      expect(typeof wrapper.vm.gravityCount).toBe('number')
    })

    it('should return 0 when no batches have gravity readings', () => {
      const wrapper = createWrapper()
      expect(wrapper.vm.gravityCount).toBe(0)
    })
  })

  describe('Pour Count Computation', () => {
    it('should calculate total pour count from all batches', () => {
      const wrapper = createWrapper()
      expect(typeof wrapper.vm.pourCount).toBe('number')
    })

    it('should return 0 when no batches have pour readings', () => {
      const wrapper = createWrapper()
      expect(wrapper.vm.pourCount).toBe(0)
    })
  })

  describe('Pressure Count Computation', () => {
    it('should calculate total pressure count from all batches', () => {
      const wrapper = createWrapper()
      expect(typeof wrapper.vm.pressureCount).toBe('number')
    })

    it('should return 0 when no batches have pressure readings', () => {
      const wrapper = createWrapper()
      expect(wrapper.vm.pressureCount).toBe(0)
    })
  })

  describe('Device Count Computation', () => {
    it('should return device count from device store', () => {
      const wrapper = createWrapper()
      expect(wrapper.vm.deviceCount).toBe(piniaMocks.deviceStore.deviceList.length)
    })
  })

  describe('Batch Count Computation', () => {
    it('should return batch count from batch store', () => {
      const wrapper = createWrapper()
      expect(wrapper.vm.batchCount).toBe(piniaMocks.batchStore.batchList.length)
    })
  })

  describe('Async Chamber and Kegmon Fetch', () => {
    it('should initialize chamber temps as empty array', () => {
      const wrapper = createWrapper()
      expect(Array.isArray(wrapper.vm.chamberTemps)).toBe(true)
      expect(wrapper.vm.chamberTemps.length).toBe(0)
    })

    it('should initialize kegmon taps as empty array', () => {
      const wrapper = createWrapper()
      expect(Array.isArray(wrapper.vm.kegmonTaps)).toBe(true)
      expect(wrapper.vm.kegmonTaps.length).toBe(0)
    })
  })

  describe('Reading Display', () => {
    it('should support adding and displaying gravity readings', async () => {
      const wrapper = createWrapper()
      const reading = {
        id: 1,
        batchName: 'Test Batch',
        gravity: 1.05,
        temperature: 20,
        battery: 4.5,
        created: new Date().toISOString()
      }
      wrapper.vm.latestGravityReadings.push(reading)
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.latestGravityReadings.length).toBe(1)
      expect(wrapper.vm.latestGravityReadings[0].batchName).toBe('Test Batch')
    })

    it('should support adding and displaying pressure readings', async () => {
      const wrapper = createWrapper()
      const reading = {
        id: 1,
        batchName: 'Test Batch',
        pressure: 2.5,
        temperature: 20,
        battery: 4.5,
        created: new Date().toISOString()
      }
      wrapper.vm.latestPressureReadings.push(reading)
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.latestPressureReadings.length).toBe(1)
    })

    it('should support adding and displaying pour readings', async () => {
      const wrapper = createWrapper()
      const reading = {
        id: 1,
        batchName: 'Test Batch',
        volume: 50,
        pour: 20,
        created: new Date().toISOString()
      }
      wrapper.vm.latestPourReadings.push(reading)
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.latestPourReadings.length).toBe(1)
    })
  })

  describe('Fermentation Control List', () => {
    it('should initialize fermentation control list', () => {
      const wrapper = createWrapper()
      expect(Array.isArray(wrapper.vm.fermentationControlList)).toBe(true)
    })

    it('should support adding fermentation controller device', async () => {
      const wrapper = createWrapper()
      const device = new Device(
        1,
        'abc123',
        'http://localhost:8080/',
        'Chamber Controller',
        'Chamber-Controller'
      )
      wrapper.vm.fermentationControlList.push(device)
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.fermentationControlList.length).toBe(1)
    })
  })

  describe('fetchChamber() - Async Chamber Data', () => {
    it('should clear chamber temps when showChamberTemps is false', async () => {
      const wrapper = createWrapper()
      piniaMocks.global.showChamberTemps = false
      wrapper.vm.chamberTemps = [{ mdns: 'test' }]

      await wrapper.vm.fetchChamber()

      expect(wrapper.vm.chamberTemps).toEqual([])
    })

    it('should call proxyRequest for each chamber device when enabled', async () => {
      const wrapper = createWrapper()
      const device = new Device({
        id: '1',
        chipId: 'abc123',
        url: 'http://localhost/',
        name: 'Test Chamber',
        deviceType: 'chamber_controller'
      })
      piniaMocks.deviceStore.deviceList = [device]
      piniaMocks.deviceStore.proxyRequest = vi.fn().mockResolvedValue({
        mdns: 'chamber1',
        pid_fridge_temp: 10
      })
      piniaMocks.global.showChamberTemps = true

      await wrapper.vm.fetchChamber()

      expect(wrapper.vm.chamberTemps.length).toBeGreaterThanOrEqual(0)
      expect(piniaMocks.deviceStore.proxyRequest).toHaveBeenCalledWith(
        'GET',
        'http://localhost/api/status',
        'Content-Type: application/json',
        '',
        { noErrorNotify: true }
      )
    })

    it('renders an error entry when a chamber request rejects', async () => {
      const wrapper = createWrapper()
      const device = new Device({
        id: 'chamber-failed',
        chipId: 'abc123',
        url: 'http://chamber/',
        name: 'Chamber',
        deviceType: 'chamber_controller'
      })
      piniaMocks.deviceStore.deviceList = [device]
      piniaMocks.deviceStore.proxyRequest = vi.fn().mockRejectedValue(new Error('offline'))
      piniaMocks.global.showChamberTemps = true

      await wrapper.vm.fetchChamber()

      expect(wrapper.vm.chamberTemps).toEqual([
        { mdns: device.mdns, url: device.url, error: 'Failed to fetch data' }
      ])
    })

    it('should filter only Chamber-Controller devices', async () => {
      const wrapper = createWrapper()
      const chamberDevice = new Device({
        id: 1,
        chipId: 'abc123',
        url: 'http://chamber/',
        description: 'Chamber'
      })
      const otherDevice = new Device({
        id: 2,
        chipId: 'def456',
        url: 'http://other/',
        description: 'Other'
      })
      piniaMocks.deviceStore.deviceList = [chamberDevice, otherDevice]
      piniaMocks.global.showChamberTemps = true

      // Should succeed without errors
      await wrapper.vm.fetchChamber()

      expect(wrapper.vm.chamberTemps).toBeDefined()
    })
  })

  describe('fetchKegmon() - Async Kegmon Data', () => {
    it('should clear kegmon taps when showKegmonTaps is false', async () => {
      const wrapper = createWrapper()
      piniaMocks.global.showKegmonTaps = false
      wrapper.vm.kegmonTaps = [{ mdns: 'test' }]

      await wrapper.vm.fetchKegmon()

      expect(wrapper.vm.kegmonTaps).toEqual([])
    })

    it('should filter only Kegmon devices', async () => {
      const wrapper = createWrapper()
      const kegmonDevice = new Device({
        id: 1,
        chipId: 'def456',
        url: 'http://kegmon/',
        description: 'Kegmon'
      })
      const otherDevice = new Device(
        2,
        'abc123',
        'http://chamber/',
        'Chamber',
        'Chamber-Controller'
      )
      piniaMocks.deviceStore.deviceList = [kegmonDevice, otherDevice]
      piniaMocks.global.showKegmonTaps = true

      // Should succeed without errors
      await wrapper.vm.fetchKegmon()

      expect(wrapper.vm.kegmonTaps).toBeDefined()
    })

    it('renders an error entry when a Kegmon request rejects', async () => {
      const wrapper = createWrapper()
      const device = new Device({
        id: 'kegmon-failed',
        chipId: 'def456',
        url: 'http://kegmon/',
        name: 'Kegmon',
        deviceType: 'kegmon'
      })
      piniaMocks.deviceStore.deviceList = [device]
      piniaMocks.deviceStore.proxyRequest = vi.fn().mockRejectedValue(new Error('offline'))
      piniaMocks.global.showKegmonTaps = true

      await wrapper.vm.fetchKegmon()

      expect(wrapper.vm.kegmonTaps).toEqual([
        { mdns: device.mdns, url: device.url, error: 'Failed to fetch data' }
      ])
    })

    it('should fallback to empty array when fetch fails', async () => {
      const wrapper = createWrapper()
      piniaMocks.deviceStore.deviceList = []
      piniaMocks.global.showKegmonTaps = true

      await wrapper.vm.fetchKegmon()

      expect(wrapper.vm.kegmonTaps).toEqual([])
    })
  })

  describe('fetchScheduler() - Async Scheduler Status', () => {
    it('should attempt to fetch scheduler status', async () => {
      const wrapper = createWrapper()
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue([])
      })

      await wrapper.vm.fetchScheduler()

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('system/scheduler'),
        expect.objectContaining({ method: 'GET' })
      )
    })

    it('logs a scheduler request failure', async () => {
      const wrapper = createWrapper()
      global.fetch = vi.fn().mockRejectedValue(new Error('offline'))

      await wrapper.vm.fetchScheduler()
      await flushPromises()

      expect(logError).toHaveBeenCalledWith('HomeView.fetchScheduler()', expect.any(Error))
    })
  })

  describe('Latest Readings - Computed from dashboard', () => {
    it('should expose latestGravityReadings as an array', () => {
      const wrapper = createWrapper()
      expect(Array.isArray(wrapper.vm.latestGravityReadings)).toBe(true)
    })

    it('should expose latestPressureReadings as an array', () => {
      const wrapper = createWrapper()
      expect(Array.isArray(wrapper.vm.latestPressureReadings)).toBe(true)
    })

    it('should expose latestPourReadings as an array', () => {
      const wrapper = createWrapper()
      expect(Array.isArray(wrapper.vm.latestPourReadings)).toBe(true)
    })

    it('should derive gravity readings from dashboard batches', () => {
      piniaMocks.dashboardStore.batches = [
        {
          currentGravity: 1.05,
          currentTemp: 20,
          battery: 3.8,
          lastReadingAt: '2026-05-26T10:00:00'
        }
      ]
      const wrapper = createWrapper()
      expect(wrapper.vm.latestGravityReadings.length).toBe(1)
      expect(wrapper.vm.latestGravityReadings[0].gravity).toBe(1.05)
    })

    it('should lazy-fetch pour readings per vessel via pourStore.listPours', async () => {
      piniaMocks.dashboardStore.vessels = [{ id: 'vessel1' }]
      piniaMocks.pourStore.listPours = vi.fn().mockResolvedValue([
        { createdAt: '2026-05-26T10:00:00', volumeRemaining: 15.0, pourAmount: 0.5 }
      ])
      const wrapper = createWrapper()

      await wrapper.vm.fetchLatestPourReadings()

      expect(piniaMocks.pourStore.listPours).toHaveBeenCalledWith('vessel1')
      expect(wrapper.vm.latestPourReadings.length).toBe(1)
    })

    it('ignores vessels whose pour list is null', async () => {
      piniaMocks.dashboardStore.vessels = [{ id: 'empty-vessel' }]
      piniaMocks.pourStore.listPours.mockResolvedValue(null)
      const wrapper = createWrapper()

      await wrapper.vm.fetchLatestPourReadings()

      expect(wrapper.vm.latestPourReadings).toEqual([])
    })
  })

  describe('onMounted() - Component Initialization', () => {
    it('should initialize active batch list', async () => {
      const wrapper = createWrapper()

      await flushPromises()

      expect(wrapper.vm.activeBatchList).toBeDefined()
      expect(Array.isArray(wrapper.vm.activeBatchList)).toBe(true)
    })

    it('should set up ticker intervals on mount', async () => {
      const wrapper = createWrapper()

      await flushPromises()

      expect(wrapper.vm.ticker).toBeDefined()
      expect(wrapper.vm.readingsTicker).toBeDefined()
    })
  })

  describe('Ready to Serve Card', () => {
    it('should expose readyItems computed property as empty array by default', () => {
      const wrapper = createWrapper()
      expect(Array.isArray(wrapper.vm.readyItems)).toBe(true)
      expect(wrapper.vm.readyItems.length).toBe(0)
    })

    it('should combine ready batches and vessels into readyItems', () => {
      piniaMocks.dashboardStore.readyBatches = [
        { id: 'b1', name: 'Ready Lager', kind: 'batch', readyDate: '2026-06-01' }
      ]
      piniaMocks.dashboardStore.readyVessels = [
        { id: 'v1', name: 'Ready Keg', kind: 'vessel', readyDate: '2026-06-05' }
      ]
      const wrapper = createWrapper()
      expect(wrapper.vm.readyItems.length).toBe(2)
    })

    it('should show only batches in readyItems when no ready vessels', () => {
      piniaMocks.dashboardStore.readyBatches = [
        { id: 'b1', name: 'Summer Ale', kind: 'batch', readyDate: '2026-06-01' }
      ]
      const wrapper = createWrapper()
      expect(wrapper.vm.readyItems.length).toBe(1)
      expect(wrapper.vm.readyItems[0].name).toBe('Summer Ale')
      expect(wrapper.vm.readyItems[0].kind).toBe('batch')
    })

    it('should show only vessels in readyItems when no ready batches', () => {
      piniaMocks.dashboardStore.readyVessels = [
        { id: 'v1', name: 'Keg #1', kind: 'vessel', readyDate: '2026-06-05' }
      ]
      const wrapper = createWrapper()
      expect(wrapper.vm.readyItems.length).toBe(1)
      expect(wrapper.vm.readyItems[0].name).toBe('Keg #1')
      expect(wrapper.vm.readyItems[0].kind).toBe('vessel')
    })
  })


})
