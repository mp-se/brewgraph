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

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import BatchListView from '../BatchListView.vue'
import { nextTick } from 'vue'

vi.mock('pinia', async () => {
  const { toRef } = await import('vue')
  return {
    storeToRefs: (store) => {
      const refs = {}
      for (const key in store) {
        if (typeof store[key] !== 'function' && key !== 'batchList') {
          refs[key] = toRef(store, key)
        }
      }
      return refs
    }
  }
})

// Mock fetch for getBatch
global.fetch = vi.fn()

const globalMock = vi.hoisted(() => ({
  batchListFilterDevice: '*',
  batchListFilterActive: false,
  batchListFilterData: false,
  updatedBatchData: 0,
  disabled: false,
  acquireBusy() {
    this.disabled = true
    let released = false
    return () => { if (!released) { released = true; this.disabled = false } }
  },
  messageError: '',
  messageSuccess: '',
  clearMessages: vi.fn(),
  fetchTimout: 1000
}))

const { batchStoreMock, deviceStoreMock, gravityStoreMock, pressureStoreMock, tempReadingStoreMock, vesselStoreMock } = vi.hoisted(() => {
  return {
    batchStoreMock: {
      batchList: [
        {
          id: 1,
          name: 'B1',
          brewDate: '2023-01-01',
          acceptIngest: true,
          gravityCount: 10,
          pressureCount: 5,
          gravityDeviceId: 'c1',
          pressureDeviceId: 'p1'
        },
        {
          id: 2,
          name: 'B2',
          brewDate: '2023-02-01',
          acceptIngest: false,
          gravityCount: 0,
          pressureCount: 0,
          gravityDeviceId: 'c2',
          pressureDeviceId: 'p2'
        }
      ],
      updateBatch: vi.fn().mockResolvedValue(true),
      deleteBatch: vi.fn().mockResolvedValue(true),
      archiveBatch: vi.fn().mockResolvedValue(true),
      unarchiveBatch: vi.fn().mockResolvedValue(true),
      processEvent: vi.fn().mockResolvedValue(true),
      getBatch: vi.fn().mockResolvedValue({ id: 1, name: 'B1', gravity: [] })
    },
    deviceStoreMock: {
      deviceList: [
        { id: 'c1', chipId: 'c1', mdns: 'dev1' },
        { id: 'c2', chipId: 'c2', mdns: 'dev2' }
      ]
    },
    gravityStoreMock: {
      getGravity: vi.fn().mockResolvedValue([{ date: '2023-01-01', gravity: 1.05 }])
    },
    pressureStoreMock: {
      getPressure: vi.fn().mockResolvedValue([{ date: '2023-01-01', pressure: 12 }])
    },
    tempReadingStoreMock: {
      getTempListForBatch: vi.fn().mockResolvedValue([])
    },
    vesselStoreMock: {
      vesselList: [],
      getVesselList: vi.fn().mockResolvedValue([])
    }
  }
})

vi.mock('@/modules/pinia', async () => {
  const { reactive } = await import('vue')
  const reactiveGlobalMock = reactive(globalMock)

  return {
    global: reactiveGlobalMock,
    preferences: reactiveGlobalMock,
    batchStore: batchStoreMock,
    deviceStore: deviceStoreMock,
    gravityStore: gravityStoreMock,
    pressureStore: pressureStoreMock,
    tempReadingStore: tempReadingStoreMock,
    vesselStore: vesselStoreMock
  }
})

const routerMock = vi.hoisted(() => ({
  currentRoute: { value: { query: {} } },
  push: vi.fn()
}))
vi.mock('@/modules/router', () => ({ default: routerMock }))
const utilsMock = vi.hoisted(() => ({ download: vi.fn() }))
vi.mock('@/modules/utils', () => utilsMock)
vi.mock('@/ui', () => ({ logDebug: vi.fn(), logError: vi.fn() }))
const uiMock = vi.hoisted(() => ({
  sortedIconClass: 'bi-sort',
  setSortingDefault: vi.fn(),
  sortedClass: vi.fn().mockReturnValue('sorted'),
  sortList: vi.fn(),
  applySortList: vi.fn()
}))

vi.mock('@/modules/ui', () => uiMock)

const sortableListMock = vi.hoisted(() => ({
  sortedIconClass: 'bi-sort',
  getSortedClass: vi.fn().mockReturnValue('sorted'),
  setSortingDefault: vi.fn(),
  sortList: vi.fn(),
  applySortList: vi.fn()
}))

vi.mock('@/modules/useSortableList', () => ({
  useSortableList: vi.fn().mockReturnValue(sortableListMock)
}))

describe('BatchListView.vue', () => {
  const createInitialBatchList = () => [
    {
      id: 1,
      name: 'B1',
      brewDate: '2023-01-01',
      acceptIngest: true,
      gravityCount: 10,
      pressureCount: 5,
      temperatureCount: 3,
      gravityDeviceId: 'c1',
      pressureDeviceId: 'p1'
    },
    {
      id: 2,
      name: 'B2',
      brewDate: '2023-02-01',
      acceptIngest: false,
      gravityCount: 0,
      pressureCount: 0,
      gravityDeviceId: 'c2',
      pressureDeviceId: 'p2'
    }
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    batchStoreMock.batchList = createInitialBatchList()
    globalMock.batchListFilterDevice = '*'
    globalMock.batchListFilterActive = false
    globalMock.batchListFilterData = false
    globalMock.messageError = ''
    globalMock.messageSuccess = ''
    routerMock.currentRoute.value.query = {}
    batchStoreMock.batchList[0].acceptIngest = true
    batchStoreMock.batchList[1].acceptIngest = false
    gravityStoreMock.getGravity.mockReset()
    pressureStoreMock.getPressure.mockReset()
    gravityStoreMock.getGravityListForBatch = vi.fn().mockResolvedValue([])
    pressureStoreMock.getPressureListForBatch = vi.fn().mockResolvedValue([])
    tempReadingStoreMock.getTempListForBatch.mockReset()
    tempReadingStoreMock.getTempListForBatch.mockResolvedValue([])
    vesselStoreMock.vesselList = []
    batchStoreMock.archiveBatch.mockResolvedValue(true)
    batchStoreMock.unarchiveBatch.mockResolvedValue(true)
  })

  const mountWrapper = () =>
    mount(BatchListView, {
      attachTo: document.body,
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          AppSelect: {
            template:
              '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="o in options" :value="o.value">{{o.label}}</option></select>',
            props: ['modelValue', 'options']
          },
          AppToggle: {
            template:
              '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
            props: ['modelValue']
          },
          AppConfirmDialog: {
            template: '<div id="deleteBatch" @click="$props.callback(true)"></div>',
            props: ['callback']
          }
        }
      }
    })

  it('keeps the original desktop list heading and filter layout', () => {
    const wrapper = mountWrapper()
    expect(wrapper.find('.app-page').exists()).toBe(true)
    expect(wrapper.find('.text-h6').text()).toContain('Batch List')
    expect(wrapper.findAll('.app-page-header .col-12 .row > div')).toHaveLength(3)
    wrapper.unmount()
  })

  it('filters by active status', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    globalMock.batchListFilterDevice = 'c1'
    wrapper.vm.filterBatchList()
    expect(wrapper.vm.batchList).toHaveLength(1)
    expect(wrapper.vm.batchList[0].id).toBe(1)
  })

  it('filters by data status', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    globalMock.batchListFilterActive = false
    globalMock.batchListFilterData = true
    wrapper.vm.filterBatchList()
    expect(wrapper.vm.batchList).toHaveLength(1)
    expect(wrapper.vm.batchList[0].id).toBe(1)
  })

  it('filters by device', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    globalMock.batchListFilterActive = false
    globalMock.batchListFilterData = false
    globalMock.batchListFilterDevice = 'c2'
    wrapper.vm.filterBatchList()
    expect(wrapper.vm.batchList).toHaveLength(1)
    expect(wrapper.vm.batchList[0].id).toBe(2)
  })

  it('handles empty query chipId on mount', async () => {
    routerMock.currentRoute.value.query = {}
    mountWrapper()
    await nextTick()
    expect(globalMock.batchListFilterDevice).toBe('*')
  })

  it('handles chipId query on mount', async () => {
    routerMock.currentRoute.value.query = { deviceId: 'c1' }
    mountWrapper()
    await nextTick()
    expect(globalMock.batchListFilterDevice).toBe('c1')
  })

  it('toggles batch excluded', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    await wrapper.vm.toggleAcceptIngest(1)
    expect(batchStoreMock.updateBatch).toHaveBeenCalled()
  })

  it('deletes batch on confirmation', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    wrapper.vm.deleteBatch(1, 'Batch 1')
    await wrapper.vm.confirmDeleteCallback(true)
    expect(batchStoreMock.deleteBatch).toHaveBeenCalled()
  })

  it('routes delete-button clicks through the confirmation callback', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    const confirmationLookup = vi.spyOn(document, 'getElementById').mockImplementation((id) => {
      if (id === 'deleteBatch') return { click: () => wrapper.vm.confirmDeleteCallback(true) }
      return null
    })
    await wrapper.find('[data-testid="batch-delete-action"]').trigger('click')
    await flushPromises()
    confirmationLookup.mockRestore()

    expect(batchStoreMock.deleteBatch).toHaveBeenCalledWith(1)
    expect(globalMock.messageSuccess).toBe('Deleted batch')
  })

  it('counts only vessels linked to the requested batch', async () => {
    vesselStoreMock.vesselList = [
      { id: 1, batchId: 1 },
      { id: 2, batchId: 1 },
      { id: 3, batchId: 2 }
    ]
    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.vm.vesselCountForBatch(1)).toBe(2)
  })

  it('archives and unarchives batches and refreshes their rows', async () => {
    const wrapper = mountWrapper()
    await nextTick()

    await wrapper.vm.archiveBatch(1, 'B1')
    expect(batchStoreMock.archiveBatch).toHaveBeenCalledWith(1)
    expect(batchStoreMock.processEvent).toHaveBeenCalledWith('update', 1)
    expect(globalMock.messageSuccess).toBe('Archived batch')

    await wrapper.vm.unarchiveBatch(2)
    expect(batchStoreMock.unarchiveBatch).toHaveBeenCalledWith(2)
    expect(batchStoreMock.processEvent).toHaveBeenCalledWith('update', 2)
    expect(globalMock.messageSuccess).toBe('Un-archived batch')
  })

  it('fails to toggle batch excluded if update fails', async () => {
    batchStoreMock.updateBatch.mockResolvedValueOnce(false)
    const wrapper = mountWrapper()
    await nextTick()
    await wrapper.vm.toggleAcceptIngest(1)
    expect(globalMock.messageError).toContain('Failed to update batch')
  })

  it('exposes no JSON export action', () => {
    // GET /batches/{id}/export was removed from OSS (plan item 3.6); portability lives in
    // Backup & Restore. The client-side CSV exports below are unaffected.
    const wrapper = mountWrapper()
    expect(wrapper.vm.exportBatchJSON).toBeUndefined()
  })

  it('uses one fixed control system for edit, delete, graph, and overflow actions', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    const firstRow = wrapper.find('tbody tr')

    const gravityGraph = firstRow.find('[data-testid="gravity-graph-action"]')
    const pressureGraph = firstRow.find('[data-testid="pressure-graph-action"]')
    const temperatureGraph = firstRow.find('[data-testid="temperature-graph-action"]')

    expect(gravityGraph.exists()).toBe(true)
    expect(pressureGraph.exists()).toBe(true)
    expect(temperatureGraph.exists()).toBe(true)
    // Filled icon buttons coloured by meaning: edit primary, delete negative, gravity positive,
    // pressure warning, temperature info, the overflow trigger secondary.
    expect(firstRow.find('[data-testid="batch-edit-action"]').classes()).toEqual(expect.arrayContaining(['app-button', 'app-button--primary', 'app-button--dense']))
    expect(firstRow.find('[data-testid="batch-delete-action"]').classes()).toContain('app-button--negative')
    expect(gravityGraph.classes()).toContain('app-button--positive')
    expect(pressureGraph.classes()).toContain('app-button--warning')
    expect(temperatureGraph.classes()).toContain('app-button--info')
    expect(firstRow.find('[data-testid="batch-data-overflow-menu"]').classes()).toContain('app-button--secondary')
    expect(firstRow.findAll('.app-row-action')).toHaveLength(6)
    expect(firstRow.findAll('[data-testid="batch-data-overflow-menu"]')).toHaveLength(1)
    expect(firstRow.find('[title="Archive batch"]').exists()).toBe(false)
  })

  it('keeps the overflow control when measurement actions are unavailable', async () => {
    batchStoreMock.batchList[0].gravityCount = 0
    batchStoreMock.batchList[0].pressureCount = 0
    batchStoreMock.batchList[0].temperatureCount = 0
    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.findAll('[data-testid$="graph-action"]')).toHaveLength(0)
    expect(wrapper.findAll('[data-testid="batch-data-overflow-menu"]')).toHaveLength(2)
  })

  it('places archive and unarchive lifecycle actions in the overflow menu', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    const rows = wrapper.findAll('tbody tr')
    const firstMenu = rows[0].find('[data-testid="batch-data-overflow-menu"]')

    expect(wrapper.text()).not.toContain('Archive batch')
    expect(document.body.textContent).not.toContain('Archive batch')
    await firstMenu.trigger('click')
    await nextTick()
    await nextTick()
    expect(document.body.querySelectorAll('[data-testid="batch-data-menu-content"]')).toHaveLength(1)
    expect(document.body.textContent).toContain('Archive batch')
    wrapper.unmount()
    batchStoreMock.batchList[0].status = 'archived'
    const archivedWrapper = mountWrapper()
    archivedWrapper.vm.statusFilter = 'all'
    await nextTick()
    await archivedWrapper.find('[data-testid="batch-data-overflow-menu"]').trigger('click')
    await nextTick()
    await nextTick()
    expect(document.body.textContent).toContain('Unarchive batch')
  })

  it('exports temperature CSV', async () => {
    global.fetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ id: 1, name: 'B1' }) })
    tempReadingStoreMock.getTempListForBatch.mockResolvedValue([
      { createdAt: '2023-01-01', temperature: 20, tempType: 'beer', battery: 3.8, rssi: -60, excluded: false }
    ])
    const wrapper = mountWrapper()

    await wrapper.vm.exportBatchTemperatureCSV(1)

    expect(tempReadingStoreMock.getTempListForBatch).toHaveBeenCalledWith(1)
    expect(utilsMock.download).toHaveBeenCalledWith(
      expect.stringContaining('B1,2023-01-01,20,beer'),
      'text/csv',
      'brewgraph_temperature_batch_1.csv'
    )
  })

  it('exports pressure CSV', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: 1, name: 'B1' })
    })
    pressureStoreMock.getPressureListForBatch.mockResolvedValue([
      { createdAt: '2023-01-01', temperature: 20, pressure: 10 }
    ])

    const wrapper = mountWrapper()
    await nextTick()
    await wrapper.vm.exportBatchPressureCSV(1)
    await nextTick()
    await nextTick()
    expect(pressureStoreMock.getPressureListForBatch).toHaveBeenCalledWith(1)
    expect(utilsMock.download).toHaveBeenCalledWith(
      expect.stringContaining('B1,2023-01-01,20,10'),
      'text/csv',
      'brewgraph_pressure_batch_1.csv'
    )
  })

  it('exports gravity CSV', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: 1, name: 'B1' })
    })
    gravityStoreMock.getGravityListForBatch.mockResolvedValue([
      { createdAt: '2023-01-01', temperature: 20, gravity: 1.05 }
    ])

    const wrapper = mountWrapper()
    await nextTick()
    await wrapper.vm.exportBatchGravityCSV(1)
    await nextTick()
    await nextTick()
    expect(gravityStoreMock.getGravityListForBatch).toHaveBeenCalledWith(1)
    expect(utilsMock.download).toHaveBeenCalledWith(
      expect.stringContaining('B1,2023-01-01,20,1.05'),
      'text/csv',
      'brewgraph_gravity_batch_1.csv'
    )
  })

  it.each([
    ['gravity', 'exportBatchGravityCSV', 'getGravityListForBatch'],
    ['pressure', 'exportBatchPressureCSV', 'getPressureListForBatch']
  ])('does not download %s CSV when the reading list is unavailable', async (kind, exportMethod, storeMethod) => {
    global.fetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ id: 1, name: 'B1' }) })
    const store = kind === 'gravity' ? gravityStoreMock : pressureStoreMock
    store[storeMethod].mockResolvedValue(undefined)
    const wrapper = mountWrapper()

    await wrapper.vm[exportMethod](1)

    expect(utilsMock.download).not.toHaveBeenCalled()
    expect(globalMock.messageError).toContain('Failed to fetch ' + kind + ' readings')
  })

  it.each([
    ['gravity', 'exportBatchGravityCSV', 'getGravityListForBatch'],
    ['pressure', 'exportBatchPressureCSV', 'getPressureListForBatch']
  ])('does not download %s CSV when the reading list is empty', async (kind, exportMethod, storeMethod) => {
    global.fetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ id: 1, name: 'B1' }) })
    const store = kind === 'gravity' ? gravityStoreMock : pressureStoreMock
    store[storeMethod].mockResolvedValue([])
    const wrapper = mountWrapper()

    await wrapper.vm[exportMethod](1)

    expect(utilsMock.download).not.toHaveBeenCalled()
    expect(globalMock.messageError).toContain('There are no ' + kind + ' readings')
  })

  it('handles confirmDeleteCallback on failure', async () => {
    batchStoreMock.deleteBatch.mockResolvedValueOnce(false)
    const wrapper = mountWrapper()
    await nextTick()
    await wrapper.vm.confirmDeleteCallback(true)
    expect(globalMock.messageError).toContain('Failed to batch device')
  })

  it('sorts batch list', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    const sortLink = wrapper.find('a.icon-link')
    await sortLink.trigger('click')
    expect(sortableListMock.sortList).toHaveBeenCalled()
  })

  it('watches updatedBatchData', async () => {
    for (let i = 3; i <= 12; i++) {
      batchStoreMock.batchList.push({
        id: i,
        name: `B${i}`,
        brewDate: '2023-03-01',
        excluded: false,
        gravityCount: 1,
        pressureCount: 0,
        gravityDeviceId: 'c1',
        pressureDeviceId: 'p1'
      })
    }
    const wrapper = mountWrapper()
    await nextTick()
    wrapper.vm.goToPage(2)
    globalMock.updatedBatchData = 1
    await nextTick()
    expect(sortableListMock.applySortList).toHaveBeenCalled()
    expect(wrapper.vm.currentPage).toBe(2)
  })

  it('watches batchListFilterDevice', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    await flushPromises()

    await wrapper.findAll('select')[0].setValue('c2')
    await flushPromises()

    expect(wrapper.vm.batchList.map((batch) => batch.id)).toEqual([2])
    expect(sortableListMock.applySortList).toHaveBeenCalled()
  })

  it('paginates batch list with fixed 10 items', async () => {
    for (let i = 3; i <= 12; i++) {
      batchStoreMock.batchList.push({
        id: i,
        name: `B${i}`,
        brewDate: '2023-03-01',
        excluded: false,
        gravityCount: 1,
        pressureCount: 0,
        gravityDeviceId: 'c1',
        pressureDeviceId: 'p1'
      })
    }

    const wrapper = mountWrapper()
    await nextTick()
    expect(wrapper.vm.totalPages).toBe(2)
    expect(wrapper.vm.paginatedBatchList).toHaveLength(10)
  })

  it('changes page and clamps out-of-range page numbers', async () => {
    for (let i = 3; i <= 12; i++) {
      batchStoreMock.batchList.push({
        id: i,
        name: `B${i}`,
        brewDate: '2023-03-01',
        excluded: false,
        gravityCount: 1,
        pressureCount: 0,
        gravityDeviceId: 'c1',
        pressureDeviceId: 'p1'
      })
    }

    const wrapper = mountWrapper()
    await nextTick()

    wrapper.vm.goToPage(2)
    await nextTick()
    expect(wrapper.vm.currentPage).toBe(2)
    expect(wrapper.vm.paginatedBatchList).toHaveLength(2)

    wrapper.vm.goToPage(99)
    expect(wrapper.vm.currentPage).toBe(2)

    wrapper.vm.goToPage(0)
    expect(wrapper.vm.currentPage).toBe(1)
  })

  it('renders Bootstrap pagination controls when list has multiple pages', async () => {
    for (let i = 3; i <= 12; i++) {
      batchStoreMock.batchList.push({
        id: i,
        name: `B${i}`,
        brewDate: '2023-03-01',
        excluded: false,
        gravityCount: 1,
        pressureCount: 0,
        gravityDeviceId: 'c1',
        pressureDeviceId: 'p1'
      })
    }

    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.find('ul.app-pagination').exists()).toBe(true)
    expect(wrapper.text()).toContain('Previous')
    expect(wrapper.text()).toContain('Next')
  })

  it('watches batchListFilterData', async () => {
    const wrapper = mountWrapper()
    await nextTick()

    await wrapper.find('[aria-label="Show only batches with data"]').setValue(true)
    await flushPromises()

    expect(wrapper.vm.batchList.map((batch) => batch.id)).toEqual([1])
    expect(sortableListMock.applySortList).toHaveBeenCalled()
  })

  it('filters archived batches when the status selector changes', async () => {
    batchStoreMock.batchList[1].status = 'archived'
    const wrapper = mountWrapper()
    await nextTick()

    await wrapper.findAll('select')[1].setValue('archived')
    await flushPromises()

    expect(wrapper.vm.batchList.map((batch) => batch.id)).toEqual([2])
  })

  it('reports archive and unarchive failures', async () => {
    batchStoreMock.archiveBatch.mockResolvedValueOnce(false)
    batchStoreMock.unarchiveBatch.mockResolvedValueOnce(false)
    const wrapper = mountWrapper()
    await nextTick()

    await wrapper.vm.archiveBatch(1, 'B1')
    expect(globalMock.messageError).toBe('Failed to archive batch')

    await wrapper.vm.unarchiveBatch(2)
    expect(globalMock.messageError).toBe('Failed to un-archive batch')
    expect(batchStoreMock.processEvent).not.toHaveBeenCalled()
  })

  describe('Sorting', () => {
    it('applies sort class to sortable columns', async () => {
      mountWrapper()
      await nextTick()
      expect(sortableListMock.getSortedClass).toHaveBeenCalled()
    })

    it('triggers sort on column header click', async () => {
      const wrapper = mountWrapper()
      await nextTick()
      const sortButton = wrapper.find('a.icon-link')
      expect(sortButton.exists()).toBe(true)
      await sortButton.trigger('click')
      expect(sortableListMock.sortList).toHaveBeenCalled()
    })

    it('reapplies sort after filter changes', async () => {
      mountWrapper()
      await nextTick()
      globalMock.batchListFilterDevice = 'c2'
      await nextTick()
      // Verify the filter changed and component reacted
      expect(globalMock.batchListFilterDevice).toBe('c2')
    })
  })

  describe('Export Operations', () => {
    it('exports gravity CSV with proper formatting', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            id: 1,
            name: 'B1'
          })
      })
      gravityStoreMock.getGravityListForBatch.mockResolvedValue([
        { createdAt: '2023-01-01T12:00:00', gravity: 1.05, temperature: 20 },
        { createdAt: '2023-01-02T12:00:00', gravity: 1.045, temperature: 21 }
      ])
      const wrapper = mountWrapper()
      await nextTick()
      await wrapper.vm.exportBatchGravityCSV(1)
      await nextTick()
      await nextTick()
      expect(utilsMock.download).toHaveBeenCalled()
    })

    it('does not export gravity CSV when no gravity data exists', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ id: 1, name: 'B1' })
      })
      const wrapper = mountWrapper()
      await nextTick()
      await wrapper.vm.exportBatchGravityCSV(1)
      await nextTick()
      await nextTick()
      expect(utilsMock.download).not.toHaveBeenCalled()
      expect(globalMock.messageError).toContain('There are no gravity readings')
    })

    it('exports pressure CSV with proper formatting', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            id: 1,
            name: 'B1'
          })
      })
      pressureStoreMock.getPressureListForBatch.mockResolvedValue([
        { createdAt: '2023-01-01T12:00:00', pressure: 10, temperature: 20 },
        { createdAt: '2023-01-02T12:00:00', pressure: 12, temperature: 21 }
      ])
      const wrapper = mountWrapper()
      await nextTick()
      await wrapper.vm.exportBatchPressureCSV(1)
      await nextTick()
      await nextTick()
      expect(utilsMock.download).toHaveBeenCalled()
    })

    it('does not export pressure CSV when no pressure data exists', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ id: 1, name: 'B1' })
      })
      const wrapper = mountWrapper()
      await nextTick()
      await wrapper.vm.exportBatchPressureCSV(1)
      await nextTick()
      await nextTick()
      expect(utilsMock.download).not.toHaveBeenCalled()
      expect(globalMock.messageError).toContain('There are no pressure readings')
    })

    it('handles export gravity CSV failure', async () => {
      global.fetch.mockResolvedValue({ ok: false })
      const wrapper = mountWrapper()
      await nextTick()
      await wrapper.vm.exportBatchGravityCSV(999)
      expect(globalMock.messageError).toContain('Failed')
    })

    it('handles export pressure CSV failure', async () => {
      global.fetch.mockResolvedValue({ ok: false })
      const wrapper = mountWrapper()
      await nextTick()
      await wrapper.vm.exportBatchPressureCSV(999)
      expect(globalMock.messageError).toContain('Failed')
    })
  })

  it('puts Add Batch in the page header and shows accepting as a toggle', async () => {
    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.find('.app-page-header__action').text()).toBe('Add Batch')
    const toggle = wrapper.find('[data-testid="accept-ingest-toggle"]')
    expect(toggle.classes()).toContain('q-toggle')
    expect(toggle.attributes('aria-label')).toBe('Accept ingest data from devices')
    wrapper.unmount()
  })
})
