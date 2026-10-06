/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import BatchTempChartView from '../BatchTempChartView.vue'

const chartState = vi.hoisted(() => ({
  instance: { options: { scales: { x: {} } }, update: vi.fn() }
}))
const chartCtor = vi.hoisted(() => vi.fn(function () { return chartState.instance }))

vi.mock('chart.js', () => ({
  Chart: Object.assign(chartCtor, { register: vi.fn() }),
  registerables: []
}))
vi.mock('chartjs-plugin-zoom', () => ({ default: {} }))
vi.mock('chartjs-adapter-date-fns', () => ({}))
vi.mock('date-fns', () => ({}))
vi.mock('@/modules/pinia', () => ({
  batchStore: { getBatch: vi.fn() },
  global: { disabled: false, messageError: '' },
  config: { isTempC: true }
}))
vi.mock('@/modules/apiClient', () => ({
  apiJson: vi.fn()
}))
vi.mock('@/modules/router', () => ({
  default: { currentRoute: { value: { params: { id: 'b1' } } } }
}))
vi.mock('@/modules/utils', () => ({ tempToF: (t) => t }))
vi.mock('@/ui', () => ({ logDebug: vi.fn(), logError: vi.fn() }))

import { batchStore, config, global } from '@/modules/pinia'
import { apiJson } from '@/modules/apiClient'

describe('BatchTempChartView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    batchStore.getBatch.mockResolvedValue({ name: 'Stout' })
    apiJson.mockResolvedValue([
      { t: '2026-01-01T00:00:00Z', temp: 18 },
      { t: '2026-01-01T01:00:00Z', temp: 19 }
    ])
    config.isTempC = true
    global.disabled = false
    global.messageError = ''
    chartState.instance = { options: { scales: { x: {} } }, update: vi.fn() }
  })

  const mountView = () => mount(BatchTempChartView, {
    attachTo: document.body,
    global: {
      stubs: {
        'router-link': true,
        'app-button': {
          props: { variant: String, dense: Boolean },
          template: '<button :class="[\'app-button\', variant && `app-button--${variant}`, dense && \'app-button--dense\']"><slot /></button>'
        },
        'q-icon': true
      }
    }
  })

  it('draws the chart once the readings have rendered the canvas', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('#tempChart').exists()).toBe(true)
    expect(chartCtor).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('updates the chart range from each time filter button', async () => {
    const wrapper = mountView()
    await flushPromises()
    const buttons = wrapper.findAll('button')

    await buttons.find((button) => button.text() === '24h').trigger('click')
    expect(chartState.instance.options.scales.x.min).toBe('2025-12-31T01:00:00.000Z')
    expect(chartState.instance.options.scales.x.max).toBe('2026-01-01T01:00:00Z')
    await buttons.find((button) => button.text() === '48h').trigger('click')
    expect(chartState.instance.options.scales.x.min).toBe('2025-12-30T01:00:00.000Z')
    await buttons.find((button) => button.text() === '7d').trigger('click')
    expect(chartState.instance.options.scales.x.min).toBe('2025-12-25T01:00:00.000Z')
    await buttons.find((button) => button.text() === 'All').trigger('click')
    expect(chartState.instance.options.scales.x.min).toBe('2026-01-01T00:00:00Z')
    expect(chartState.instance.update).toHaveBeenCalledTimes(4)
    wrapper.unmount()
  })

  it('shows the empty state without constructing a chart when there are no readings', async () => {
    apiJson.mockResolvedValueOnce([])
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('No temperature readings found for this batch.')
    expect(chartCtor).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('reports a missing batch but still loads its temperature readings', async () => {
    batchStore.getBatch.mockResolvedValueOnce(null)
    const wrapper = mountView()
    await flushPromises()
    expect(global.messageError).toBe('Failed to load batch b1')
    expect(apiJson).toHaveBeenCalledWith('GET', 'batches/b1/temp/chart', undefined, { busy: false })
    expect(chartCtor).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
})
