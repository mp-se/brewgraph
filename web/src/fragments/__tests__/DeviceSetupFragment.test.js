/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

// deps ../DeviceSetupFragment.vue

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DeviceSetupFragment from '../DeviceSetupFragment.vue'

function render(deviceType) {
  return mount(DeviceSetupFragment, { props: { deviceType, token: 'tok-123', hasReadings: false } })
}

describe('DeviceSetupFragment', () => {
  it.each(['gravitymon', 'gravitymon_gateway', 'ispindel', 'pressuremon', 'kegmon', 'chamber_controller'])(
    'shows the server URL and token for %s',
    (type) => {
      const wrapper = render(type)
      expect(wrapper.text()).toContain('Server URL')
      expect(wrapper.text()).toContain('Token')
      expect(wrapper.text()).toContain('tok-123')
      expect(wrapper.text()).not.toContain('No setup instructions')
      expect(wrapper.findAll('button').filter((b) => b.text().includes('Copy')).length).toBeGreaterThanOrEqual(2)
    }
  )

  it.each(['gravitymon', 'gravitymon_gateway', 'ispindel', 'pressuremon', 'chamber_controller'])(
    'shows the ingest path for %s',
    (type) => {
      expect(render(type).text()).toContain('/ingest/')
    }
  )

  it('shows the full ingest URL for a gravity device', () => {
    expect(render('gravitymon').text()).toContain(`http://${window.location.host}/ingest/gravitymon`)
  })

  it('shows the server only for a Kegmon', () => {
    const wrapper = render('kegmon')
    expect(wrapper.find('code').text()).toBe(`http://${window.location.host}`)
  })

  it('lists address, path, port and SSL separately for an iSpindel', () => {
    const text = render('ispindel').text()
    expect(text).toContain('Server address')
    expect(text).toContain('Port')
    expect(text).toContain('Use SSL')
  })

  describe('token in the URL', () => {
    const origin = `http://${window.location.host}`
    const copyButtons = (wrapper) => wrapper.findAll('button').filter((b) => b.text().includes('Copy'))

    it.each(['gravitymon', 'gravitymon_gateway', 'ispindel', 'pressuremon'])(
      'offers the body, query and path variants for %s',
      (type) => {
        const wrapper = render(type)
        const path = type === 'gravitymon_gateway' ? 'gravitymon' : type
        expect(wrapper.text()).toContain('Token')
        expect(wrapper.find('[data-variant="query"] code').text()).toBe(`${origin}/ingest/${path}?token=tok-123`)
        expect(wrapper.find('[data-variant="path"] code').text()).toBe(`${origin}/ingest/${path}/tok-123`)
      }
    )

    it('gives every variant its own copy button', () => {
      const wrapper = render('pressuremon')
      expect(wrapper.find('[data-variant="query"] button').exists()).toBe(true)
      expect(wrapper.find('[data-variant="path"] button').exists()).toBe(true)
      // server URL + token + the two URL variants
      expect(copyButtons(wrapper)).toHaveLength(4)
    })

    it('shows <token> without copy buttons while the token is only a placeholder', () => {
      const wrapper = mount(DeviceSetupFragment, {
        props: { deviceType: 'ispindel', token: '<token>', hasReadings: false }
      })
      expect(wrapper.find('[data-variant="query"] code').text()).toBe(`${origin}/ingest/ispindel?token=<token>`)
      expect(wrapper.find('[data-variant="path"] code').text()).toBe(`${origin}/ingest/ispindel/<token>`)
      expect(wrapper.find('[data-variant="query"] button').exists()).toBe(false)
      expect(wrapper.find('[data-variant="path"] button').exists()).toBe(false)
    })

    it.each(['kegmon', 'chamber_controller'])('leaves %s setup unchanged', (type) => {
      const wrapper = render(type)
      expect(wrapper.find('[data-variant]').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('?token=')
    })
  })

  it('says so when the device type has no instructions', () => {
    expect(render('').text()).toContain('No setup instructions available')
  })
})
