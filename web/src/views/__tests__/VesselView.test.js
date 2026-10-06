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

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import VesselView from '../VesselView.vue'
import { StorageVessel } from '@/modules/classes'

const { mockRoute, globalMock, vesselStoreMock, batchStoreMock, deviceStoreMock, pourStoreMock } =
  vi.hoisted(() => ({
    mockRoute: { params: { id: 'vessel-1' }, query: {} },
    globalMock: {
      disabled: false,
      clearMessages: vi.fn(),
      messageSuccess: '',
      messageError: '',
      vesselChanged: false,
      updatedVesselData: 0
    },
    vesselStoreMock: {
      vesselList: [
        {
          id: 'vessel-1',
          name: 'Keg 1',
          batchId: 'batch-1',
          vesselType: 'keg',
          status: 'filled',
          fillDate: '2026-01-01',
          totalVolume: 19,
          volumeRemaining: 19,
          bottleVolume: 0,
          bottleCount: 0,
          bottlesRemaining: 0,
          location: '',
          notes: '',
          isOnTap: false,
          toJson: vi.fn().mockReturnValue({ id: 'vessel-1', name: 'Keg 1' })
        }
      ],
      getVessel: vi.fn(),
      addVessel: vi.fn(),
      updateVessel: vi.fn()
    },
    batchStoreMock: {
      batchList: [{ id: 'batch-1', name: 'Batch 1' }],
      getBatchList: vi.fn().mockResolvedValue([])
    },
    deviceStoreMock: {
      devices: [
        { id: 'device-pressure-1', vesselId: null, deviceType: 'pressuremon' },
        { id: 'device-chamber-1', vesselId: null, deviceType: 'chamber_controller' }
      ],
      updateDevice: vi.fn().mockResolvedValue(true)
    },
    pourStoreMock: {
      recordPour: vi.fn(),
      recordBottlePour: vi.fn()
    }
  })
)

vi.mock('pinia', () => ({
  storeToRefs: () => ({
    updatedVesselData: ref(globalMock.updatedVesselData)
  })
}))

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute
}))

vi.mock('@/modules/pinia', () => ({
  global: globalMock,
  vesselStore: vesselStoreMock,
  batchStore: batchStoreMock,
  deviceStore: deviceStoreMock,
  pourStore: pourStoreMock,
  config: { isTempC: true, isPressurePSI: false, isPressureBAR: false }
}))

vi.mock('@/modules/router', () => ({
  default: {
    currentRoute: { value: mockRoute },
    push: vi.fn()
  }
}))

vi.mock('@/ui', async (importActual) => {
  const actual = await importActual()
  return {
    ...actual,
    logDebug: vi.fn()
  }
})

describe('VesselView device pairing', () => {
  const mountWrapper = () =>
    mount(VesselView, {
      global: {
        stubs: {
          'router-link': true,
          AppSelect: true,
          AppTextInput: true,
          AppInputNumber: true
        }
      }
    })

  beforeEach(() => {
    vi.clearAllMocks()
    globalMock.disabled = false
    mockRoute.params = { id: 'vessel-1' }
    deviceStoreMock.devices = [
      { id: 'device-pressure-1', vesselId: null, deviceType: 'pressuremon' },
      { id: 'device-chamber-1', vesselId: null, deviceType: 'chamber_controller' }
    ]
  })

  it('loads existing device assignments on mount for an already-paired vessel', async () => {
    deviceStoreMock.devices[0].vesselId = 'vessel-1'
    deviceStoreMock.devices[1].vesselId = 'vessel-1'
    const wrapper = mountWrapper()
    await vi.waitUntil(() => wrapper.vm.vessel != null)

    expect(wrapper.vm.selectedPressureDeviceId).toBe('device-pressure-1')
    expect(wrapper.vm.selectedChamberDeviceId).toBe('device-chamber-1')
  })

  it('leaves selections null when no device is paired to the vessel', async () => {
    const wrapper = mountWrapper()
    await vi.waitUntil(() => wrapper.vm.vessel != null)

    expect(wrapper.vm.selectedPressureDeviceId).toBeNull()
    expect(wrapper.vm.selectedChamberDeviceId).toBeNull()
  })

  it('keeps a new vessel clean until the user changes it', async () => {
    mockRoute.params = { id: 'new' }
    const wrapper = mountWrapper()
    await vi.waitUntil(() => wrapper.vm.vessel != null)

    expect(wrapper.vm.vesselChanged()).toBe(false)
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()

    wrapper.vm.vessel.name = 'New keg'
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.vesselChanged()).toBe(true)
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
  })

  it('treats a device assignment change as an unsaved vessel change', async () => {
    const wrapper = mountWrapper()
    await vi.waitUntil(() => wrapper.vm.vessel != null)

    wrapper.vm.vessel = new StorageVessel({
      id: 'vessel-1',
      name: 'Keg 1',
      batchId: 'batch-1',
      vesselType: 'keg',
      status: 'filled'
    })
    wrapper.vm.vesselSaved = wrapper.vm.vessel

    expect(wrapper.vm.vesselChanged()).toBe(false)
    wrapper.vm.selectedPressureDeviceId = 'device-pressure-1'

    expect(wrapper.vm.vesselChanged()).toBe(true)
  })

  it('syncDeviceAssignments sets vesselId on the newly-selected device and clears the old one', async () => {
    deviceStoreMock.devices[0].vesselId = 'vessel-1'
    const wrapper = mountWrapper()
    await vi.waitUntil(() => wrapper.vm.vessel != null)

    // Switch the pressure device assignment to a different device.
    deviceStoreMock.devices.push({ id: 'device-pressure-2', vesselId: null, deviceType: 'pressuremon' })
    wrapper.vm.selectedPressureDeviceId = 'device-pressure-2'

    await wrapper.vm.syncDeviceAssignments('vessel-1')

    const oldDev = deviceStoreMock.devices.find((d) => d.id === 'device-pressure-1')
    const newDev = deviceStoreMock.devices.find((d) => d.id === 'device-pressure-2')
    expect(oldDev.vesselId).toBeNull()
    expect(newDev.vesselId).toBe('vessel-1')
    expect(deviceStoreMock.updateDevice).toHaveBeenCalledWith(oldDev)
    expect(deviceStoreMock.updateDevice).toHaveBeenCalledWith(newDev)
  })

  it('syncDeviceAssignments is a no-op for unchanged selections', async () => {
    deviceStoreMock.devices[0].vesselId = 'vessel-1'
    const wrapper = mountWrapper()
    await vi.waitUntil(() => wrapper.vm.vessel != null)

    await wrapper.vm.syncDeviceAssignments('vessel-1')

    expect(deviceStoreMock.updateDevice).not.toHaveBeenCalled()
  })

  it('does not render manual temp/pressure logging (removed in favour of device readings)', async () => {
    const wrapper = mountWrapper()
    await vi.waitUntil(() => wrapper.vm.vessel != null)

    expect(wrapper.text()).not.toContain('Log Temperature')
    expect(wrapper.text()).not.toContain('Log Pressure')
    expect(wrapper.text()).toContain('Device Setup')
  })

  it('keeps disabled save and pour actions idle until their own request starts', async () => {
    globalMock.disabled = true
    const wrapper = mountWrapper()
    await vi.waitUntil(() => wrapper.vm.vessel != null)

    const saveButton = wrapper.get('button[type="submit"]')
    expect(saveButton.attributes('aria-busy')).toBe('false')
    expect(wrapper.find('.app-spinner').exists()).toBe(false)
  })

  describe('device setup instructions', () => {
    const SETUP_TITLE = 'How to configure this device'

    beforeEach(() => {
      deviceStoreMock.devices = [
        { id: 'device-pressure-1', vesselId: null, deviceType: 'pressuremon', token: 'p-token-1', chipId: 'p1', deviceColor: 'Red' },
        { id: 'device-pressure-2', vesselId: null, deviceType: 'pressuremon', token: 'p-token-2', chipId: 'p2', deviceColor: 'Blue' },
        { id: 'device-chamber-1', vesselId: null, deviceType: 'chamber_controller', token: 'c-token-1', chipId: 'c1', deviceColor: 'Green', url: 'http://chamber.local' }
      ]
    })

    it('shows nothing while no device is selected', async () => {
      const wrapper = mountWrapper()
      await vi.waitUntil(() => wrapper.vm.vessel != null)

      expect(wrapper.text()).not.toContain(SETUP_TITLE)
    })

    it('shows URL and token for the paired pressure and chamber devices', async () => {
      deviceStoreMock.devices[0].vesselId = 'vessel-1'
      deviceStoreMock.devices[2].vesselId = 'vessel-1'
      const wrapper = mountWrapper()
      await vi.waitUntil(() => wrapper.vm.vessel != null)

      const text = wrapper.text()
      expect(text.split(SETUP_TITLE).length - 1).toBe(2)
      expect(text).toContain('/ingest/pressuremon')
      expect(text).toContain('p-token-1')
      expect(text).toContain('/ingest/chamber')
      expect(text).toContain('c-token-1')
    })

    it('follows the picker immediately, before saving', async () => {
      const wrapper = mountWrapper()
      await vi.waitUntil(() => wrapper.vm.vessel != null)

      wrapper.vm.selectedPressureDeviceId = 'device-pressure-1'
      await wrapper.vm.$nextTick()
      expect(wrapper.text()).toContain('p-token-1')
      expect(wrapper.text()).not.toContain('c-token-1')

      wrapper.vm.selectedPressureDeviceId = 'device-pressure-2'
      await wrapper.vm.$nextTick()
      expect(wrapper.text()).toContain('p-token-2')
      expect(wrapper.text()).not.toContain('p-token-1')

      wrapper.vm.selectedChamberDeviceId = 'device-chamber-1'
      await wrapper.vm.$nextTick()
      expect(wrapper.text()).toContain('c-token-1')
      expect(wrapper.text().split(SETUP_TITLE).length - 1).toBe(2)

      wrapper.vm.selectedPressureDeviceId = null
      wrapper.vm.selectedChamberDeviceId = null
      await wrapper.vm.$nextTick()
      expect(wrapper.text()).not.toContain(SETUP_TITLE)
      expect(wrapper.text()).not.toContain('p-token-2')
    })
  })
})
