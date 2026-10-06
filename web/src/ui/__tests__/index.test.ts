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

import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { AppMessage } from '../index'

describe('AppMessage', () => {
  it('uses an explicit negative treatment for danger messages', () => {
    const wrapper = mount(AppMessage, {
      props: { alert: 'danger', message: 'Failed to load logfile for device' }
    })

    expect(wrapper.classes()).toContain('app-message')
    expect(wrapper.classes()).toContain('app-message--negative')
  })

  it.each([
    ['warning', 'app-message--warning'],
    ['success', 'app-message--success'],
    ['info', 'app-message--info']
  ])('uses the semantic %s treatment', (alert, expectedClass) => {
    const wrapper = mount(AppMessage, { props: { alert, message: 'Status message' } })

    expect(wrapper.classes()).toContain(expectedClass)
  })

  it.each([
    ['danger', 'warning'],
    ['warning', 'error_outline'],
    ['success', 'check_circle'],
    ['info', 'info']
  ])('renders a labelled, presentational %s severity icon', (alert, expectedIcon) => {
    const wrapper = mount(AppMessage, { props: { alert, message: 'A longer status message' } })
    const icon = wrapper.get('.app-message__icon')

    expect(icon.text()).toBe(expectedIcon)
    expect(icon.attributes('aria-hidden')).toBe('true')
    expect(icon.classes()).toContain('material-icons')
  })

  it('keeps the close action available beside a multiline message', () => {
    const wrapper = mount(AppMessage, {
      props: {
        alert: 'success',
        dismissable: true,
        message: 'This status message is intentionally long enough to wrap on a narrow screen.'
      }
    })

    expect(wrapper.find('.app-message__icon').exists()).toBe(true)
    expect(wrapper.find('button[aria-label="Close"]').exists()).toBe(true)
  })
})
