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

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick, ref } from 'vue'
import VesselListView from '../VesselListView.vue'

const mockRoute = {
  query: {}
}

const { globalMock, vesselStoreMock, batchStoreMock, sortableListMock } = vi.hoisted(() => ({
  globalMock: {
    disabled: false,
    clearMessages: vi.fn(),
    messageSuccess: '',
    messageError: '',
    updatedVesselData: 0
  },
  vesselStoreMock: {
    vesselList: [],
    deleteVessel: vi.fn().mockResolvedValue(true),
    processEvent: vi.fn().mockResolvedValue(true)
  },
  batchStoreMock: {
    batchList: []
  },
  sortableListMock: {
    sortedIconClass: 'bi-sort',
    getSortedClass: vi.fn().mockReturnValue('sorted'),
    sortList: vi.fn(),
    applySortList: vi.fn()
  }
}))

vi.mock('pinia', () => ({
  storeToRefs: () => ({
    updatedVesselData: ref(globalMock.updatedVesselData)
  })
}))

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute
}))

vi.mock('@/modules/pinia', () => ({
  global: globalMock,
  vesselStore: vesselStoreMock,
  batchStore: batchStoreMock
}))

vi.mock('@/modules/useSortableList', () => ({
  useSortableList: vi.fn().mockReturnValue(sortableListMock)
}))

vi.mock('@/ui', () => ({
  logDebug: vi.fn()
}))

describe('VesselListView', () => {
  const mountWrapper = () =>
    mount(VesselListView, {
      attachTo: document.body,
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          AppSelect: {
            props: ['label', 'modelValue', 'options'],
            template:
              '<label>{{ label }}<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>'
          },
          AppProgress: true,
          AppConfirmDialog: {
            template:
              '<button id="deleteVessel" type="button" hidden @click="callback(true)"></button>',
            props: ['callback']
          }
        }
      }
    })

  beforeEach(() => {
    vi.clearAllMocks()
    mockRoute.query = {}
    batchStoreMock.batchList = []
    vesselStoreMock.vesselList = Array.from({ length: 12 }, (_, idx) => ({
      id: `vessel-${idx + 1}`,
      name: `Vessel ${idx + 1}`,
      vesselType: 'keg',
      status: idx % 2 === 0 ? 'serving' : 'clean',
      volumeRemaining: 10,
      totalVolume: 20,
      pourCount: idx === 0 ? 2 : 0,
      batchId: idx < 2 ? `batch-${idx + 1}` : null
    }))
    vesselStoreMock.deleteVessel.mockResolvedValue(true)
    vesselStoreMock.processEvent.mockResolvedValue(true)
  })

  afterEach(() => {
    document.body.replaceChildren()
    vi.restoreAllMocks()
  })

  it('paginates vessels with fixed 10 items per page', async () => {
    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.vm.totalPages).toBe(2)
    expect(wrapper.vm.paginatedFilteredVesselList).toHaveLength(10)
  })

  it('places both filters in the top page toolbar', async () => {
    const wrapper = mountWrapper()
    await nextTick()

    const toolbar = wrapper.findComponent({ name: 'AppPageHeader' })
    expect(toolbar.exists()).toBe(true)
    expect(toolbar.props('title')).toBe('Vessels')
    expect(toolbar.findAll('select')).toHaveLength(2)
  })

  it('renders Bootstrap pagination controls for multiple pages', async () => {
    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.find('ul.app-pagination').exists()).toBe(true)
    expect(wrapper.text()).toContain('Previous')
    expect(wrapper.text()).toContain('Next')
  })

  it('changes page and clamps out-of-range page numbers', async () => {
    const wrapper = mountWrapper()
    await nextTick()

    wrapper.vm.goToPage(2)
    expect(wrapper.vm.currentPage).toBe(2)
    expect(wrapper.vm.paginatedFilteredVesselList).toHaveLength(2)

    wrapper.vm.goToPage(99)
    expect(wrapper.vm.currentPage).toBe(2)

    wrapper.vm.goToPage(0)
    expect(wrapper.vm.currentPage).toBe(1)
  })

  it('applies route filters, including the first value of query arrays', async () => {
    mockRoute.query = { batchId: ['batch-2', 'batch-1'], status: ['clean', 'serving'] }
    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.vm.batchFilter).toBe('batch-2')
    expect(wrapper.vm.statusFilter).toBe('clean')
    expect(wrapper.vm.filteredVesselList.map((vessel) => vessel.id)).toEqual(['vessel-2'])
  })

  it('filters by selected status and batch, and resets pagination when filters change', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    wrapper.vm.goToPage(2)
    wrapper.vm.batchFilter = 'batch-1'
    await nextTick()
    expect(wrapper.vm.currentPage).toBe(1)
    expect(wrapper.vm.filteredVesselList.map((vessel) => vessel.id)).toEqual(['vessel-1'])

    await wrapper.findAll('select')[0].setValue('clean')
    await nextTick()
    expect(wrapper.vm.filteredVesselList).toEqual([])
  })

  it('builds batch filter options from the batch store', async () => {
    batchStoreMock.batchList = [
      { id: 'batch-1', name: 'First batch' },
      { id: 'batch-2', name: 'Second batch' }
    ]
    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.vm.batchFilterOptions).toEqual([
      { label: 'All batches', value: 'all' },
      { label: 'First batch', value: 'batch-1' },
      { label: 'Second batch', value: 'batch-2' }
    ])
  })

  it('computes keg volume progress with safe bounds', async () => {
    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.vm.volumeProgress({ totalVolume: 0, volumeRemaining: 2 })).toBe(0)
    expect(wrapper.vm.volumeProgress({ totalVolume: 20, volumeRemaining: 10 })).toBe(50)
    expect(wrapper.vm.volumeProgress({ totalVolume: 20, volumeRemaining: 30 })).toBe(100)
    expect(wrapper.vm.volumeProgress({ totalVolume: 20, volumeRemaining: -2 })).toBe(0)
  })

  it('maps vessel statuses and normalizes optional batch links', async () => {
    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.vm.statusBadgeClass('serving')).toContain('positive')
    expect(wrapper.vm.statusBadgeClass('clean')).toContain('secondary')
    expect(wrapper.vm.statusBadgeClass('unknown')).toContain('secondary')
    expect(wrapper.vm.getBatchIdForRoute(null)).toBe(null)
    expect(wrapper.vm.getBatchIdForRoute(' undefined ')).toBe(null)
    expect(wrapper.vm.getBatchIdForRoute(' batch-1 ')).toBe('batch-1')
  })

  it('sorts by vessel number and name using the rendered column controls', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    const sortLinks = wrapper.findAll('a.icon-link')
    expect(sortLinks).toHaveLength(2)

    for (const link of sortLinks) await link.trigger('click')

    expect(sortableListMock.sortList).toHaveBeenCalledTimes(2)
  })

  it('changes pages through the rendered pagination controls', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    await wrapper.find('button[aria-label="Next page"]').trigger('click')
    expect(wrapper.vm.currentPage).toBe(2)
    await wrapper.find('button[aria-label="Previous page"]').trigger('click')
    expect(wrapper.vm.currentPage).toBe(1)
    await wrapper.find('button[aria-label="Page 2"]').trigger('click')
    expect(wrapper.vm.currentPage).toBe(2)
  })

  it('renders keg and bottle volume states and conditional vessel actions', async () => {
    vesselStoreMock.vesselList = [
      { ...vesselStoreMock.vesselList[0], vesselType: 'keg', batchId: 'batch-1', pourCount: 2 },
      {
        ...vesselStoreMock.vesselList[1],
        vesselType: 'bottle',
        batchId: null,
        pourCount: 0,
        bottlesRemaining: 4,
        bottleCount: 12
      },
      {
        ...vesselStoreMock.vesselList[2],
        vesselType: 'bottle',
        batchId: null,
        pourCount: 0,
        bottlesRemaining: null
      }
    ]
    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.text()).toContain('10.0 / 20.0 L')
    expect(wrapper.text()).toContain('4 / 12 bottles')
    expect(wrapper.text()).toContain('—')
    expect(wrapper.find('button[aria-label="Open batch"]').exists()).toBe(true)
    expect(wrapper.find('button[aria-label="Show pour list"]').exists()).toBe(true)
    expect(wrapper.findAll('button[aria-label="Open batch"]')).toHaveLength(1)
  })

  it('deletes through confirmation and refreshes the vessel list', async () => {
    const wrapper = mountWrapper()
    await nextTick()

    await wrapper.find('button[aria-label="Delete vessel"]').trigger('click')
    await flushPromises()

    expect(vesselStoreMock.deleteVessel).toHaveBeenCalledWith('vessel-1')
    expect(vesselStoreMock.processEvent).toHaveBeenCalledWith('delete', 'vessel-1')
    expect(globalMock.messageSuccess).toBe('Vessel deleted')
  })

  it('reports a failed deletion and ignores a cancelled confirmation', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    vesselStoreMock.deleteVessel.mockResolvedValueOnce(false)
    wrapper.vm.confirmDeleteId = 'vessel-2'
    await wrapper.vm.confirmDeleteCallback(true)

    expect(globalMock.messageError).toBe('Failed to delete vessel')
    const callsBeforeCancel = vesselStoreMock.deleteVessel.mock.calls.length
    await wrapper.vm.confirmDeleteCallback(false)
    expect(vesselStoreMock.deleteVessel).toHaveBeenCalledTimes(callsBeforeCancel)
  })

  it('syncs changed vessel data and clamps a page after the list shrinks', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    wrapper.vm.goToPage(2)
    vesselStoreMock.vesselList = vesselStoreMock.vesselList.slice(0, 3)
    wrapper.vm.updatedVesselData = 1
    await nextTick()

    expect(wrapper.vm.vesselList).toHaveLength(3)
    expect(wrapper.vm.currentPage).toBe(1)
    expect(sortableListMock.applySortList).toHaveBeenCalledWith(wrapper.vm.vesselList)
  })

  it('puts Add Vessel in the page header and renders icon row actions', async () => {
    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.find('.app-page-header__action').text()).toBe('Add Vessel')
    const row = wrapper.find('tbody tr')
    expect(row.find('[aria-label="Edit vessel"]').classes()).toEqual(expect.arrayContaining(['app-button', 'app-button--primary', 'app-button--dense']))
    expect(row.find('[aria-label="Delete vessel"]').classes()).toContain('app-button--negative')
    // The links to the vessel's batch and its pours are positive, as before.
    expect(row.find('[aria-label="Show pour list"]').classes()).toContain('app-button--positive')
    wrapper.unmount()
  })
})
