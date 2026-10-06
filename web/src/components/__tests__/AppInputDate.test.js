/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AppInputDate from '@/components/AppInputDate.vue'

/*
 * The component itself is not new — it has existed since the initial migration and is
 * globally registered, already used by the gravity and pressure list views. It had no
 * tests, and the batch/vessel forms were still using free-text date fields, so this
 * covers it as those forms move onto it.
 */

describe('AppInputDate', () => {
  it('renders a native date input so the browser supplies the calendar', () => {
    const wrapper = mount(AppInputDate, { props: { modelValue: '2026-05-01' } })
    const input = wrapper.find('input')

    expect(input.attributes('type')).toBe('date')
    expect(input.element.value).toBe('2026-05-01')
  })

  it('emits the YYYY-MM-DD value the API expects, unconverted', () => {
    // The native input's value is already in this format, which is why there is no
    // parsing layer here to disagree with the wire format.
    const wrapper = mount(AppInputDate, { props: { modelValue: '' } })

    wrapper.find('input').setValue('2026-07-14')

    expect(wrapper.emitted('update:modelValue')).toEqual([['2026-07-14']])
  })

  it('stays clearable — these fields are nullable', () => {
    const wrapper = mount(AppInputDate, { props: { modelValue: '2026-05-01' } })

    wrapper.find('input').setValue('')

    expect(wrapper.emitted('update:modelValue')).toEqual([['']])
  })

  it('renders null/undefined as empty rather than the string "null"', () => {
    expect(mount(AppInputDate, { props: { modelValue: null } }).find('input').element.value).toBe('')
    expect(
      mount(AppInputDate, { props: { modelValue: undefined } }).find('input').element.value
    ).toBe('')
  })

  it('shows Quasar field label and help text', () => {
    const wrapper = mount(AppInputDate, {
      props: { modelValue: '', label: 'Fill date', help: 'When the keg was filled' }
    })

    expect(wrapper.find('.app-field-label').text()).toBe('Fill date')
    expect(wrapper.find('.app-field-help').text()).toBe('When the keg was filled')
  })

  it('omits its own label when not given', () => {
    const wrapper = mount(AppInputDate, { props: { modelValue: '' } })

    expect(wrapper.find('.app-field-label').exists()).toBe(false)
  })

  it('disables the input', () => {
    const wrapper = mount(AppInputDate, { props: { modelValue: '', disabled: true } })

    expect(wrapper.find('input').attributes('disabled')).toBeDefined()
  })

  it('uses Quasar error presentation', () => {
    const wrapper = mount(AppInputDate, {
      props: { modelValue: '', label: 'Brew date', errorMessage: 'Choose a valid date' }
    })

    expect(wrapper.find('.q-field--error').exists()).toBe(true)
    expect(wrapper.text()).toContain('Choose a valid date')
  })
})
