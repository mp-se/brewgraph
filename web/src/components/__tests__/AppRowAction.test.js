/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { QIcon, QTooltip } from 'quasar'
import AppButton from '@/components/AppButton.vue'
import AppRowAction from '@/components/AppRowAction.vue'
import AppRowActions from '@/components/AppRowActions.vue'

// The real AppButton, not the setup file's plain-button stand-in, so the rendered Quasar classes are checked.
const mountAction = (props, options = {}) =>
  mount(AppRowAction, {
    props: { icon: 'edit', label: 'Edit thing', ...props },
    attachTo: document.body,
    global: { components: { AppButton, QIcon } },
    ...options
  })

describe('AppRowAction', () => {
  it('is a filled, dense icon button named by its label, not flat or round', () => {
    const wrapper = mountAction()

    expect(wrapper.element.tagName).toBe('BUTTON')
    expect(wrapper.classes()).toEqual(expect.arrayContaining(['app-button', 'app-button--dense', 'q-btn--standard']))
    expect(wrapper.classes()).not.toContain('q-btn--flat')
    expect(wrapper.classes()).not.toContain('q-btn--round')
    expect(wrapper.attributes('aria-label')).toBe('Edit thing')
    wrapper.unmount()
  })

  it('carries a tooltip with the same text as the aria-label', () => {
    const wrapper = mountAction({ label: 'Show device log' })

    const tooltip = wrapper.findComponent(QTooltip)
    expect(tooltip.exists()).toBe(true)
    // The tooltip's content is only rendered while it is shown; read its slot instead.
    expect(tooltip.vm.$slots.default()[0].children).toBe('Show device log')
    expect(wrapper.attributes('aria-label')).toBe('Show device log')
    wrapper.unmount()
  })

  it.each(['primary', 'negative', 'positive', 'warning', 'info', 'secondary'])('%s is coloured by its app-button kind', (kind) => {
    const wrapper = mountAction({ kind })

    expect(wrapper.classes()).toContain(`app-button--${kind}`)
    wrapper.unmount()
  })

  it('is secondary (grey) when no kind is given', () => {
    const wrapper = mountAction()

    expect(wrapper.classes()).toContain('app-button--secondary')
    wrapper.unmount()
  })

  it('shows its icon', () => {
    const wrapper = mountAction({ icon: 'delete_forever' })

    expect(wrapper.text()).toContain('delete_forever')
    wrapper.unmount()
  })

  it('emits click and honours disable', async () => {
    const onClick = vi.fn()
    const wrapper = mountAction({}, { attrs: { onClick } })

    await wrapper.trigger('click')
    expect(onClick).toHaveBeenCalledTimes(1)

    const disabled = mountAction({}, { attrs: { disable: true, onClick } })
    expect(disabled.attributes('disabled')).toBeDefined()
    wrapper.unmount()
    disabled.unmount()
  })

  it('stays focusable by keyboard', () => {
    const wrapper = mountAction()

    expect(wrapper.attributes('tabindex')).not.toBe('-1')
    wrapper.element.focus()
    expect(document.activeElement).toBe(wrapper.element)
    wrapper.unmount()
  })
})

describe('AppRowActions', () => {
  it('groups the row actions under one label', () => {
    const wrapper = mount(AppRowActions, { props: { label: 'Device actions' }, slots: { default: '<span>x</span>' } })

    expect(wrapper.attributes('role')).toBe('group')
    expect(wrapper.attributes('aria-label')).toBe('Device actions')
    expect(wrapper.text()).toBe('x')
  })
})
