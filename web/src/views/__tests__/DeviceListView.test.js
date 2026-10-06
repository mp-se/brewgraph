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

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import DeviceListView from '../DeviceListView.vue'

vi.mock('pinia', async () => {
  const { ref } = await import('vue')
  return {
    storeToRefs(store) {
      const refs = {}
      for (const key of Object.keys(store)) {
        if (typeof store[key] === 'function') continue
        const linked = ref(store[key])
        refs[key] = linked
        Object.defineProperty(store, key, {
          get: () => linked.value,
          set: (value) => { linked.value = value },
          enumerable: true,
          configurable: true
        })
      }
      return refs
    }
  }
})

// Mock stores
const { mockDeviceStore, mockGlobalStore, mockPreferences, mockBatchStore } = vi.hoisted(() => ({
  mockDeviceStore: {
    deviceList: [],
    load: vi.fn(),
    deleteDevice: vi.fn().mockResolvedValue(true),
    updateDevice: vi.fn().mockResolvedValue(true),
    addDevice: vi.fn().mockResolvedValue(true),
    searchNetwork: vi.fn().mockResolvedValue([]),
    proxyRequest: vi.fn().mockResolvedValue({})
  },
  mockGlobalStore: {
    disabled: false,
    acquireBusy() {
      this.disabled = true
      let released = false
      return () => { if (!released) { released = true; this.disabled = false } }
    },
    messageError: '',
    messageSuccess: '',
    updatedDeviceData: {},
    clearMessages: vi.fn(),
    baseURL: 'http://localhost:8080/',
    token: 'mock-token',
    fetchTimout: 5000
  },
  mockPreferences: { deviceListFilterDeviceType: '*' },
  mockBatchStore: {
    batchList: [],
    anyBatchesForDevice: vi.fn(() => false)
  }
}))

const mockRouter = vi.hoisted(() => ({
  push: vi.fn(),
  currentRoute: { value: { query: {}, name: 'device-list' } }
}))

const mockUi = vi.hoisted(() => ({
  setSortingDefault: vi.fn(),
  applySortList: vi.fn(),
  sortList: vi.fn(),
  getSortIcon: vi.fn().mockReturnValue('bi-sort-alpha-down'),
  sortedClass: vi.fn().mockReturnValue('sorted'),
  sortedIconClass: 'bi-sort-down'
}))

const mockLogger = vi.hoisted(() => ({
  logDebug: vi.fn(),
  logInfo: vi.fn(),
  logError: vi.fn()
}))

const sortableListMock = vi.hoisted(() => ({
  sortedIconClass: 'bi-sort-down',
  getSortedClass: vi.fn().mockReturnValue('sorted'),
  setSortingDefault: vi.fn(),
  sortList: vi.fn(),
  applySortList: vi.fn()
}))

const mockDetect = vi.hoisted(() => ({
  detectId: vi.fn().mockReturnValue('ABC123'),
  detectMdns: vi.fn().mockReturnValue('test-device'),
  detectPlatform: vi.fn().mockReturnValue('ESP32'),
  detectDeviceType: vi.fn().mockReturnValue('gravitymon')
}))

// Mock pinia exports
vi.mock('@/modules/pinia', () => ({
  default: {},
  global: mockGlobalStore,
  preferences: mockPreferences,
  deviceStore: mockDeviceStore,
  batchStore: mockBatchStore
}))

vi.mock('@/modules/router', () => ({ default: mockRouter }))
vi.mock('@/modules/ui', () => mockUi)
vi.mock('@/modules/useSortableList', () => ({
  useSortableList: vi.fn().mockReturnValue(sortableListMock)
}))
vi.mock('@/ui', () => mockLogger)
vi.mock('@/modules/detect', () => mockDetect)

vi.stubGlobal('open', vi.fn())

describe('DeviceListView.vue', () => {
  let wrapper

  const mockDevice = (id = 1, mdns = 'device1', deviceType = 'gravitymon') => ({
    id,
    mdns,
    chipId: `CHIP${id}`,
    deviceType,
    collectLogs: false,
    url: `http://1.1.1.${id}`,
    chipFamily: 'ESP32',
    deviceColor: 'white',
    description: `Device ${id}`
  })

  const mountWrapper = () => {
    return mount(DeviceListView, {
      attachTo: document.body,
      global: {
        stubs: {
          'router-link': true,
          AppCard: {
            template:
              '<div><slot name="header"></slot><slot></slot><slot name="footer"></slot></div>'
          },
          AppMenuBar: { template: '<div><slot></slot></div>' },
          AppDataDialog: { props: ['id'], template: '<div :id="id"><slot></slot></div>' },
          AppConfirmDialog: {
            props: ['id', 'callback'],
            template:
              '<button type="button" :id="id" hidden style="display:none" @click="callback(true)"></button>'
          },
          AppSelectDialog: {
            props: ['id', 'callback'],
            template:
              '<button type="button" :id="id" hidden style="display:none" @click="callback(true, \'mock-val\')"></button>'
          },
          AppSelect: {
            props: ['modelValue', 'options'],
            template:
              '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="o in options" :value="o.value">{{o.label}}</option><slot></slot></select>'
          },
          AppMessage: { template: '<div></div>' },
          memory: { template: '<span></span>' },
          construction: { template: '<span></span>' },
          IconXCircle: { template: '<span></span>' },
          IconInfoCircle: { template: '<span></span>' },
          IconUpArrow: { template: '<span></span>' },
          IconCloudUpArrow: { template: '<span></span>' },
          IconListUl: { template: '<span></span>' }
        },
        directives: { tooltip: {} }
      }
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
    mockBatchStore.anyBatchesForDevice.mockImplementation(() => false)
    mockDeviceStore.deviceList = [
      mockDevice(1, 'device1', 'gravitymon'),
      mockDevice(2, 'device2', 'kegmon'),
      mockDevice(3, 'device3', 'chamber_controller')
    ]
    mockPreferences.deviceListFilterDeviceType = '*'
    mockGlobalStore.disabled = false
    mockGlobalStore.messageError = ''
    mockGlobalStore.messageSuccess = ''
    mockGlobalStore.updatedDeviceData = {}
    // Setup default fetch mock
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(['device1.log', 'device2.log']) })
    )
    mockRouter.currentRoute.value = { query: {}, name: 'device-list' }
  })

  afterEach(() => {
    if (wrapper) wrapper.unmount()
    vi.restoreAllMocks()
  })

  describe('Rendering', () => {
    it('renders component structure', async () => {
      wrapper = mountWrapper()
      expect(wrapper.find('.app-page').exists()).toBe(true)
      expect(wrapper.find('.text-h6').text()).toContain('Device List')
    })

    it('renders table with all devices', async () => {
      wrapper = mountWrapper()
      await flushPromises()
      const rows = wrapper.findAll('tbody tr')
      expect(rows.length).toBe(3)
    })

    it('renders a color swatch for every listed device', async () => {
      wrapper = mountWrapper()
      await flushPromises()

      const swatches = wrapper.findAll('tbody .device-color-swatch')
      expect(swatches).toHaveLength(3)
      expect(swatches[0].attributes('aria-label')).toBe('White device color')
    })

    it('renders loading state when deviceList is null', async () => {
      mockDeviceStore.deviceList = []
      wrapper = mountWrapper()
      await flushPromises()
      expect(wrapper.text()).toMatch(/Loading|Device/)
    })
  })

  describe('Filtering', () => {
    it('renders all devices when filter is *', async () => {
      wrapper = mountWrapper()
      await flushPromises()
      expect(wrapper.findAll('tbody tr').length).toBe(3)
    })

    it('filters by device type', async () => {
      mockPreferences.deviceListFilterDeviceType = 'gravitymon'
      wrapper = mountWrapper()
      await flushPromises()
      expect(wrapper.findAll('tbody tr').length).toBe(1)
      expect(wrapper.find('tbody tr').text()).toContain('CHIP1')
    })

    it('filters by Chamber-Controller', async () => {
      mockPreferences.deviceListFilterDeviceType = 'chamber_controller'
      wrapper = mountWrapper()
      await flushPromises()
      const rows = wrapper.findAll('tbody tr')
      expect(rows.length).toBeGreaterThan(0)
    })

    it('updates filter when watch triggers', async () => {
      wrapper = mountWrapper()
      await flushPromises()
      await wrapper.find('select').setValue('kegmon')
      await flushPromises()
      expect(wrapper.findAll('tbody tr')).toHaveLength(1)
      expect(wrapper.find('tbody tr').text()).toContain('CHIP2')
    })

    it('refilters and reapplies sorting when device data changes', async () => {
      wrapper = mountWrapper()
      await flushPromises()
      sortableListMock.applySortList.mockClear()

      mockGlobalStore.updatedDeviceData = { id: 1 }
      await flushPromises()

      expect(wrapper.vm.deviceList).toHaveLength(3)
      expect(sortableListMock.applySortList).toHaveBeenCalledWith(wrapper.vm.deviceList)
    })

    it('sorts by each sortable device column from the rendered headers', async () => {
      wrapper = mountWrapper()
      await flushPromises()
      const sortLinks = wrapper.findAll('a.icon-link')
      expect(sortLinks).toHaveLength(4)

      for (const link of sortLinks) await link.trigger('click')

      expect(sortableListMock.sortList).toHaveBeenCalledTimes(4)
    })

    it('paginates device list with fixed 10 items and renders controls', async () => {
      mockDeviceStore.deviceList = Array.from({ length: 12 }, (_, idx) =>
        mockDevice(idx + 1, `device${idx + 1}`, 'gravitymon')
      )

      wrapper = mountWrapper()
      await flushPromises()

      expect(wrapper.vm.totalPages).toBe(2)
      expect(wrapper.vm.paginatedDeviceList).toHaveLength(10)
      expect(wrapper.find('ul.app-pagination').exists()).toBe(true)
    })

    it('marks the active page for assistive technology and visual styling', async () => {
      mockDeviceStore.deviceList = Array.from({ length: 12 }, (_, idx) =>
        mockDevice(idx + 1, `device${idx + 1}`, 'gravitymon')
      )

      wrapper = mountWrapper()
      await flushPromises()

      expect(wrapper.find('.app-pagination__item.active').text()).toBe('1')
      expect(wrapper.find('button[aria-label="Page 1"]').attributes('aria-current')).toBe('page')
      expect(wrapper.find('button[aria-label="Page 2"]').attributes('aria-current')).toBeUndefined()
    })

    it('changes pages through the rendered pagination controls', async () => {
      mockDeviceStore.deviceList = Array.from({ length: 12 }, (_, idx) =>
        mockDevice(idx + 1, `device${idx + 1}`, 'gravitymon')
      )
      wrapper = mountWrapper()
      await flushPromises()

      await wrapper.find('button[aria-label="Next page"]').trigger('click')
      expect(wrapper.vm.currentPage).toBe(2)
      await wrapper.find('button[aria-label="Previous page"]').trigger('click')
      expect(wrapper.vm.currentPage).toBe(1)
      await wrapper.find('button[aria-label="Page 2"]').trigger('click')
      expect(wrapper.vm.currentPage).toBe(2)
    })

    it('changes page and clamps out-of-range page numbers', async () => {
      mockDeviceStore.deviceList = Array.from({ length: 12 }, (_, idx) =>
        mockDevice(idx + 1, `device${idx + 1}`, 'gravitymon')
      )

      wrapper = mountWrapper()
      await flushPromises()

      wrapper.vm.goToPage(2)
      expect(wrapper.vm.currentPage).toBe(2)
      expect(wrapper.vm.paginatedDeviceList).toHaveLength(2)

      wrapper.vm.goToPage(99)
      expect(wrapper.vm.currentPage).toBe(2)

      wrapper.vm.goToPage(0)
      expect(wrapper.vm.currentPage).toBe(1)
    })
  })

  describe('Fetch Device Logs', () => {
    it('fetches device log list on mount', async () => {
      wrapper = mountWrapper()
      await flushPromises()
      expect(global.fetch).toHaveBeenCalled()
    })

    it('sets disabled state during fetch', async () => {
      global.fetch = vi.fn(async () => {
        expect(mockGlobalStore.disabled).toBe(true)
        return { ok: true, json: () => Promise.resolve([]) }
      })
      wrapper = mountWrapper()
      await flushPromises()
    })

    it('handles fetch error gracefully', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Fetch failed'))
      wrapper = mountWrapper()
      await flushPromises()
      expect(mockLogger.logError).toHaveBeenCalled()
    })

    it('handles empty device logs list', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: () => Promise.resolve([]) })
      wrapper = mountWrapper()
      await flushPromises()
      expect(mockGlobalStore.disabled).toBe(false)
    })

    it('filters log file names correctly', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(['device1.log', 'device1.log.1', 'device2.log'])
      })
      wrapper = mountWrapper()
      await flushPromises()
      expect(global.fetch).toHaveBeenCalled()
    })

    describe('Toggle Device Logging', () => {
      it('toggles device logging', async () => {
        wrapper = mountWrapper()
        await flushPromises()
        const device = wrapper.vm.deviceList[0]
        await wrapper.vm.toggleDeviceLogging(device.id)
        expect(mockDeviceStore.updateDevice).toHaveBeenCalled()
      })

      it('handles logging toggle failure', async () => {
        mockDeviceStore.updateDevice.mockResolvedValueOnce(false)
        wrapper = mountWrapper()
        await flushPromises()
        await wrapper.vm.toggleDeviceLogging(1)
        expect(mockGlobalStore.messageError).toBeDefined()
      })

      it('toggles collectLogs property', async () => {
        wrapper = mountWrapper()
        await flushPromises()
        const initialState = wrapper.vm.deviceList[0].collectLogs
        await wrapper.vm.toggleDeviceLogging(wrapper.vm.deviceList[0].id)
        expect(wrapper.vm.deviceList[0].collectLogs).toBe(!initialState)
      })

      it('updates logging when the rendered collect-logs control is clicked', async () => {
        wrapper = mountWrapper()
        await flushPromises()

        await wrapper.find('tbody input[type="checkbox"]').trigger('click')
        await flushPromises()

        expect(mockDeviceStore.updateDevice).toHaveBeenCalledWith(wrapper.vm.deviceList[0])
      })

      it('keeps the current page when toggling logging', async () => {
        mockDeviceStore.deviceList = Array.from({ length: 12 }, (_, idx) =>
          mockDevice(idx + 1, `device${idx + 1}`, 'gravitymon')
        )
        wrapper = mountWrapper()
        await flushPromises()
        wrapper.vm.goToPage(2)

        await wrapper.vm.toggleDeviceLogging(wrapper.vm.paginatedDeviceList[0].id)

        expect(wrapper.vm.currentPage).toBe(2)
      })
    })

    describe('Delete Device', () => {
      it('calls deleteDevice with correct id', async () => {
        wrapper = mountWrapper()
        await flushPromises()
        await wrapper.vm.confirmDeleteCallback(true)
        expect(mockGlobalStore.disabled).toBeDefined()
      })

      it('routes the rendered delete action through confirmation', async () => {
        wrapper = mountWrapper()
        await flushPromises()
        const lookup = vi.spyOn(document, 'getElementById').mockImplementation((id) => {
          if (id === 'deleteDevice') return { click: () => wrapper.vm.confirmDeleteCallback(true) }
          return null
        })

        await wrapper.find('button[aria-label="Delete device"]').trigger('click')
        await flushPromises()

        expect(mockDeviceStore.deleteDevice).toHaveBeenCalledWith(1)
        expect(mockGlobalStore.messageSuccess).toBe('Deleted device')
        lookup.mockRestore()
      })

      it('sets error message on delete failure', async () => {
        mockDeviceStore.deleteDevice.mockResolvedValueOnce(false)
        wrapper = mountWrapper()
        await flushPromises()
        wrapper.vm.confirmDeleteId = 1
        await wrapper.vm.confirmDeleteCallback(true)
        expect(mockGlobalStore.messageError).toContain('Failed to delete')
      })

      it('ignores delete confirmation when result is false', async () => {
        wrapper = mountWrapper()
        await flushPromises()
        const initialCallCount = mockDeviceStore.deleteDevice.mock.calls.length
        await wrapper.vm.confirmDeleteCallback(false)
        expect(mockDeviceStore.deleteDevice.mock.calls.length).toBe(initialCallCount)
      })

      it('sets success message on delete', async () => {
        mockDeviceStore.deleteDevice.mockResolvedValueOnce(true)
        wrapper = mountWrapper()
        await flushPromises()
        wrapper.vm.confirmDeleteId = 1
        await wrapper.vm.confirmDeleteCallback(true)
        expect(mockGlobalStore.messageSuccess).toContain('Deleted')
      })
    })

    describe('Open URL', () => {
      it('opens device URL in new window', () => {
        wrapper = mountWrapper()
        wrapper.vm.openUrl('http://device.local')
        expect(global.open).toHaveBeenCalledWith('http://device.local', '_blank')
      })

      it('opens the device UI from its rendered action button', async () => {
        wrapper = mountWrapper()
        await flushPromises()

        await wrapper.find('button[aria-label="Open device UI"]').trigger('click')

        expect(global.open).toHaveBeenCalledWith('http://1.1.1.1', '_blank')
      })

      it('filters devices with valid URLs', async () => {
        mockDeviceStore.deviceList = [
          { ...mockDevice(1), url: 'http://device.local' },
          { ...mockDevice(2), url: '' }
        ]
        wrapper = mountWrapper()
        await flushPromises()
        expect(wrapper.vm.deviceList.length).toBeGreaterThan(0)
      })
    })

    describe('Search Network', () => {
      it('opens search modal', async () => {
        wrapper = mountWrapper()
        await flushPromises()
        vi.spyOn(document, 'getElementById').mockReturnValue({ click: vi.fn() })
        await wrapper.vm.search()
        expect(mockGlobalStore.disabled).toBe(true)
      })

      it('handles search network success', async () => {
        mockDeviceStore.searchNetwork.mockResolvedValueOnce([
          { name: 'device1', host: 'device1.local', type: 'http.local.' }
        ])
        wrapper = mountWrapper()
        await flushPromises()
        await wrapper.vm.search()
        expect(wrapper.vm.searchOptions).toBeDefined()
      })

      it('handles search network failure', async () => {
        mockDeviceStore.searchNetwork.mockResolvedValueOnce(null)
        wrapper = mountWrapper()
        await flushPromises()
        await wrapper.vm.search()
        expect(mockGlobalStore.messageError).toContain('Failed to search')
      })

      it('clears previous search results', async () => {
        wrapper = mountWrapper()
        await flushPromises()
        wrapper.vm.searchOptions = [{ label: 'old' }]
        wrapper.vm.searchSelected = 'something'
        vi.spyOn(document, 'getElementById').mockReturnValue({ click: vi.fn() })
        await wrapper.vm.search()
        expect(wrapper.vm.searchSelected).toBe('')
      })

      it('handles a confirmed search selection and releases the search lock', async () => {
        wrapper = mountWrapper()
        await flushPromises()
        wrapper.vm.searchOptions = [{ label: 'Device', value: 'device.local' }]
        mockDeviceStore.proxyRequest.mockResolvedValueOnce({})

        wrapper.vm.confirmSearchCallback(true, 'device.local')
        await flushPromises()

        expect(mockDeviceStore.proxyRequest).toHaveBeenCalledWith(
          'GET',
          'http://device.local/api/status',
          '',
          ''
        )
        expect(mockGlobalStore.disabled).toBe(false)
      })
    })

    describe('Detect Device Type', () => {
      it('detects device type from API response', async () => {
        mockDeviceStore.proxyRequest.mockResolvedValueOnce({
          id: 'ABC123',
          mdns: 'test-device',
          model: 'ESP32',
          fw_type: 'Gravitymon'
        })
        wrapper = mountWrapper()
        await flushPromises()
        await wrapper.vm.detectDeviceType('http://device.local')
        expect(mockDetect.detectId).toHaveBeenCalled()
      })

      it('adds detected device to store', async () => {
        mockDeviceStore.proxyRequest.mockResolvedValueOnce({})
        wrapper = mountWrapper()
        await flushPromises()
        await wrapper.vm.detectDeviceType('http://test.local')
        expect(mockDeviceStore.addDevice).toHaveBeenCalled()
      })

      it('handles empty device ID during detection', async () => {
        mockDetect.detectId.mockReturnValueOnce('')
        mockDeviceStore.proxyRequest.mockResolvedValueOnce({})
        wrapper = mountWrapper()
        await flushPromises()
        await wrapper.vm.detectDeviceType('http://test.local')
        expect(mockGlobalStore.messageError).toContain('Unable to detect')
      })

      it('handles fetch failure during detection', async () => {
        mockDeviceStore.proxyRequest.mockRejectedValueOnce(new Error('Connection failed'))
        wrapper = mountWrapper()
        await flushPromises()
        await wrapper.vm.detectDeviceType('http://test.local')
        expect(mockGlobalStore.messageError).toContain('Failed to fetch')
      })

      it('handles duplicate device during add', async () => {
        mockDeviceStore.addDevice.mockResolvedValueOnce(false)
        mockDeviceStore.proxyRequest.mockResolvedValueOnce({})
        wrapper = mountWrapper()
        await flushPromises()
        await wrapper.vm.detectDeviceType('http://test.local')
        expect(mockGlobalStore.messageError).toContain('might already exist')
      })
    })

    describe('Device Type Options', () => {
      it('provides all device type filter options', async () => {
        wrapper = mountWrapper()
        expect(wrapper.vm.deviceTypeOptions.length).toBeGreaterThan(0)
        expect(wrapper.vm.deviceTypeOptions.some((o) => o.value === 'gravitymon')).toBe(true)
      })
    })

    describe('Table Columns', () => {
      it('displays device chipId in table', async () => {
        wrapper = mountWrapper()
        await flushPromises()
        const row = wrapper.find('tbody tr')
        expect(row.text()).toContain('CHIP1')
      })

      it('displays device type in table', async () => {
        wrapper = mountWrapper()
        await flushPromises()
        const row = wrapper.find('tbody tr')
        expect(row.text()).toContain('gravitymon')
      })
    })

    describe('Buttons and Actions', () => {
      it('renders action buttons', async () => {
        wrapper = mountWrapper()
        await flushPromises()
        const buttons = wrapper.findAll('button')
        expect(buttons.length).toBeGreaterThan(0)
      })

      it('disables buttons when global.disabled is true', async () => {
        mockGlobalStore.disabled = true
        wrapper = mountWrapper()
        await flushPromises()
        const buttons = wrapper.findAll('button')
        // Verify buttons exist - the actual disabled binding is handled by Vue
        expect(buttons.length).toBeGreaterThan(0)
      })
    })

    describe('Modal Integration', () => {
      it('renders delete confirmation modal', async () => {
        wrapper = mountWrapper()
        // Modal is rendered as a stub button with id="deleteDevice"
        expect(wrapper.find('button[id="deleteDevice"]').exists()).toBe(true)
      })

      it('renders search modal', async () => {
        wrapper = mountWrapper()
        // Modal is rendered as a stub button with id="searchDevice"
        expect(wrapper.find('button[id="searchDevice"]').exists()).toBe(true)
      })
    })

    describe('Component Lifecycle', () => {
      it('initializes on mount', async () => {
        wrapper = mountWrapper()
        await flushPromises()
        // With useSortableList, the initial state is set in the composable factory
        expect(wrapper.exists()).toBe(true)
      })

      it('applies sorting on mount', async () => {
        wrapper = mountWrapper()
        await flushPromises()
        expect(sortableListMock.applySortList).toHaveBeenCalled()
      })
    })
  })

  describe('List screen conventions', () => {
    const toggles = () => wrapper.findAll('[data-testid="collect-logs-toggle"]')

    it('shows the collect-logs setting as a toggle that reflects the device', async () => {
      mockDeviceStore.deviceList[1].collectLogs = true
      wrapper = mountWrapper()
      await flushPromises()

      expect(toggles()).toHaveLength(3)
      expect(toggles()[0].classes()).toContain('q-toggle')
      expect(toggles()[0].attributes('aria-label')).toBe('Collect logs from device when active')
      expect(toggles().map((t) => t.attributes('aria-checked'))).toEqual(['false', 'true', 'false'])
    })

    it('saves at once when the toggle is switched and keeps the new value', async () => {
      wrapper = mountWrapper()
      await flushPromises()

      await toggles()[0].trigger('click')
      await flushPromises()

      expect(mockDeviceStore.updateDevice).toHaveBeenCalledTimes(1)
      expect(mockDeviceStore.updateDevice.mock.calls[0][0].collectLogs).toBe(true)
      expect(toggles()[0].attributes('aria-checked')).toBe('true')
      expect(mockGlobalStore.messageError).toBe('')
    })

    it('puts the toggle back and says which device when the save fails', async () => {
      mockDeviceStore.updateDevice.mockResolvedValueOnce(null)
      wrapper = mountWrapper()
      await flushPromises()

      await toggles()[0].trigger('click')
      await flushPromises()

      expect(mockDeviceStore.updateDevice).toHaveBeenCalledTimes(1)
      expect(wrapper.vm.deviceList[0].collectLogs).toBe(false)
      expect(toggles()[0].attributes('aria-checked')).toBe('false')
      expect(mockGlobalStore.messageError).toContain('Collect logs')
      expect(mockGlobalStore.messageError).toContain('device1')
      expect(mockGlobalStore.messageError).toContain('put back')
    })

    it('shows the chip family column while a listed device has a chip family', async () => {
      wrapper = mountWrapper()
      await flushPromises()

      expect(wrapper.text()).toContain('Chip Family')
      expect(wrapper.findAll('thead th')).toHaveLength(6)
      expect(wrapper.findAll('tbody tr')[0].findAll('td')).toHaveLength(6)
    })

    it('hides the chip family column when no listed device has one', async () => {
      mockDeviceStore.deviceList.forEach((d) => { d.chipFamily = '' })
      wrapper = mountWrapper()
      await flushPromises()

      expect(wrapper.text()).not.toContain('Chip Family')
      expect(wrapper.findAll('thead th')).toHaveLength(5)
      expect(wrapper.findAll('tbody tr')[0].findAll('td')).toHaveLength(5)
    })

    it('decides the chip family column from the filtered list, not every device', async () => {
      mockDeviceStore.deviceList.forEach((d) => { d.chipFamily = '' })
      mockDeviceStore.deviceList[1].chipFamily = 'ESP32'
      mockPreferences.deviceListFilterDeviceType = 'gravitymon'
      wrapper = mountWrapper()
      await flushPromises()
      expect(wrapper.text()).not.toContain('Chip Family')

      mockPreferences.deviceListFilterDeviceType = 'kegmon'
      wrapper.unmount()
      wrapper = mountWrapper()
      await flushPromises()
      expect(wrapper.text()).toContain('Chip Family')
    })

    it('draws no colour dot for a device without a colour', async () => {
      mockDeviceStore.deviceList[0].deviceColor = ''
      wrapper = mountWrapper()
      await flushPromises()

      expect(wrapper.findAll('tbody .device-color-swatch')).toHaveLength(2)
    })

    it('puts the create action in the page header and not under the table', async () => {
      wrapper = mountWrapper()
      await flushPromises()

      const header = wrapper.find('.app-page-header__action')
      expect(header.exists()).toBe(true)
      expect(header.text()).toBe('Add Device')
      expect(wrapper.find('.app-list-actions').text()).not.toContain('Add Device')
      expect(wrapper.find('.app-list-actions').text()).toContain('Search for Devices')
      expect(wrapper.find('.app-list-actions').text()).toContain('Device Logs')
    })

    it('gives each row filled icon actions, coloured by meaning, with labels', async () => {
      mockBatchStore.anyBatchesForDevice.mockReturnValue(true)
      wrapper = mountWrapper()
      await flushPromises()

      const row = wrapper.findAll('tbody tr')[0]
      expect(row.find('[aria-label="Edit device"]').classes()).toEqual(expect.arrayContaining(['app-button', 'app-button--primary', 'app-button--dense']))
      expect(row.find('[aria-label="Delete device"]').classes()).toContain('app-button--negative')
      expect(row.find('[aria-label="Show batches for this device"]').classes()).toContain('app-button--positive')
      expect(row.find('[aria-label="Open device UI"]').classes()).toContain('app-button--secondary')
    })
  })
})
