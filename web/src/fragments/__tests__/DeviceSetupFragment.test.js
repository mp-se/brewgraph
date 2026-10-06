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
      expect(wrapper.text()).toContain('/ingest/')
      expect(wrapper.text()).not.toContain('No setup instructions')
      expect(wrapper.findAll('button').filter((b) => b.text().includes('Copy')).length).toBeGreaterThanOrEqual(2)
    }
  )

  it('shows the full ingest URL for a gravity device', () => {
    expect(render('gravitymon').text()).toContain(`http://${window.location.host}/ingest/gravitymon`)
  })

  it('lists address, path, port and SSL separately for an iSpindel', () => {
    const text = render('ispindel').text()
    expect(text).toContain('Server address')
    expect(text).toContain('Port')
    expect(text).toContain('Use SSL')
  })

  it('says so when the device type has no instructions', () => {
    expect(render('').text()).toContain('No setup instructions available')
  })
})
