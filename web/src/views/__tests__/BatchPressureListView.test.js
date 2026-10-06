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
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import BatchPressureListView from '../BatchPressureListView.vue'
import { nextTick } from 'vue'

const mockStores = vi.hoisted(() => ({
  batch: {
    getBatch: vi.fn()
  },
  pressure: {
    getPressureListForBatch: vi.fn(),
    updatePressure: vi.fn()
  },
  config: {
    isPressurePSI: true,
    isPressureBAR: false,
    isTempC: true,
    $subscribe: vi.fn(),
    $patch: vi.fn()
  },
  global: {
    disabled: false,
    acquireBusy() {
      this.disabled = true
      let released = false
      return () => { if (!released) { released = true; this.disabled = false } }
    },
    messageError: '',
    $subscribe: vi.fn(),
    $patch: vi.fn()
  },
  analytics: {
    date: {
      firstDate: '2023-01-01',
      lastDate: '2023-01-03'
    }
  },
  router: {
    currentRoute: {
      value: {
        params: { id: '1' }
      }
    }
  }
}))

vi.mock('@/modules/pinia', () => ({
  config: mockStores.config,
  pressureStore: mockStores.pressure,
  batchStore: mockStores.batch,
  global: mockStores.global,
  default: {}
}))

vi.mock('@/modules/router', () => ({
  default: mockStores.router
}))

vi.mock('@/ui', async (importActual) => {
  const actual = await importActual()
  return {
    ...actual,
    logDebug: vi.fn(),
    logInfo: vi.fn(),
    logError: vi.fn()
  }
})

vi.mock('@/modules/utils', () => ({
  getPressureDataAnalytics: vi.fn(() => mockStores.analytics),
  getFormattedTemperature: vi.fn((t) => `${t} C`),
  getFormattedPressure: vi.fn((p) => `${p} PSI`)
}))

vi.mock('@/modules/ui', () => ({
  sortedIconClass: 'bi-sort-down',
  setSortingDefault: vi.fn(),
  sortedClass: vi.fn(() => 'sorted'),
  sortList: vi.fn(),
  applySortList: vi.fn()
}))

describe('BatchPressureListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    mockStores.batch.getBatch.mockResolvedValue({ id: '1', name: 'Batch 1' })
    mockStores.pressure.getPressureListForBatch.mockResolvedValue([
      {
        id: 1,
        pressure: 10,
        createdAt: '2023-01-01T10:00:00Z',
        active: true,
        temperature: 20,
        battery: 4.2,
        rssi: -60,
        runTime: 1.5
      },
      {
        id: 2,
        pressure: 12,
        createdAt: '2023-01-02T10:00:00Z',
        active: true,
        temperature: 21,
        battery: 4.1,
        rssi: -65,
        runTime: 1.6
      }
    ])
    mockStores.pressure.updatePressure.mockResolvedValue(true)
  })

  const mountWrapper = async () => {
    const wrapper = mount(BatchPressureListView, {
      global: {
        stubs: {
          'router-link': { template: '<a><slot></slot></a>' },
          AppInputDate: { template: '<input v-model="modelValue" />', props: ['modelValue'] },
          AppField: { template: '<div><slot></slot></div>' },
          PressureStatsFragment: { template: '<div />' }
        }
      }
    })

    await nextTick()
    await nextTick()
    return wrapper
  }

  it('initializes and loads data on mount', async () => {
    const wrapper = await mountWrapper()
    expect(mockStores.batch.getBatch).toHaveBeenCalledWith('1')
    expect(mockStores.pressure.getPressureListForBatch).toHaveBeenCalledWith('1')
    expect(wrapper.vm.batchName).toBe('Batch 1')
    expect(wrapper.vm.pressureList.length).toBe(2)
  })

  it('handles loading error for batch', async () => {
    mockStores.batch.getBatch.mockResolvedValue(null)
    const wrapper = await mountWrapper()
    expect(wrapper.vm.batchName).toBe('')
  })

  it('updates pressure when checkbox clicked', async () => {
    const wrapper = await mountWrapper()
    const toggle = wrapper.find('tbody .q-toggle')

    await toggle.trigger('click')
    expect(mockStores.pressure.updatePressure).toHaveBeenCalled()
  })

  it('does not update anything when the checked pressure id is missing', async () => {
    const wrapper = await mountWrapper()

    await wrapper.vm.updatePressure('missing')

    expect(mockStores.pressure.updatePressure).not.toHaveBeenCalled()
  })

  it('recalculates stats after a successful exclusion toggle', async () => {
    const wrapper = await mountWrapper()

    await wrapper.vm.updatePressure(1)

    expect(mockStores.pressure.updatePressure).toHaveBeenCalledWith(
      expect.objectContaining({ id: 1, excluded: true })
    )
    const { getPressureDataAnalytics } = await import('@/modules/utils')
    expect(getPressureDataAnalytics).toHaveBeenCalledWith(wrapper.vm.pressureList)
  })

  it('handles update failure', async () => {
    mockStores.pressure.updatePressure.mockResolvedValueOnce(false)
    const wrapper = await mountWrapper()
    const before = wrapper.vm.pressureList[0].excluded
    const toggle = wrapper.find('tbody .q-toggle')

    await toggle.trigger('click')
    await flushPromises()
    expect(mockStores.global.messageError).toContain('Failed to save the excluded setting for pressure reading')
    // A failed save puts the switch back.
    expect(wrapper.vm.pressureList[0].excluded).toBe(before)
  })

  it('applies filters', async () => {
    const wrapper = await mountWrapper()
    wrapper.vm.infoFirstDay = '2023-01-01'
    wrapper.vm.infoLastDay = '2023-01-02'

    await wrapper.vm.apply()
    expect(mockStores.pressure.updatePressure).toHaveBeenCalled()
  })

  it('applies date bounds, excludes out-of-range rows, and releases busy state', async () => {
    mockStores.pressure.getPressureListForBatch.mockResolvedValue([
      { id: 1, createdAt: '2023-01-01T10:00:00Z', excluded: true },
      { id: 2, createdAt: '2023-01-02T10:00:00Z', excluded: true },
      { id: 3, createdAt: '2023-01-04T10:00:00Z', excluded: false }
    ])
    const wrapper = await mountWrapper()
    wrapper.vm.infoFirstDay = '2023-01-01'
    wrapper.vm.infoLastDay = '2023-01-02'

    await wrapper.vm.apply()

    expect(wrapper.vm.pressureList.map(({ excluded }) => excluded)).toEqual([false, false, true])
    expect(mockStores.pressure.updatePressure).toHaveBeenCalledTimes(3)
    expect(mockStores.global.disabled).toBe(false)
  })

  it('handles apply failure', async () => {
    mockStores.pressure.updatePressure.mockResolvedValue(false)
    const wrapper = await mountWrapper()
    wrapper.vm.infoFirstDay = '2023-01-01'
    wrapper.vm.infoLastDay = '2023-01-02'

    await wrapper.vm.apply()
    // It should have logged error
    const logger = await import('@/ui')
    expect(logger.logError).toHaveBeenCalled()
  })

  it('activates all records', async () => {
    mockStores.pressure.getPressureListForBatch.mockResolvedValue([
      { id: 1, pressure: 10, createdAt: '2023-01-01T10:00:00Z', excluded: true, temperature: 20 }
    ])
    const wrapper = await mountWrapper()

    await wrapper.vm.activateAll()
    expect(mockStores.pressure.updatePressure).toHaveBeenCalled()
    expect(wrapper.vm.pressureList[0].excluded).toBe(false)
  })

  it('does not save already included records when clearing exclusions', async () => {
    mockStores.pressure.getPressureListForBatch.mockResolvedValue([
      { id: 1, createdAt: '2023-01-01T10:00:00Z', excluded: false }
    ])
    const wrapper = await mountWrapper()

    await wrapper.vm.activateAll()

    expect(mockStores.pressure.updatePressure).not.toHaveBeenCalled()
    expect(mockStores.global.disabled).toBe(false)
  })

  it('handles activateAll failure', async () => {
    mockStores.pressure.getPressureListForBatch.mockResolvedValue([
      { id: 1, pressure: 10, createdAt: '2023-01-01T10:00:00Z', excluded: true, temperature: 20 }
    ])
    mockStores.pressure.updatePressure.mockResolvedValue(false)
    const wrapper = await mountWrapper()

    await wrapper.vm.activateAll()
    const logger = await import('@/ui')
    expect(logger.logError).toHaveBeenCalled()
  })

  it('should render table headers and icons', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.find('th').exists()).toBe(true)
    expect(wrapper.find('.icon-link').exists()).toBe(true)
  })

  it('sorts by date, pressure, and battery using the table header controls', async () => {
    const wrapper = await mountWrapper()
    const { sortList } = await import('@/modules/ui')

    await wrapper.findAll('.icon-link')[0].trigger('click')
    await wrapper.findAll('.icon-link')[1].trigger('click')
    await wrapper.findAll('.icon-link')[2].trigger('click')

    expect(sortList).toHaveBeenNthCalledWith(1, wrapper.vm.pressureList, 'created', 'date')
    expect(sortList).toHaveBeenNthCalledWith(2, wrapper.vm.pressureList, 'pressure', 'num')
    expect(sortList).toHaveBeenNthCalledWith(3, wrapper.vm.pressureList, 'battery', 'num')
  })

  it('routes the filter controls to their view actions', async () => {
    const wrapper = await mountWrapper()
    const applySpy = vi.spyOn(wrapper.vm, 'apply').mockResolvedValue()
    const clearSpy = vi.spyOn(wrapper.vm, 'activateAll').mockResolvedValue()

    const buttons = wrapper.findAll('button.app-button--secondary')
    await buttons.find((button) => button.text().includes('Apply Filter')).trigger('click')
    await buttons.find((button) => button.text().includes('Clear excluded')).trigger('click')

    expect(applySpy).toHaveBeenCalledOnce()
    expect(clearSpy).toHaveBeenCalledOnce()
  })

  it('renders pagination actions for long reading lists', async () => {
    mockStores.pressure.getPressureListForBatch.mockResolvedValue(
      Array.from({ length: 101 }, (_, index) => ({
        id: index + 1,
        pressure: 10,
        createdAt: '2023-01-01T10:00:00Z',
        excluded: false
      }))
    )
    const wrapper = await mountWrapper()

    expect(wrapper.find('nav[aria-label="Pressure list pagination"]').exists()).toBe(true)
    await wrapper.get('button[aria-label="Next page"]').trigger('click')
    expect(wrapper.vm.currentPage).toBe(2)
    await wrapper.get('button[aria-label="Previous page"]').trigger('click')
    expect(wrapper.vm.currentPage).toBe(1)
    await wrapper.get('button[aria-label="Page 2"]').trigger('click')
    expect(wrapper.vm.currentPage).toBe(2)
  })

  it('reports a failed pressure list load and leaves the list empty', async () => {
    mockStores.pressure.getPressureListForBatch.mockResolvedValue(null)
    const wrapper = await mountWrapper()
    const logger = await import('@/ui')

    expect(wrapper.vm.pressureList).toBe(null)
    expect(logger.logError).toHaveBeenCalledWith(
      'BatchPressureListView.onMounted()',
      'Failed to load pressure',
      '1'
    )
  })

  it('shows stats section expanded by default', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.vm.showStats).toBe(true)
    expect(wrapper.find('#pressure-stats-collapse').classes()).toContain('show')
    expect(wrapper.text()).toContain('Hide stats')
  })

  it('toggles stats section visibility when toggle button is clicked', async () => {
    const wrapper = await mountWrapper()
    const button = wrapper.find('button.app-button.app-button--outline-secondary.app-button--dense')
    expect(button.exists()).toBe(true)

    await button.trigger('click')
    await nextTick()
    expect(wrapper.vm.showStats).toBe(false)
    expect(wrapper.find('#pressure-stats-collapse').classes()).not.toContain('show')
    expect(wrapper.text()).toContain('Show stats')
  })
})
