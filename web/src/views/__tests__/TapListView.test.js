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
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import TapListView from '../TapListView.vue'

const { globalMock, tapStoreMock, vesselStoreMock, batchStoreMock, sortableListMock } = vi.hoisted(
  () => ({
    globalMock: {
      disabled: false,
      clearMessages: vi.fn(),
      messageSuccess: '',
      messageError: ''
    },
    tapStoreMock: {
      tapList: [],
      deleteTap: vi.fn().mockResolvedValue(true)
    },
    vesselStoreMock: {
      vesselList: []
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
  })
)

vi.mock('@/modules/pinia', () => ({
  global: globalMock,
  tapStore: tapStoreMock,
  vesselStore: vesselStoreMock,
  batchStore: batchStoreMock
}))

vi.mock('@/modules/useSortableList', () => ({
  useSortableList: vi.fn().mockReturnValue(sortableListMock)
}))

vi.mock('@/ui', () => ({
  logDebug: vi.fn()
}))

describe('TapListView', () => {
  const mountWrapper = () =>
    mount(TapListView, {
      attachTo: document.body,
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          AppProgress: true,
          AppConfirmDialog: {
            template: '<button id="deleteTap" type="button" hidden @click="callback(true)"></button>',
            props: ['callback']
          }
        }
      }
    })

  beforeEach(() => {
    vi.clearAllMocks()
    tapStoreMock.tapList = Array.from({ length: 12 }, (_, idx) => ({
      id: `tap-${idx + 1}`,
      name: `Tap ${idx + 1}`,
      location: '',
      tapNumber: idx + 1
    }))
    vesselStoreMock.vesselList = []
    batchStoreMock.batchList = []
    globalMock.messageSuccess = ''
    globalMock.messageError = ''
    tapStoreMock.deleteTap.mockResolvedValue(true)
  })

  afterEach(() => {
    document.body.replaceChildren()
    vi.restoreAllMocks()
  })

  it('paginates taps with fixed 10 items per page', async () => {
    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.vm.totalPages).toBe(2)
    expect(wrapper.vm.paginatedTapList).toHaveLength(10)
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
    expect(wrapper.vm.paginatedTapList).toHaveLength(2)

    wrapper.vm.goToPage(99)
    expect(wrapper.vm.currentPage).toBe(2)

    wrapper.vm.goToPage(0)
    expect(wrapper.vm.currentPage).toBe(1)
  })

  it('shows the empty state when no taps are configured', async () => {
    tapStoreMock.tapList = []
    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.text()).toContain('No taps configured.')
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('sorts taps by name through the table header', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    await wrapper.find('a.icon-link').trigger('click')

    expect(sortableListMock.sortList).toHaveBeenCalledWith(wrapper.vm.tapList, 'name', 'str')
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

  it('shows linked batch and keg volume and flags overdue cleaning', async () => {
    const oldCleanedAt = new Date(Date.now() - 16 * 86_400_000).toISOString()
    tapStoreMock.tapList[0] = {
      ...tapStoreMock.tapList[0],
      id: 'tap-with-keg',
      lastCleanedAt: oldCleanedAt,
      location: 'North wall'
    }
    vesselStoreMock.vesselList = [
      {
        tapId: 'tap-with-keg',
        batchId: 'batch-1',
        volumeRemaining: 7.5,
        totalVolume: 19
      }
    ]
    batchStoreMock.batchList = [{ id: 'batch-1', name: 'Cloudburst' }]
    const wrapper = mountWrapper()
    await nextTick()

    const row = wrapper.find('tbody tr')
    expect(row.text()).toContain('North wall')
    expect(row.text()).toContain('Cloudburst')
    expect(row.text()).toContain('7.5 / 19.0 L')
    expect(row.text()).toContain('Cleaning due')
  })

  it('calculates volume progress safely and handles disconnected vessels', async () => {
    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.vm.tapVolumeProgress(null)).toBe(0)
    expect(wrapper.vm.tapVolumeProgress({ volumeRemaining: null, totalVolume: 20 })).toBe(0)
    expect(wrapper.vm.tapVolumeProgress({ volumeRemaining: 5, totalVolume: 0 })).toBe(0)
    expect(wrapper.vm.tapVolumeProgress({ volumeRemaining: 10, totalVolume: 20 })).toBe(50)
    expect(wrapper.vm.tapVolumeProgress({ volumeRemaining: 30, totalVolume: 20 })).toBe(100)
    expect(wrapper.vm.tapVolumeProgress({ volumeRemaining: -2, totalVolume: 20 })).toBe(0)
  })

  it('detects cleaning due from last-cleaned or creation date only after 14 days', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    const now = Date.now()
    const inTenDays = new Date(now - 10 * 86_400_000).toISOString()
    const inFifteenDays = new Date(now - 15 * 86_400_000).toISOString()

    expect(wrapper.vm.cleaningDue({ lastCleanedAt: inTenDays, createdAt: inFifteenDays })).toBe(false)
    expect(wrapper.vm.cleaningDue({ createdAt: inFifteenDays })).toBe(true)
    expect(wrapper.vm.cleaningDue({})).toBe(false)
  })

  it('normalizes invalid tap ids before creating route links', async () => {
    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.vm.getTapIdForRoute(null)).toBe(null)
    expect(wrapper.vm.getTapIdForRoute(' undefined ')).toBe(null)
    expect(wrapper.vm.getTapIdForRoute(' null ')).toBe(null)
    expect(wrapper.vm.getTapIdForRoute(' tap-4 ')).toBe('tap-4')
  })

  it('deletes through the rendered confirmation and reports success', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    await wrapper.find('button[aria-label="Delete tap"]').trigger('click')
    await nextTick()

    expect(tapStoreMock.deleteTap).toHaveBeenCalledWith('tap-1')
    expect(globalMock.clearMessages).toHaveBeenCalled()
    expect(globalMock.messageSuccess).toBe('Tap deleted')
  })

  it('reports delete failures and ignores cancelled confirmation', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    tapStoreMock.deleteTap.mockResolvedValueOnce(false)
    wrapper.vm.confirmDeleteId = 'tap-2'
    await wrapper.vm.confirmDeleteCallback(true)
    expect(globalMock.messageError).toBe('Failed to delete tap')

    const callsBeforeCancel = tapStoreMock.deleteTap.mock.calls.length
    await wrapper.vm.confirmDeleteCallback(false)
    expect(tapStoreMock.deleteTap).toHaveBeenCalledTimes(callsBeforeCancel)
  })

  it('puts Add Tap in the page header, also when no taps exist yet', async () => {
    tapStoreMock.tapList = []
    const wrapper = mountWrapper()
    await nextTick()

    expect(wrapper.find('.app-page-header__action').text()).toBe('Add Tap')
    wrapper.unmount()
  })

  it('renders edit as primary and delete as negative icon actions', async () => {
    const wrapper = mountWrapper()
    await nextTick()
    const row = wrapper.find('tbody tr')

    expect(row.find('[aria-label="Edit tap"]').classes()).toEqual(expect.arrayContaining(['app-button', 'app-button--primary', 'app-button--dense']))
    expect(row.find('[aria-label="Delete tap"]').classes()).toContain('app-button--negative')
    wrapper.unmount()
  })
})
