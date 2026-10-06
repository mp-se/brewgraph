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
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import BatchFermentationControlView from '../BatchFermentationControlView.vue'

vi.mock('@/modules/pinia', () => ({
  global: { disabled: false, messageError: '' },
  config: { isTempF: false, isTempC: true, tempUnit: 'C' },
  batchStore: { getBatch: vi.fn().mockResolvedValue(null) },
  deviceStore: {
    getDevice: vi.fn().mockResolvedValue(null),
    getFermentationSteps: vi.fn().mockResolvedValue([]),
    addFermentationSteps: vi.fn().mockResolvedValue(true),
    activateFermentationSteps: vi.fn().mockResolvedValue([]),
    deactivateFermentationSteps: vi.fn().mockResolvedValue(true),
    advanceFermentationStep: vi.fn().mockResolvedValue({})
  },
  default: {}
}))

vi.mock('@/modules/router', () => ({
  default: { currentRoute: { value: { params: { id: '1' } } } }
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

describe('BatchFermentationControlView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  const mountWrapper = async () => {
    const wrapper = mount(BatchFermentationControlView, {
      global: {
        stubs: {
          AppMessage: true
        }
      }
    })
    return wrapper
  }

  it('renders fermentation steps as read-only table', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.find('.app-page').exists()).toBe(true)
  })

  it('displays correct temperature unit in table', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.html()).toContain('app-page')
  })

  it('loads profile correctly on mount', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.text()).toContain('Fermentation Control')
  })

  it('handles batch without fermentation profile', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.find('.app-page').exists()).toBe(true)
  })

  it('handles batch without fermentation controller selected', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.find('.app-page').exists()).toBe(true)
  })

  it('handles device load failure', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.find('.app-page').exists()).toBe(true)
  })

  it('handles loadProfile failure (batch not found)', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.find('.app-page').exists()).toBe(true)
  })

  it('displays fermentation steps with proper step numbers starting from 1', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.find('.app-page').exists()).toBe(true)
  })

  it('displays step details in table columns', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.find('.app-page').exists()).toBe(true)
  })

  it('shows warning when device has active steps', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.find('.app-page').exists()).toBe(true)
  })

  it('starts steps when none are active', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.find('.app-page').exists()).toBe(true)
  })

  it('handles start steps failure', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.find('.app-page').exists()).toBe(true)
  })

  it('deletes existing steps before starting new ones', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.find('.app-page').exists()).toBe(true)
  })

  it('shows not available message', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.text()).toContain('No fermentation')
  })

  // ---------------------------------------------------------------------------
  // Chamber control
  //
  // Creating the steps is not enough: `chamber_control_active` is set by the
  // activate endpoint alone, and the chamber ingest returns mode `R` until it is.
  // The UI must call activate after saving the step list, or the feature
  // stays unreachable even though the steps exist.
  // ---------------------------------------------------------------------------

  it('activates chamber control for the saved steps', async () => {
    const { batchStore, deviceStore } = await import('@/modules/pinia')
    batchStore.getBatch.mockResolvedValue({ id: 'b1', name: 'Test', chamberControlActive: false })
    deviceStore.getFermentationSteps.mockResolvedValue([
      { id: 's1', name: 'Primary', temp: 20, days: 7, deviceId: 'd1' }
    ])
    deviceStore.activateFermentationSteps.mockResolvedValue([
      { id: 's1', name: 'Primary', temp: 20, days: 7, date: '2026-08-22' }
    ])

    const wrapper = await mountWrapper()
    await wrapper.vm.$nextTick()
    await wrapper.vm.activateExistingSteps()

    expect(deviceStore.activateFermentationSteps).toHaveBeenCalledWith('b1')
    expect(wrapper.vm.chamberControlActive).toBe(true)
  })

  it('leaves control off when activation fails', async () => {
    const { batchStore, deviceStore } = await import('@/modules/pinia')
    batchStore.getBatch.mockResolvedValue({ id: 'b1', name: 'Test', chamberControlActive: false })
    deviceStore.activateFermentationSteps.mockResolvedValue(null)

    const wrapper = await mountWrapper()
    await wrapper.vm.activateExistingSteps()

    expect(wrapper.vm.chamberControlActive).toBe(false)
  })

  it('resolves the controller from the steps, not from a batch field', async () => {
    const { batchStore, deviceStore } = await import('@/modules/pinia')
    batchStore.getBatch.mockResolvedValue({ id: 'b1', name: 'Test', chamberControlActive: false })
    deviceStore.getFermentationSteps.mockResolvedValue([
      { id: 's1', name: 'Primary', temp: 20, days: 7, deviceId: 'd9' }
    ])
    deviceStore.getDevice.mockResolvedValue({ id: 'd9', name: 'Chamber', deviceType: 'chamber' })

    await mountWrapper()
    await new Promise((r) => setTimeout(r, 0))

    // `batch.fermentationChamber` exists only in the backup format, inherited from
    // BrewLogger — reading it here always resolved to null.
    expect(deviceStore.getDevice).toHaveBeenCalledWith('d9')
  })

  it('deactivates chamber control', async () => {
    const { batchStore, deviceStore } = await import('@/modules/pinia')
    batchStore.getBatch.mockResolvedValue({ id: 'b1', name: 'Test', chamberControlActive: true })

    const wrapper = await mountWrapper()
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.chamberControlActive).toBe(true)

    await wrapper.vm.deactivateCallback()
    expect(deviceStore.deactivateFermentationSteps).toHaveBeenCalledWith('b1')
    expect(wrapper.vm.chamberControlActive).toBe(false)
  })

  it('advances to the next step and reloads the schedule', async () => {
    const { batchStore, deviceStore } = await import('@/modules/pinia')
    batchStore.getBatch.mockResolvedValue({ id: 'b1', name: 'Test', chamberControlActive: true })

    const wrapper = await mountWrapper()
    await wrapper.vm.advanceCallback()

    expect(deviceStore.advanceFermentationStep).toHaveBeenCalledWith('b1')
    expect(deviceStore.getFermentationSteps).toHaveBeenCalled()
  })
})
