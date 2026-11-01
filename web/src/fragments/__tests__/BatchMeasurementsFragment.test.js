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

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'
import { Batch } from '@/modules/classes'
import router from '@/modules/router'
import BatchMeasurementsFragment from '../BatchMeasurementsFragment.vue'

vi.mock('@/modules/router', () => ({
  default: {
    currentRoute: { value: { params: { id: 'batch-1' }, query: {} } },
    replace: vi.fn()
  }
}))
vi.mock('@/views/BatchGravityGraphView.vue', () => ({ default: { template: '<div data-view="gravity">Gravity chart</div>' } }))
vi.mock('@/views/BatchPressureGraphView.vue', () => ({ default: { template: '<div data-view="pressure">Pressure chart</div>' } }))
vi.mock('@/views/BatchTempChartView.vue', () => ({ default: { template: '<div data-view="temp">Temp chart</div>' } }))

const mountMeasurements = async (counts = {}, query = {}) => {
  router.currentRoute.value = reactive({ params: { id: 'batch-1' }, query })
  router.replace.mockImplementation(({ query: nextQuery }) => {
    router.currentRoute.value.query = nextQuery
  })
  const wrapper = mount(BatchMeasurementsFragment, {
    props: { batch: new Batch({ id: 'batch-1', ...counts }) },
    global: { stubs: { AppButton: { template: '<button v-bind="$attrs"><slot /></button>' } } }
  })
  await flushPromises()
  return wrapper
}

describe('Batch measurement selection', () => {
  beforeEach(() => vi.clearAllMocks())

  it.each([
    [{ gravityCount: 1, pressureCount: 2, temperatureCount: 3 }, 'gravity'],
    [{ pressureCount: 2, temperatureCount: 3 }, 'pressure'],
    [{ temperatureCount: 3 }, 'temp'],
    [{}, 'gravity']
  ])('opens the first view with readings, or Gravity when empty', async (counts, expected) => {
    const wrapper = await mountMeasurements(counts)
    expect(wrapper.find('[data-view="' + expected + '"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Diagnostics')
    wrapper.unmount()
  })

  it('hides the control when only Gravity is available', async () => {
    const wrapper = await mountMeasurements({ gravityCount: 2 })
    expect(wrapper.find('[role="group"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('shows the control when another view holds readings', async () => {
    const wrapper = await mountMeasurements({ gravityCount: 2, temperatureCount: 1 })
    expect(wrapper.findAll('button')).toHaveLength(2)
    wrapper.unmount()
  })

  it('marks only views with readings using a dot and an accessible label', async () => {
    const wrapper = await mountMeasurements({ pressureCount: 2 })
    expect(wrapper.findAll('.measurement-data-dot')).toHaveLength(1)
    expect(wrapper.get('[aria-label="Pressure, has readings"]').find('.measurement-data-dot').exists()).toBe(true)
    wrapper.unmount()
  })

  it('lets an explicit view override counts and a legacy tab', async () => {
    const wrapper = await mountMeasurements({ pressureCount: 2 }, { tab: 'pressure', view: 'temp' })
    expect(wrapper.find('[data-view="temp"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('honours legacy measurement links without a view parameter', async () => {
    const wrapper = await mountMeasurements({ gravityCount: 2 }, { tab: 'pressure' })
    expect(wrapper.find('[data-view="pressure"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('keeps a selected view when reading counts change', async () => {
    const wrapper = await mountMeasurements({ pressureCount: 2, temperatureCount: 1 }, { tab: 'measurements' })
    await wrapper.get('[aria-label^="Temp"]').trigger('click')
    await wrapper.setProps({ batch: new Batch({ id: 'batch-1', gravityCount: 4, pressureCount: 2 }) })
    await flushPromises()
    expect(wrapper.find('[data-view="temp"]').exists()).toBe(true)
    expect(router.replace).toHaveBeenCalledWith({ query: { tab: 'measurements', view: 'temp' } })
    wrapper.unmount()
  })

  it('follows query navigation after a user selection', async () => {
    const wrapper = await mountMeasurements({ pressureCount: 2, temperatureCount: 1 }, { tab: 'measurements' })
    await wrapper.get('[aria-label^="Temp"]').trigger('click')
    router.currentRoute.value.query = { tab: 'measurements', view: 'gravity' }
    await flushPromises()
    expect(wrapper.find('[data-view="gravity"]').exists()).toBe(true)
    wrapper.unmount()
  })
})
