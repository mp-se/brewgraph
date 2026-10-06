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

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import BatchBrewfatherLinkFragment from '../BatchBrewfatherLinkFragment.vue'

const mocks = vi.hoisted(() => ({
  global: { disabled: false },
  brewfatherStore: {
    getBatchList: vi.fn().mockResolvedValue(true),
    batches: []
  }
}))

vi.mock('@/modules/pinia', () => ({ global: mocks.global, brewfatherStore: mocks.brewfatherStore }))
vi.mock('@/ui', () => ({ logDebug: vi.fn() }))

function mountFragment() {
  return mount(BatchBrewfatherLinkFragment, {
    global: { stubs: { AppSelectDialog: true } }
  })
}

describe('BatchBrewfatherLinkFragment', () => {
  beforeEach(() => {
    mocks.brewfatherStore.getBatchList.mockClear()
    mocks.brewfatherStore.getBatchList.mockResolvedValue(true)
    mocks.brewfatherStore.batches = [
      { brewfatherId: 'bf1', name: 'BF Name', brewDate: '2023', brewer: 'M', style: 'S' }
    ]
  })

  it('loads the Brewfather batch list on mount', async () => {
    mountFragment()
    await flushPromises()
    expect(mocks.brewfatherStore.getBatchList).toHaveBeenCalled()
  })

  it('emits linked with the matched batch when a selection is confirmed', async () => {
    const wrapper = mountFragment()
    await flushPromises()

    wrapper.vm.brewfatherModalCallback(true, 'bf1')

    expect(wrapper.emitted('linked')).toBeTruthy()
    expect(wrapper.emitted('linked')[0][0]).toMatchObject({ brewfatherId: 'bf1', name: 'BF Name' })
  })

  it('does not emit when the callback reports cancelled', async () => {
    const wrapper = mountFragment()
    await flushPromises()

    wrapper.vm.brewfatherModalCallback(false, 'bf1')

    expect(wrapper.emitted('linked')).toBeFalsy()
    expect(wrapper.emitted('cleared')).toBeFalsy()
  })

  it('does not emit when no batch matches the selected id', async () => {
    const wrapper = mountFragment()
    await flushPromises()

    wrapper.vm.brewfatherModalCallback(true, 'no-match')

    expect(wrapper.emitted('linked')).toBeFalsy()
  })

  it('emits cleared when the selection is removed', async () => {
    const wrapper = mountFragment()
    await flushPromises()

    wrapper.vm.brewfatherModalCallback(true, '')

    expect(wrapper.emitted('cleared')).toBeTruthy()
  })
})
