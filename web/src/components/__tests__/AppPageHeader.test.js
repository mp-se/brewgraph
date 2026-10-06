/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AppPageHeader from '@/components/AppPageHeader.vue'

describe('AppPageHeader', () => {
  it('renders the title with the filters beside it when there is no page action', () => {
    const wrapper = mount(AppPageHeader, { props: { title: 'Things' }, slots: { default: '<i class="filter" />' } })

    expect(wrapper.find('.text-h6').text()).toBe('Things')
    expect(wrapper.find('.app-page-header__action').exists()).toBe(false)
    expect(wrapper.find('.col-md-6 .filter').exists()).toBe(true)
  })

  it('puts the page action on the title line and the filters on their own line', () => {
    const wrapper = mount(AppPageHeader, {
      props: { title: 'Things' },
      slots: { action: '<button class="add">Add Thing</button>', default: '<i class="filter" />' }
    })

    const row = wrapper.find('.app-page-header')
    const children = [...row.element.children]
    expect(children[0].textContent).toContain('Things')
    expect(children[1].classList.contains('app-page-header__action')).toBe(true)
    expect(children[1].querySelector('.add').textContent).toBe('Add Thing')
    expect(children[2].classList.contains('col-12')).toBe(true)
    expect(children[2].querySelector('.filter')).not.toBeNull()
  })
})
