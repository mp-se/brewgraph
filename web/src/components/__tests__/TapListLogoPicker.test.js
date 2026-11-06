/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import TapListLogoPicker from '../TapListLogoPicker.vue'

const KEYS = ['hop', 'barley', 'barrel', 'kettle', 'bottle', 'glass', 'tap', 'yeast']

describe('TapListLogoPicker', () => {
  it('shows the eight symbols and a No logo tile', () => {
    const wrapper = mount(TapListLogoPicker, { props: { modelValue: null } })
    const tiles = wrapper.findAll('[role="radio"]')
    expect(tiles.map((t) => t.attributes('data-logo'))).toEqual([...KEYS, 'none'])
  })

  it('loads each symbol from the display app', () => {
    const wrapper = mount(TapListLogoPicker, { props: { modelValue: null } })
    expect(wrapper.find('[data-logo="hop"] .tap-logo-picker__symbol').attributes('style')).toContain(
      'url(/public/logos/hop.svg)'
    )
  })

  it('marks the selected tile and previews it', () => {
    const wrapper = mount(TapListLogoPicker, { props: { modelValue: 'barrel' } })
    expect(wrapper.find('[data-logo="barrel"]').attributes('aria-checked')).toBe('true')
    expect(wrapper.find('[data-logo="hop"]').attributes('aria-checked')).toBe('false')
    expect(wrapper.find('[data-testid="logo-preview"] [role="img"]').attributes('style')).toContain(
      '/public/logos/barrel.svg'
    )
  })

  it('marks No logo as selected when there is none, with no preview image', () => {
    const wrapper = mount(TapListLogoPicker, { props: { modelValue: null } })
    expect(wrapper.find('[data-logo="none"]').attributes('aria-checked')).toBe('true')
    expect(wrapper.find('[data-testid="logo-preview"] [role="img"]').exists()).toBe(false)
  })

  it('emits the key on select and null on No logo', async () => {
    const wrapper = mount(TapListLogoPicker, { props: { modelValue: null } })
    await wrapper.find('[data-logo="yeast"]').trigger('click')
    await wrapper.find('[data-logo="none"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['yeast'], [null]])
  })
})
