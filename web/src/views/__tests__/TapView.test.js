/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import TapView from '../TapView.vue'
import { Tap } from '@/modules/classes'

const piniaMocks = vi.hoisted(() => ({
  global: { disabled: false, clearMessages: vi.fn(), messageSuccess: '', messageError: '' },
  tapStore: {
    tapList: [],
    getTap: vi.fn(),
    regenerateToken: vi.fn().mockResolvedValue('rotated-tap-token')
  },
  vesselStore: { vesselList: [] }
}))

vi.mock('@/modules/pinia', () => piniaMocks)
vi.mock('vue-router', () => ({ useRoute: () => ({ params: { id: 'tap-1' } }) }))
vi.mock('@/modules/router', () => ({ default: { push: vi.fn() } }))
vi.mock('@/ui', async (importActual) => ({
  ...(await importActual()),
  logDebug: vi.fn()
}))

const stubs = {
  AppPageHeader: true,
  AppTextInput: true,
  AppInputNumber: true,
  AppSelect: true,
  DeviceSetupFragment: {
    props: ['token'],
    template: '<section class="device-setup-fragment">How to configure this device {{ token }}</section>'
  },
  'router-link': true
}

describe('TapView token layout', () => {
  it('places token regeneration with form actions and keeps the setup token current after rotation', async () => {
    piniaMocks.tapStore.tapList = [new Tap({ id: 'tap-1', name: 'Serving tap', token: 'tap-token' })]
    const wrapper = mount(TapView, { global: { stubs } })
    await flushPromises()

    const toolbar = wrapper.get('.tap-action-toolbar')
    const setup = wrapper.get('.device-setup-fragment')
    const regenerateButton = toolbar.get('button[aria-label^="Regenerate API token"]')
    expect(wrapper.find('.api-token-section').exists()).toBe(false)
    expect(toolbar.element.compareDocumentPosition(setup.element) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(setup.text()).toContain('tap-token')

    await regenerateButton.trigger('click')
    await flushPromises()
    expect(piniaMocks.tapStore.regenerateToken).toHaveBeenCalledWith('tap-1')
    expect(wrapper.vm.tap.token).toBe('rotated-tap-token')
    expect(wrapper.get('.device-setup-fragment').text()).toContain('rotated-tap-token')
  })
})
