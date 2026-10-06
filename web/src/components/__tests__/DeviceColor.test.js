/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DeviceColorSwatch from '@/components/DeviceColorSwatch.vue'
import { deviceColorOptions } from '@/modules/classes'

const palette = ['black', 'red', 'orange', 'yellow', 'green', 'blue', 'purple', 'pink', 'white']

describe('DeviceColor', () => {
  it.each(['light', 'dark'])('renders a round dot in %s theme', (theme) => {
    const wrapper = mount(DeviceColorSwatch, {
      props: { color: 'white' },
      attachTo: document.body
    })
    wrapper.element.closest('body').setAttribute('data-theme', theme)

    expect(wrapper.classes()).toContain('device-color-swatch')
    expect(wrapper.attributes('style')).toContain('background-color: white')
    expect(wrapper.attributes('aria-label')).toBe('White device color')
    // Not a box: no checkbox-like outline class, and the shape is a circle (see the component style).
    expect(wrapper.classes()).not.toContain('device-color-swatch--outlined')
    expect(wrapper.classes()).not.toContain('rounded-borders')
    wrapper.unmount()
  })

  it.each([undefined, null, ''])('renders nothing at all when the colour is %j', (color) => {
    const wrapper = mount({
      components: { DeviceColorSwatch },
      props: ['color'],
      template: '<div><DeviceColorSwatch :color="color" class="q-mr-sm" />Name</div>'
    }, { props: { color } })

    expect(wrapper.find('.device-color-swatch').exists()).toBe(false)
    expect(wrapper.find('[role="img"]').exists()).toBe(false)
    expect(wrapper.html()).not.toContain('q-mr-sm')
    expect(wrapper.text()).toBe('Name')
  })

  /*
   * The palette is closed on purpose: these values are the DeviceColor enum the API
   * validates against, so an extra entry here would be rejected on save. Asserted
   * against the options list rather than a rendered control — DeviceView now uses the
   * shared AppRadioGroup, the same control as Device Type, so there is no bespoke
   * picker component left to mount.
   */
  it('offers exactly the approved closed palette', () => {
    expect(deviceColorOptions.map((o) => o.value)).toEqual(palette)
  })

  it('labels every colour', () => {
    expect(deviceColorOptions.every((o) => typeof o.label === 'string' && o.label)).toBe(true)
  })
})
