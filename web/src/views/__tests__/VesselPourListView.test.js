/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import VesselPourListView from '../VesselPourListView.vue'

const chartCtor = vi.hoisted(() =>
  vi.fn(function () {
    return { destroy: vi.fn(), resetZoom: vi.fn() }
  })
)

vi.mock('chart.js', () => ({
  Chart: Object.assign(chartCtor, { register: vi.fn() }),
  registerables: []
}))
vi.mock('chartjs-plugin-zoom', () => ({ default: {} }))
vi.mock('chartjs-adapter-date-fns', () => ({}))
vi.mock('date-fns', () => ({}))
vi.mock('vue-router', () => ({ useRoute: () => ({ params: { id: 'v1' } }) }))
vi.mock('@/modules/pinia', () => ({
  global: { disabled: false },
  config: { isVolumeUs: false, isVolumeUk: false, isVolumeMetric: true },
  preferences: { dark_mode: false },
  pourStore: { listPours: vi.fn() },
  vesselStore: { vesselList: [], getVessel: vi.fn() }
}))
vi.mock('@/ui', () => ({ logDebug: vi.fn(), logError: vi.fn() }))

import { config, pourStore, vesselStore } from '@/modules/pinia'

function pour(id, createdAt, amount, level, extra = {}) {
  return {
    id,
    createdAt,
    pourAmount: amount,
    volumeRemaining: level,
    isManual: false,
    excluded: false,
    ...extra
  }
}

const AppButtonStub = {
  props: ['variant'],
  template: '<button :data-variant="variant"><slot /></button>'
}

function mountView() {
  return mount(VesselPourListView, {
    global: { stubs: { 'app-button': AppButtonStub } },
    attachTo: document.body
  })
}

const lastChart = () => chartCtor.mock.calls[chartCtor.mock.calls.length - 1][1]
const lastInstance = () => chartCtor.mock.results[chartCtor.mock.results.length - 1].value

describe('VesselPourListView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    config.isVolumeUs = false
    config.isVolumeUk = false
    config.isVolumeMetric = true
    vesselStore.vesselList = [{ id: 'v1', name: 'Keg 1', batchId: 'b1', totalVolume: 19 }]
    pourStore.listPours.mockResolvedValue([
      pour('a', '2026-11-01T10:00:00Z', 0.5, 18.5),
      pour('b', '2026-11-01T12:00:00Z', 0.8, 17.7),
      pour('c', '2026-11-01T14:00:00Z', 0.5, 17.2),
      pour('d', '2026-11-01T15:00:00Z', 9, 8.2, { excluded: true, isManual: true })
    ])
  })

  it('shows a chart skeleton while the pours load', async () => {
    let release
    pourStore.listPours.mockReturnValueOnce(new Promise((resolve) => (release = resolve)))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('[data-test="chart-skeleton"]').exists()).toBe(true)

    release([])
    await flushPromises()
    expect(wrapper.find('[data-test="chart-skeleton"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('groups the list by day with count and total, and keeps excluded pours out of the numbers', async () => {
    const wrapper = mountView()
    await flushPromises()

    const groups = wrapper.findAll('[data-test="day-group"]')
    expect(groups).toHaveLength(1)
    expect(groups[0].find('h3').text()).toBe('Sun 1 Nov — 3 pours, 1.8 L')
    expect(groups[0].findAll('tbody tr')).toHaveLength(4)
    expect(groups[0].text()).toContain('Manual')
    expect(groups[0].text()).toContain('Auto-detected')
    expect(wrapper.find('.pour-history__row--excluded').exists()).toBe(true)
    expect(wrapper.get('[data-test="summary"]').text()).toBe(
      'Latest level 17.2 L. Total poured 1.8 L. Busiest day Sun 1 Nov, 1.8 L.'
    )
    expect(chartCtor).toHaveBeenCalledTimes(1)
    expect(chartCtor.mock.calls[0][1].type).toBe('line')
    expect(chartCtor.mock.calls[0][1].options.scales.y.max).toBe(19)
    wrapper.unmount()
  })

  it('shows the summary in the volume unit of the user', async () => {
    config.isVolumeMetric = false
    config.isVolumeUs = true
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.get('[data-test="summary"]').text()).toContain('Latest level 4.54 gal')
    wrapper.unmount()
  })

  it('requests the pours without allFills and offers no fill selector', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(pourStore.listPours).toHaveBeenCalledTimes(1)
    expect(pourStore.listPours).toHaveBeenCalledWith('v1')
    expect(wrapper.text()).not.toContain('All fills')
    expect(wrapper.text()).not.toContain('Current fill')
    wrapper.unmount()
  })

  it('requests the pours the same way for a vessel with no batch', async () => {
    vesselStore.vesselList = [{ id: 'v1', name: 'Keg 1', batchId: '', totalVolume: 19 }]
    const wrapper = mountView()
    await flushPromises()

    expect(pourStore.listPours).toHaveBeenCalledWith('v1')
    wrapper.unmount()
  })

  it('shows one chart at a time and keeps the choice while the page is open', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.findAll('canvas')).toHaveLength(1)
    expect(wrapper.get('[data-test="view-level"]').attributes('data-variant')).toBe('primary')
    expect(lastChart().type).toBe('line')

    await wrapper.get('[data-test="view-daily"]').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('canvas')).toHaveLength(1)
    expect(wrapper.get('[data-test="view-daily"]').attributes('data-variant')).toBe('primary')
    expect(lastChart().type).toBe('bar')

    await wrapper.get('[data-test="range-24h"]').trigger('click')
    await flushPromises()
    expect(lastChart().type).toBe('bar')
    wrapper.unmount()
  })

  it('narrows the chart data with a range chip but not the summary or the list', async () => {
    pourStore.listPours.mockResolvedValue([
      pour('old', '2026-10-25T10:00:00Z', 1, 19),
      pour('a', '2026-11-01T10:00:00Z', 0.5, 18.5),
      pour('b', '2026-11-01T11:00:00Z', 0.5, 18)
    ])
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.get('[data-test="range-All"]').attributes('data-variant')).toBe('primary')
    expect(lastChart().data.datasets[0].data).toHaveLength(3)
    const summary = wrapper.get('[data-test="summary"]').text()

    await wrapper.get('[data-test="range-24h"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="range-24h"]').attributes('data-variant')).toBe('primary')
    expect(wrapper.get('[data-test="range-All"]').attributes('data-variant')).toBe('outline-secondary')
    expect(lastChart().data.datasets[0].data).toHaveLength(2)
    expect(wrapper.get('[data-test="summary"]').text()).toBe(summary)
    expect(wrapper.findAll('[data-test="day-group"]')).toHaveLength(2)
    wrapper.unmount()
  })

  it('says so in place of the chart when the range holds no pours', async () => {
    pourStore.listPours.mockResolvedValue([pour('x', '2026-11-01T10:00:00Z', 1, 18, { excluded: true })])
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.get('[data-test="range-empty"]').text()).toBe('No pours in this range')
    expect(wrapper.find('canvas').exists()).toBe(false)
    expect(wrapper.find('[data-test="ranges"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('offers reset zoom on the level chart only and resets it', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(lastChart().options.plugins.zoom.zoom.wheel.enabled).toBe(true)
    expect(lastChart().options.plugins.zoom.zoom.pinch.enabled).toBe(true)
    expect(lastChart().options.plugins.zoom.zoom.mode).toBe('x')

    const level = lastInstance()
    await wrapper.get('[data-test="reset-zoom"]').trigger('click')
    expect(level.resetZoom).toHaveBeenCalledTimes(1)

    await wrapper.get('[data-test="range-All"]').trigger('click')
    expect(level.resetZoom).toHaveBeenCalledTimes(2)

    await wrapper.get('[data-test="view-daily"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="reset-zoom"]').exists()).toBe(false)
    expect(lastChart().options.plugins.zoom).toBeUndefined()
    wrapper.unmount()
  })

  it('hides the switch and the chips when there are no pours', async () => {
    pourStore.listPours.mockResolvedValue([])
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('[data-test="chart-views"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="ranges"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('keeps the empty text and draws no chart without pours', async () => {
    pourStore.listPours.mockResolvedValue([])
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('No pours recorded')
    expect(wrapper.find('canvas').exists()).toBe(false)
    expect(chartCtor).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('shows the error with a retry and no charts when loading fails', async () => {
    pourStore.listPours.mockResolvedValueOnce(null)
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('Failed to load the pours.')
    expect(wrapper.find('canvas').exists()).toBe(false)

    await wrapper.get('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.findAll('[data-test="day-group"]')).toHaveLength(1)
    wrapper.unmount()
  })

  it('charts only the latest 500 pours and says so', async () => {
    const start = Date.parse('2026-01-01T00:00:00Z')
    const many = Array.from({ length: 501 }, (_, i) =>
      pour(`p${i}`, new Date(start + i * 3600000).toISOString(), 0.1, 19 - i * 0.01)
    )
    pourStore.listPours.mockResolvedValue(many)
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.get('[data-test="truncated"]').text()).toBe('Showing the latest 500 pours')
    expect(chartCtor.mock.calls[0][1].data.datasets[0].data).toHaveLength(500)
    wrapper.unmount()
  })
})
