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

// deps ../EmptyVesselButton.vue

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import EmptyVesselButton from '../EmptyVesselButton.vue'

const { globalMock, vesselStoreMock, tapStoreMock } = vi.hoisted(() => ({
  globalMock: { messageError: '', messageSuccess: '', clearMessages: vi.fn() },
  vesselStoreMock: { assignBatch: vi.fn() },
  tapStoreMock: { tapList: [], getTapList: vi.fn() }
}))

vi.mock('@/modules/pinia', () => ({
  global: globalMock,
  vesselStore: vesselStoreMock,
  tapStore: tapStoreMock
}))

const vessel = (overrides = {}) => ({
  id: 'keg-1',
  name: 'Keg 1',
  batchId: 'batch-1',
  batchName: 'Pale Ale',
  tapId: null,
  status: 'filled',
  volumeRemaining: 12,
  bottlesRemaining: 0,
  ...overrides
})

const mountButton = (v = vessel(), props = {}) =>
  mount(EmptyVesselButton, { props: { vessel: v, ...props } })

describe('EmptyVesselButton', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    globalMock.messageError = ''
    tapStoreMock.tapList = []
    vesselStoreMock.assignBatch.mockResolvedValue({ id: 'keg-1' })
  })

  describe('visibility', () => {
    it('is shown for a filled vessel', () => {
      expect(mountButton().find('[data-testid="empty-vessel"]').exists()).toBe(true)
    })

    it('is hidden for a clean vessel with nothing remaining and no batch', () => {
      const wrapper = mountButton(
        vessel({ status: 'clean', volumeRemaining: 0, bottlesRemaining: 0, batchId: null })
      )
      expect(wrapper.find('[data-testid="empty-vessel"]').exists()).toBe(false)
    })

    it('is shown for a clean vessel that still has volume remaining', () => {
      const wrapper = mountButton(vessel({ status: 'clean', batchId: null, volumeRemaining: 3 }))
      expect(wrapper.find('[data-testid="empty-vessel"]').exists()).toBe(true)
    })

    it('is shown for a clean vessel that is still on a tap', () => {
      const wrapper = mountButton(
        vessel({ status: 'clean', batchId: null, volumeRemaining: 0, tapId: 'tap-1' })
      )
      expect(wrapper.find('[data-testid="empty-vessel"]').exists()).toBe(true)
    })

    it('is shown for a bottle vessel with bottles remaining', () => {
      const wrapper = mountButton(
        vessel({ status: 'clean', batchId: null, volumeRemaining: 0, bottlesRemaining: 4 })
      )
      expect(wrapper.find('[data-testid="empty-vessel"]').exists()).toBe(true)
    })

    it('is disabled while the app is busy', () => {
      const wrapper = mountButton(vessel(), { disabled: true })
      expect(wrapper.get('[data-testid="empty-vessel"]').attributes('disabled')).toBeDefined()
    })
  })

  describe('confirmation', () => {
    it('opens the dialog without calling the store', async () => {
      const wrapper = mountButton()
      await wrapper.get('[data-testid="empty-vessel"]').trigger('click')
      expect(wrapper.vm.confirmOpen).toBe(true)
      expect(vesselStoreMock.assignBatch).not.toHaveBeenCalled()
    })

    it('names the batch link it ends', () => {
      const text = mountButton().get('[data-testid="empty-vessel-message"]').text()
      expect(text).toContain('This ends the link to batch "Pale Ale"')
    })

    it('names the tap it releases, from the loaded tap list', () => {
      tapStoreMock.tapList = [{ id: 'tap-1', name: 'Left tap' }]
      const text = mountButton(vessel({ tapId: 'tap-1' }))
        .get('[data-testid="empty-vessel-message"]')
        .text()
      expect(text).toContain('released from tap "Left tap"')
    })

    it('loads the tap list when the dialog opens and the tap is not known yet', async () => {
      const wrapper = mountButton(vessel({ tapId: 'tap-1' }))
      await wrapper.get('[data-testid="empty-vessel"]').trigger('click')
      expect(tapStoreMock.getTapList).toHaveBeenCalledOnce()
    })

    it('does not mention a tap when the vessel is not on one', () => {
      const text = mountButton().get('[data-testid="empty-vessel-message"]').text()
      expect(text).not.toContain('released from tap')
    })

    it('does not mention a batch link when the vessel has none', () => {
      const text = mountButton(vessel({ batchId: null, batchName: null }))
        .get('[data-testid="empty-vessel-message"]')
        .text()
      expect(text).not.toContain('ends the link')
    })

    it('cancel closes the dialog and does nothing else', async () => {
      const wrapper = mountButton()
      await wrapper.get('[data-testid="empty-vessel"]').trigger('click')
      await wrapper.get('[data-testid="empty-vessel-cancel"]').trigger('click')
      expect(wrapper.vm.confirmOpen).toBe(false)
      expect(vesselStoreMock.assignBatch).not.toHaveBeenCalled()
      expect(wrapper.emitted('emptied')).toBeUndefined()
    })
  })

  describe('emptying', () => {
    it('confirm sends batch_id null through the store and emits the result', async () => {
      const updated = { id: 'keg-1', status: 'clean' }
      vesselStoreMock.assignBatch.mockResolvedValue(updated)
      const wrapper = mountButton()
      await wrapper.get('[data-testid="empty-vessel"]').trigger('click')
      await wrapper.get('[data-testid="empty-vessel-confirm"]').trigger('click')
      await vi.waitFor(() => expect(wrapper.emitted('emptied')).toBeTruthy())
      expect(vesselStoreMock.assignBatch).toHaveBeenCalledExactlyOnceWith('keg-1', null)
      expect(wrapper.emitted('emptied')[0]).toEqual([updated])
      expect(wrapper.vm.confirmOpen).toBe(false)
    })

    it('disables the buttons while saving', async () => {
      let resolve
      vesselStoreMock.assignBatch.mockReturnValue(new Promise((r) => (resolve = r)))
      const wrapper = mountButton()
      await wrapper.get('[data-testid="empty-vessel"]').trigger('click')
      await wrapper.get('[data-testid="empty-vessel-confirm"]').trigger('click')
      expect(wrapper.get('[data-testid="empty-vessel"]').attributes('disabled')).toBeDefined()
      expect(wrapper.get('[data-testid="empty-vessel-confirm"]').attributes('disabled')).toBeDefined()
      resolve({ id: 'keg-1' })
      await vi.waitFor(() =>
        expect(wrapper.get('[data-testid="empty-vessel"]').attributes('disabled')).toBeUndefined()
      )
    })

    it('reports a failure through the shared error message and keeps the dialog open', async () => {
      vesselStoreMock.assignBatch.mockResolvedValue(null)
      const wrapper = mountButton()
      await wrapper.get('[data-testid="empty-vessel"]').trigger('click')
      await wrapper.get('[data-testid="empty-vessel-confirm"]').trigger('click')
      await vi.waitFor(() => expect(globalMock.messageError).toBe('Failed to empty vessel'))
      expect(wrapper.emitted('emptied')).toBeUndefined()
      expect(wrapper.vm.confirmOpen).toBe(true)
    })
  })
})
