// Copyright (c) 2024-2026 Magnus Persson
// SPDX-License-Identifier: GPL-3.0-only
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { AppInputNumber, AppTextInput, AppTextArea } from '@/ui'

// A label must name its control: `for` on the label and the same id on the input.
describe('form field labels', () => {
  it.each([
    ['text input', AppTextInput, 'input'],
    ['number input', AppInputNumber, 'input'],
    ['text area', AppTextArea, 'textarea']
  ])('%s: the label points at the control', (_, component, tag) => {
    const wrapper = mount(component, { props: { label: 'Name', modelValue: '' }, attachTo: document.body })
    const label = wrapper.get('label.app-field-label')
    const control = wrapper.get(tag)
    expect(label.attributes('for')).toBeTruthy()
    expect(control.attributes('id')).toBe(label.attributes('for'))
    wrapper.unmount()
  })

  it('two fields on one page get different ids', () => {
    const a = mount(AppTextInput, { props: { label: 'A', modelValue: '' } })
    const b = mount(AppTextInput, { props: { label: 'B', modelValue: '' } })
    expect(a.get('label').attributes('for')).not.toBe(b.get('label').attributes('for'))
  })

  it('an explicit id is kept', () => {
    const wrapper = mount(AppTextInput, { props: { label: 'A', modelValue: '' }, attrs: { for: 'my-id' } })
    expect(wrapper.get('label').attributes('for')).toBe('my-id')
  })
})
