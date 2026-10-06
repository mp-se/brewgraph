/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'

const { copyToClipboard } = vi.hoisted(() => ({ copyToClipboard: vi.fn() }))
vi.mock('@/modules/utils', () => ({ copyToClipboard }))

import CodeViewModal from '@/components/CodeViewModal.vue'

// Render Quasar's dialog pieces inline so the dialog content is inspectable.
const passthrough = (tag) =>
  defineComponent({ setup: (_, { slots }) => () => h(tag, slots.default?.()) })
const stubs = {
  QDialog: passthrough('div'),
  QCard: passthrough('div'),
  QCardSection: passthrough('div'),
  QBtn: defineComponent({
    props: { label: String },
    emits: ['click'],
    setup: (props, { emit }) => () => h('button', { onClick: () => emit('click') }, props.label)
  })
}

describe('CodeViewModal', () => {
  beforeEach(() => copyToClipboard.mockReset())

  it('shows the text and emits click when opened', async () => {
    const wrapper = mount(CodeViewModal, {
      props: { modelValue: '{\n  "a": 1\n}', button: 'View config' },
      global: { stubs }
    })
    expect(wrapper.find('pre').text()).toContain('"a": 1')
    await wrapper.findAll('button').find((b) => b.text() === 'View config').trigger('click')
    expect(wrapper.emitted('click')).toHaveLength(1)
  })

  it('copies the shown text and confirms it', async () => {
    copyToClipboard.mockResolvedValue(true)
    const wrapper = mount(CodeViewModal, { props: { modelValue: '{"a":1}' }, global: { stubs } })
    await wrapper.findAll('button').find((b) => b.text() === 'Copy').trigger('click')
    await flushPromises()

    expect(copyToClipboard).toHaveBeenCalledWith('{"a":1}')
    expect(wrapper.text()).toContain('Copied to clipboard.')
  })

  it('says so when the copy fails', async () => {
    copyToClipboard.mockResolvedValue(false)
    const wrapper = mount(CodeViewModal, { props: { modelValue: 'x' }, global: { stubs } })
    await wrapper.vm.copy()
    await flushPromises()
    expect(wrapper.text()).toContain('Unable to copy.')
  })
})
