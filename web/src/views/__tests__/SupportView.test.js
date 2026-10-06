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

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import SupportView from '../SupportView.vue'

// Mock pinia before anything else
vi.mock('@/modules/pinia', () => ({
  global: {
    disabled: false,
    fetchTimout: 1000,
    baseURL: 'http://localhost/',
    token: 'test-token'
  }
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

describe('SupportView', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          log: [
            { name: 'log_1_start', value: 1600000000 },
            { name: 'log_1_last', value: 1600001000 }
          ],
          ble: [{ name: 'ble_1_last', value: 1600002000 }]
        })
    })
  })

  it('should render correctly', async () => {
    const wrapper = mount(SupportView)

    // Wait for the fetch promise inside onMounted to resolve and trigger updates
    await flushPromises()
    await nextTick()

    expect(wrapper.text()).toContain('Support')
    expect(wrapper.text()).toContain('Log status')
    expect(wrapper.text()).toContain('2020')
  })
})
