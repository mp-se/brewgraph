/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ApiTokenSection from '@/components/ApiTokenSection.vue'

const stubs = {
  AppTextInput: {
    props: ['modelValue', 'disabled'],
    template: '<input class="token-field" type="text" :value="modelValue" :disabled="disabled" />'
  },
  'app-button': {
    props: ['disabled', 'title', 'ariaLabel'],
    emits: ['click'],
    template: '<button :disabled="disabled" :title="title" :aria-label="ariaLabel" @click="$emit(\'click\')"><slot /></button>'
  },
  'q-icon': true
}

describe('ApiTokenSection', () => {
  it('shows a read-only token and explains token rotation before emitting regenerate', async () => {
    const wrapper = mount(ApiTokenSection, {
      props: { token: 'tap-token', disabled: false },
      global: { stubs }
    })

    const tokenField = wrapper.get('input[type="text"]')
    expect(tokenField.element.value).toBe('tap-token')
    expect(tokenField.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('API Token')
    expect(wrapper.text()).toContain('invalidates the previous token')

    const regenerate = wrapper.get('button')
    expect(regenerate.text()).toContain('Regenerate token')
    expect(regenerate.attributes('aria-label')).toContain('immediately rotates the token')
    await regenerate.trigger('click')
    expect(wrapper.emitted('regenerate')).toHaveLength(1)
  })

  it('keeps token rotation unavailable without showing a false loading state', () => {
    const wrapper = mount(ApiTokenSection, {
      props: { token: 'device-token', disabled: true },
      global: { stubs }
    })

    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    expect(wrapper.find('.app-spinner').exists()).toBe(false)
  })
})
