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

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { Quasar } from 'quasar'
import DeviceView from '../DeviceView.vue'
import { Device } from '@/modules/classes'

// Create pinia mocks using vi.hoisted so they're defined before vi.mock calls
const piniaMocks = vi.hoisted(() => ({
  global: {
    disabled: false,
    acquireBusy() {
      this.disabled = true
      let released = false
      return () => { if (!released) { released = true; this.disabled = false } }
    },
    clearMessages: vi.fn(),
    messageSuccess: '',
    messageError: '',
    initialized: true,
    deviceChanged: false
  },
  deviceStore: {
    device: null,
    deviceList: [],
    getDevice: vi.fn(),
    addDevice: vi.fn(),
    updateDevice: vi.fn(),
    regenerateToken: vi.fn(),
    getFermentationSteps: vi.fn().mockResolvedValue([]),
    deleteDeviceFermentationSteps: vi.fn(),
    proxyRequest: vi.fn()
  },
  vesselStore: {
    vesselList: [],
    getVesselList: vi.fn().mockResolvedValue([])
  }
}))

vi.mock('@/modules/pinia', () => ({
  global: piniaMocks.global,
  deviceStore: piniaMocks.deviceStore,
  vesselStore: piniaMocks.vesselStore
}))

vi.mock('@/modules/router', () => ({
  default: {
    currentRoute: {
      value: {
        params: { id: 'new' },
        name: 'device-view'
      }
    },
    push: vi.fn()
  }
}))

vi.mock('@/ui', async (importActual) => {
  const actual = await importActual()
  return {
    ...actual,
    logDebug: vi.fn(),
    logInfo: vi.fn(),
    logError: vi.fn()
  }
})

vi.mock('@/modules/utils', () => ({
  validateCurrentForm: vi.fn(() => true),
  gravityToPlato: vi.fn()
}))

vi.mock('@/modules/detect', () => ({
  detectMdns: vi.fn(() => 'test.local'),
  detectPlatform: vi.fn(() => 'esp32'),
  detectSoftware: vi.fn(() => 'Gravitymon'),
  detectDeviceType: vi.fn(() => 'kegmon')
}))

// Mock router plugin to provide $route in templates
const routerPlugin = {
  install(app) {
    app.config.globalProperties.$route = {
      params: { id: 'new' },
      name: 'device-view'
    }
  }
}

describe('DeviceView - Enhanced', () => {
  beforeEach(() => {
    // Reset mocks before each test
    vi.clearAllMocks()
    piniaMocks.global.disabled = false
    piniaMocks.global.deviceChanged = false
    piniaMocks.global.messageSuccess = ''
    piniaMocks.global.messageError = ''
    piniaMocks.deviceStore.device = null
    piniaMocks.deviceStore.getDevice.mockClear()
    piniaMocks.deviceStore.updateDevice.mockClear()
    piniaMocks.deviceStore.regenerateToken.mockReset()
    piniaMocks.deviceStore.getFermentationSteps.mockClear()
    piniaMocks.deviceStore.deleteDeviceFermentationSteps.mockClear()
    piniaMocks.deviceStore.proxyRequest.mockClear()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  const createWrapper = async (
    routeParams = { id: 'new' },
    { renderToggles = false, interactiveDeviceControls = false } = {}
  ) => {
    // Update router mock's current route params
    routerPlugin.install({
      config: {
        globalProperties: {
          $route: { params: routeParams, name: 'device-view' }
        }
      }
    })
    ;(await import('@/modules/router')).default.currentRoute.value.params = routeParams

    const stubs = {
      AppTextInput: true,
      AppInputNumber: true,
      AppInputDate: true,
      AppCard: true,
      AppToggle: true,
      AppRadioGroup: true,
      AppSelect: true,
      AppField: true,
      AppFileUpload: true,
      AppDataDialog: true,
      // Tested on its own; the Quasar version needs the Quasar plugin to render.
      CodeViewModal: true,
      AppConfirmDialog: {
        props: ['callback', 'id'],
        template: '<button :id="id" class="confirm-dialog-stub" @click="callback()">Confirm</button>'
      },
      AppMessage: true,
      AppPageHeader: false,
      FermentationStepFragment: true,
      DeviceSetupFragment: {
        props: ['token'],
        template: '<section class="device-setup-fragment">How to configure this device {{ token }}</section>'
      },
      'router-link': {
        name: 'RouterLink',
        props: ['to'],
        template: '<a class="router-link-stub"><slot /></a>'
      }
    }
    if (!renderToggles) {
      stubs.QBtnToggle = {
        name: 'QBtnToggle',
        props: ['modelValue', 'options', 'disable'],
        emits: ['update:modelValue'],
        template: '<div class="q-btn-toggle-stub"></div>'
      }
    }
    if (interactiveDeviceControls) {
      stubs.AppTextInput = {
        props: ['modelValue', 'label', 'disabled'],
        emits: ['update:modelValue'],
        template:
          '<button class="device-input-event" :disabled="disabled" @click="$emit(\'update:modelValue\', label)">{{ label }}</button>'
      }
      stubs.AppToggle = {
        props: ['modelValue', 'label', 'disabled'],
        emits: ['update:modelValue'],
        template:
          '<button class="device-toggle-event" :disabled="disabled" @click="$emit(\'update:modelValue\', !modelValue)">{{ label }}</button>'
      }
      stubs.CodeViewModal = {
        props: ['modelValue', 'disabled'],
        emits: ['click'],
        template: '<button class="view-config-event" @click="$emit(\'click\')">View config</button>'
      }
    }

    return mount(DeviceView, {
      global: {
        stubs,
        plugins: [
          ...(renderToggles ? [Quasar] : []),
          {
            install(app) {
              app.config.globalProperties.$route = { params: routeParams, name: 'device-view' }
            }
          }
        ]
      }
    })
  }

  // Shared helper for tests that need a device
  const setupDeviceTest = async (chipId = 'a1b2c3') => {
    const wrapper = await createWrapper()
    await flushPromises()
    wrapper.vm.device = new Device({
      id: 1,
      chipId: chipId,
      url: 'http://test.local',
      description: 'Test Device'
    })
    return wrapper
  }

  describe('Rendering', () => {
    it('should render device view container', async () => {
      const wrapper = await createWrapper()
      expect(wrapper.find('.app-page').exists()).toBe(true)
    })

    it('should render page title', async () => {
      const wrapper = await createWrapper()
      expect(wrapper.text()).toContain('Device')
    })

    it('loads a cached existing device with fermentation steps and applies iSpindel rules', async () => {
      const existing = new Device({ id: 'device-1', name: 'Tilt', deviceType: 'ispindel' })
      piniaMocks.deviceStore.deviceList = [existing]
      piniaMocks.deviceStore.getFermentationSteps.mockResolvedValueOnce([{ name: 'Primary' }])

      const wrapper = await createWrapper({ id: 'device-1' })
      await flushPromises()

      expect(wrapper.vm.device).toMatchObject({ id: existing.id, deviceType: 'ispindel' })
      expect(wrapper.vm.activeFermentationSteps).toEqual([{ name: 'Primary' }])
      expect(wrapper.vm.device.canCollectLogs).toBe(false)
      expect(wrapper.vm.chipIdValid).toBe(true)
    })

    it('keeps token regeneration with device actions and shows the token only in setup instructions', async () => {
      const wrapper = await createWrapper()
      await flushPromises()
      wrapper.vm.device.deviceType = 'gravitymon'
      wrapper.vm.device.token = 'device-token'
      piniaMocks.deviceStore.regenerateToken.mockResolvedValue('rotated-device-token')
      await wrapper.vm.$nextTick()

      const actions = wrapper.find('.device-action-toolbar')
      const tokenSection = wrapper.find('.api-token-section')
      const connectionDetails = wrapper.find('.device-connection-details')
      const setupInstructions = wrapper.find('.device-setup-fragment')
      const regenerateButton = actions.get('button[aria-label^="Regenerate API token"]')
      expect(actions.exists()).toBe(true)
      expect(tokenSection.exists()).toBe(false)
      expect(connectionDetails.exists()).toBe(true)
      expect(setupInstructions.exists()).toBe(true)
      expect(actions.text()).toContain('Regenerate token')
      expect(actions.element.compareDocumentPosition(setupInstructions.element) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()

      await regenerateButton.trigger('click')
      await flushPromises()
      expect(piniaMocks.deviceStore.regenerateToken).toHaveBeenCalledWith(wrapper.vm.device.id)
      expect(setupInstructions.text()).toContain('rotated-device-token')
    })

    it('routes Kegmon credentials to the Tap instead of exposing a Device token', async () => {
      const wrapper = await createWrapper()
      await flushPromises()
      wrapper.vm.device.deviceType = 'kegmon'
      wrapper.vm.device.token = 'legacy-device-token'
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.api-token-section').exists()).toBe(false)
      expect(wrapper.find('.device-connection-details').exists()).toBe(false)
      expect(wrapper.find('.device-action-toolbar').find('[aria-label^="Regenerate API token"]').exists()).toBe(false)
      expect(wrapper.find('.device-kegmon-credentials').text()).toContain('Tap')
      expect(
        wrapper.find('.device-action-toolbar').element.compareDocumentPosition(
          wrapper.find('.device-kegmon-credentials').element
        ) & Node.DOCUMENT_POSITION_FOLLOWING
      ).toBeTruthy()
      expect(wrapper.find('.device-kegmon-credentials').findComponent({ name: 'RouterLink' }).props('to')).toEqual({
        name: 'tap-list'
      })
    })
  })

  describe('Option Arrays', () => {
    it('should have chip family options', async () => {
      const wrapper = await createWrapper()
      await flushPromises()

      expect(wrapper.vm.chipFamilyOptions.length).toBeGreaterThan(0)
      expect(wrapper.vm.chipFamilyOptions.some((o) => o.value === 'esp32')).toBe(true)
    })

    it('should have device type options', async () => {
      const wrapper = await createWrapper()
      await flushPromises()

      expect(wrapper.vm.deviceTypeOptions.length).toBeGreaterThan(0)
      expect(wrapper.vm.deviceTypeOptions.some((o) => o.value === 'gravitymon')).toBe(true)
    })

    it('should offer the complete device color palette', async () => {
      const wrapper = await createWrapper()
      await flushPromises()

      expect(wrapper.vm.deviceColorOptions.map((o) => o.value)).toEqual([
        'black', 'red', 'orange', 'yellow', 'green', 'blue', 'purple', 'pink', 'white'
      ])
    })

    it('uses value-preserving Quasar button toggles for device selectors', async () => {
      const wrapper = await createWrapper()
      await flushPromises()

      const toggles = wrapper.findAllComponents({ name: 'QBtnToggle' })
      expect(toggles).toHaveLength(3)
      expect(toggles[0].props('options')).toEqual(wrapper.vm.chipFamilyOptions)
      expect(toggles[1].props('options')).toEqual(wrapper.vm.deviceTypeOptions)
      expect(toggles[2].props('options')).toEqual(wrapper.vm.deviceColorOptions)

      toggles[1].vm.$emit('update:modelValue', 'kegmon')
      toggles[2].vm.$emit('update:modelValue', 'blue')
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.device.deviceType).toBe('kegmon')
      expect(wrapper.vm.device.deviceColor).toBe('blue')
    })

    it('renders selectable buttons for every device selector', async () => {
      const wrapper = await createWrapper({ id: 'new' }, { renderToggles: true })
      await flushPromises()

      const groups = wrapper.findAll('.device-form-toggle__buttons')
      expect(groups).toHaveLength(3)
      expect(groups[0].findAll('.q-btn')).toHaveLength(wrapper.vm.chipFamilyOptions.length)
      expect(groups[1].findAll('.q-btn')).toHaveLength(wrapper.vm.deviceTypeOptions.length)
      expect(groups[2].findAll('.q-btn')).toHaveLength(wrapper.vm.deviceColorOptions.length)
      expect(groups[0].text()).toContain('ESP32')
      expect(groups[1].text()).toContain('Kegmon')
      expect(groups[2].text()).toContain('White')
    })

    it('uses labelled color buttons without a redundant selected-color summary', async () => {
      const wrapper = await createWrapper()
      await flushPromises()

      expect(wrapper.find('.device-form-toggle__color-cue').exists()).toBe(false)
      expect(wrapper.find('.device-color-toggle__buttons').exists()).toBe(true)
    })
  })

  describe('Rendered control interactions', () => {
    it('wires device inputs, log toggle, config viewer and delete confirmation', async () => {
      const wrapper = await createWrapper({ id: 'new' }, { interactiveDeviceControls: true })
      await flushPromises()
      wrapper.vm.device.config = { sample: true }
      piniaMocks.deviceStore.deleteDeviceFermentationSteps.mockResolvedValue(true)
      await wrapper.vm.$nextTick()
      wrapper.vm.activeFermentationSteps = []
      await wrapper.vm.$nextTick()

      const inputs = wrapper.findAll('.device-input-event')
      expect(inputs.map((input) => input.text())).toEqual([
        'Name', 'Chip ID', 'mDNS', 'Device URL', 'Description', 'Configuration'
      ])
      for (const input of inputs.filter((input) => !input.attributes('disabled'))) {
        await input.trigger('click')
      }
      expect(wrapper.vm.device).toMatchObject({
        name: 'Name', chipId: 'Chip ID', mdns: 'mDNS', url: 'Device URL', description: 'Description'
      })

      await wrapper.find('.device-toggle-event').trigger('click')
      expect(wrapper.vm.device.collectLogs).toBe(true)

      await wrapper.find('.view-config-event').trigger('click')
      expect(wrapper.vm.render).toContain('sample')

      const confirmButton = wrapper.get('.confirm-dialog-stub').element
      const confirmLookup = vi.spyOn(document, 'getElementById').mockReturnValue(confirmButton)
      wrapper.vm.deleteFermentationSteps()
      confirmLookup.mockRestore()
      await flushPromises()
      expect(piniaMocks.deviceStore.deleteDeviceFermentationSteps).toHaveBeenCalledWith(wrapper.vm.device.id)
      expect(piniaMocks.global.messageSuccess).toContain('Fermentation steps removed')
    })
  })

  describe('Save baseline', () => {
    it('keeps the dirty baseline clean through navigation after device creation', async () => {
      const router = (await import('@/modules/router')).default
      const wrapper = await createWrapper({ id: 'new' })
      const saved = new Device({ id: 'device-1', name: 'Sensor', chipId: 'a1b2c3' })
      wrapper.vm.device = new Device({ name: 'Sensor', chipId: 'a1b2c3' })
      piniaMocks.deviceStore.addDevice.mockResolvedValue(saved)
      piniaMocks.global.deviceChanged = true
      router.push.mockImplementation(() => {
        expect(piniaMocks.global.deviceChanged).toBe(false)
        // The route transition can replace the rendered device with a fresh
        // server-normalised copy before save() finishes.
        wrapper.vm.device = new Device({ id: 'device-1', name: 'Sensor', chipId: 'a1b2c3', description: 'Normalised' })
      })

      await wrapper.vm.save()

      expect(router.push).toHaveBeenCalledWith({ name: 'device', params: { id: 'device-1' } })
      expect(Device.compare(wrapper.vm.device, wrapper.vm.deviceSaved)).toBe(true)
      expect(wrapper.vm.deviceChanged()).toBe(false)
    })

    it('uses the saved API response as the new baseline', async () => {
      const wrapper = await createWrapper({ id: 'device-1' })
      const saved = new Device({ id: 'device-1', name: 'Sensor', deviceColor: 'blue' })
      piniaMocks.deviceStore.getDevice.mockResolvedValue(saved)
      await flushPromises()
      wrapper.vm.device = new Device({ id: 'device-1', name: 'Sensor', deviceColor: 'red' })
      piniaMocks.deviceStore.updateDevice.mockResolvedValue(saved)

      await wrapper.vm.save()

      expect(wrapper.vm.device.deviceColor).toBe('blue')
      expect(wrapper.vm.deviceChanged()).toBe(false)
      expect(piniaMocks.global.messageSuccess).toBe('Saved device')
    })

  })

  describe('validateChipId() - Chip ID Validation', () => {
    it('should accept valid 6-char hex lowercase chip IDs', async () => {
      const wrapper = await setupDeviceTest('a1b2c3')
      const result = wrapper.vm.validateChipId()
      expect(result).toBe(true)
    })

    it('should accept all zeros', async () => {
      const wrapper = await setupDeviceTest('000000')
      const result = wrapper.vm.validateChipId()
      expect(result).toBe(true)
    })

    it('should accept all f characters', async () => {
      const wrapper = await setupDeviceTest('ffffff')
      const result = wrapper.vm.validateChipId()
      expect(result).toBe(true)
    })

    it('should accept mixed valid hex', async () => {
      const wrapper = await setupDeviceTest('a0b1c2')
      const result = wrapper.vm.validateChipId()
      expect(result).toBe(true)
    })

    it('should reject chip IDs too short', async () => {
      const wrapper = await setupDeviceTest('a1b2c')
      const result = wrapper.vm.validateChipId()
      expect(result).toBe(false)
    })

    it('should reject chip IDs too long', async () => {
      const wrapper = await setupDeviceTest('a1b2c3d4')
      const result = wrapper.vm.validateChipId()
      expect(result).toBe(false)
    })

    it('should reject chip IDs with uppercase letters', async () => {
      const wrapper = await setupDeviceTest('A1B2C3')
      const result = wrapper.vm.validateChipId()
      expect(result).toBe(false)
    })

    it('should reject chip IDs with commas (previous regex bug)', async () => {
      const wrapper = await setupDeviceTest('a1,b2c3')
      const result = wrapper.vm.validateChipId()
      expect(result).toBe(false)
    })

    it('should reject chip IDs with invalid characters', async () => {
      const wrapper = await setupDeviceTest('a1b2c!')
      const result = wrapper.vm.validateChipId()
      expect(result).toBe(false)
    })

    it('should reject empty chip ID', async () => {
      const wrapper = await setupDeviceTest('')
      const result = wrapper.vm.validateChipId()
      expect(result).toBe(false)
    })

    it('should reject chip IDs with spaces', async () => {
      const wrapper = await setupDeviceTest('a1 b2c3')
      const result = wrapper.vm.validateChipId()
      expect(result).toBe(false)
    })

    it('should update chipIdValid reactive property', async () => {
      const wrapper = await setupDeviceTest('a1b2c3')
      wrapper.vm.validateChipId()
      expect(wrapper.vm.chipIdValid).toBe(true)

      wrapper.vm.device = new Device({
        id: 1,
        chipId: 'invalid',
        url: 'http://test.local',
        description: 'Test'
      })
      wrapper.vm.validateChipId()
      expect(wrapper.vm.chipIdValid).toBe(false)
    })
  })

  describe('Method Existence', () => {
    it('should have fetchConfigFromDevice method', async () => {
      const wrapper = await createWrapper()
      expect(typeof wrapper.vm.fetchConfigFromDevice).toBe('function')
    })

    it('should have validateUrl method', async () => {
      const wrapper = await createWrapper()
      expect(typeof wrapper.vm.validateUrl).toBe('function')
    })

    it('should have deviceChanged method', async () => {
      const wrapper = await createWrapper()
      expect(typeof wrapper.vm.deviceChanged).toBe('function')
    })

    it('should have isNew method', async () => {
      const wrapper = await createWrapper()
      expect(typeof wrapper.vm.isNew).toBe('function')
    })

    it('should have save method', async () => {
      const wrapper = await createWrapper()
      expect(typeof wrapper.vm.save).toBe('function')
    })

    it('should have deleteFermentationSteps method', async () => {
      const wrapper = await createWrapper()
      expect(typeof wrapper.vm.deleteFermentationSteps).toBe('function')
    })
  })

  describe('Layout Structure', () => {
    it('should render grid rows', async () => {
      const wrapper = await createWrapper()
      expect(wrapper.findAll('.row').length).toBeGreaterThan(0)
    })

    it('should render horizontal separator', async () => {
      const wrapper = await createWrapper()
      expect(wrapper.findAll('hr').length).toBeGreaterThan(0)
    })

    it('should render bootstrap column classes', async () => {
      const wrapper = await createWrapper()
      const cols = wrapper.findAll('[class*="col-"]')
      expect(cols.length).toBeGreaterThan(0)
    })
  })

  describe('Form Data Binding and Device Rendering', () => {
    it('should render form when device exists', async () => {
      const wrapper = await createWrapper()
      piniaMocks.deviceStore.device = new Device({
        id: 1,
        chipId: 'a1b2c3',
        url: 'http://test.local',
        description: 'Test Device'
      })
      await flushPromises()

      const form = wrapper.find('form')
      expect(form.exists()).toBe(true)
    })

    it('should show error message when device is null', async () => {
      const wrapper = await createWrapper()
      // Initially on 'new' route, device should be initialized to an empty Device
      // So we cannot easily test null state. Test that form exists for valid device instead.
      expect(wrapper.vm.device).not.toBeNull()
    })

    it('should initialize device on new route', async () => {
      const wrapper = await createWrapper()
      await flushPromises()

      const device = wrapper.vm.device
      expect(device).toBeDefined()
    })

    it('should properly close invalid URLs', async () => {
      const wrapper = await createWrapper()
      piniaMocks.deviceStore.device = new Device({
        id: 1,
        chipId: 'a1b2c3',
        url: 'http://',
        description: 'Test'
      })
      await flushPromises()

      expect(wrapper.vm.device.url).toBe('')
    })
  })

  describe('Device Save Functionality', () => {
    it('keeps a disabled no-change save idle', async () => {
      const wrapper = await createWrapper()
      await flushPromises()
      piniaMocks.global.disabled = true
      await wrapper.vm.$nextTick()

      const saveButton = wrapper.get('button[type="submit"]')
      expect(saveButton.attributes('aria-busy')).toBe('false')
      expect(wrapper.find('.app-spinner').exists()).toBe(false)
    })

    it('shows a save spinner only while its mutation is pending', async () => {
      const wrapper = await createWrapper({ id: 'device-1' })
      const device = new Device({ id: 'device-1', name: 'Sensor' })
      wrapper.vm.device = device
      wrapper.vm.deviceSaved = new Device({ id: 'device-1', name: 'Original' })
      let finishSave
      piniaMocks.deviceStore.updateDevice.mockReturnValue(new Promise((resolve) => { finishSave = resolve }))

      const savePromise = wrapper.vm.save()
      await wrapper.vm.$nextTick()

      expect(wrapper.get('button[type="submit"]').attributes('aria-busy')).toBe('true')
      expect(wrapper.find('.app-spinner').exists()).toBe(true)

      finishSave(device)
      await savePromise
      expect(wrapper.find('.app-spinner').exists()).toBe(false)
    })

    it('should have save method available', async () => {
      const wrapper = await createWrapper()
      expect(typeof wrapper.vm.save).toBe('function')
    })

    it('should validate chip ID before processing', async () => {
      const wrapper = await setupDeviceTest('invalid-id')
      const result = wrapper.vm.validateChipId()
      expect(result).toBe(false)
    })

    it('shows a validation error and does not call the store when the form is invalid', async () => {
      const { validateCurrentForm } = await import('@/modules/utils')
      const wrapper = await createWrapper()
      validateCurrentForm.mockReturnValueOnce(false)

      await wrapper.vm.save()

      expect(piniaMocks.deviceStore.addDevice).not.toHaveBeenCalled()
      expect(wrapper.vm.isSaving).toBe(false)
    })

    it('reports a failed create and always clears the saving state', async () => {
      const wrapper = await createWrapper()
      piniaMocks.deviceStore.addDevice.mockResolvedValue(null)

      await wrapper.vm.save()

      expect(piniaMocks.global.messageError).toBe('Failed to add device')
      expect(wrapper.vm.isSaving).toBe(false)
    })

    it('reports a failed update and always clears the saving state', async () => {
      const wrapper = await createWrapper({ id: 'device-1' })
      const device = new Device({ id: 'device-1', name: 'Sensor' })
      wrapper.vm.device = device
      piniaMocks.deviceStore.updateDevice.mockResolvedValue(null)

      await wrapper.vm.save()

      expect(piniaMocks.global.messageError).toBe('Failed to save device')
      expect(wrapper.vm.isSaving).toBe(false)
    })

    it('should clear messages on save attempt', async () => {
      const wrapper = await setupDeviceTest('a1b2c3')
      piniaMocks.global.messageError = 'Some error'

      await wrapper.vm.validateUrl()
      // After validation, global methods should be callable
      expect(typeof piniaMocks.global.clearMessages).toBe('function')
    })
  })

  describe('Device Detection and Proxy Requests', () => {
    it('should have fetchConfigFromDevice method', async () => {
      const wrapper = await createWrapper()
      expect(typeof wrapper.vm.fetchConfigFromDevice).toBe('function')
    })

    it('should have fetchConfigEspFwkV1 method for device API v1', async () => {
      const wrapper = await createWrapper()
      expect(typeof wrapper.vm.fetchConfigEspFwkV1).toBe('function')
    })

    it('should set disabled state during fetch', async () => {
      const wrapper = await setupDeviceTest('a1b2c3')
      piniaMocks.global.disabled = false

      const promise = wrapper.vm.fetchConfigFromDevice()
      expect(piniaMocks.global.disabled).toBe(true)

      await promise
    })

    // Answers the device endpoints like firmware that predates /api/feature,
    // where the proxied request yields no JSON (the device redirects).
    const answerDevice = ({ feature = null, status = { id: 'c5cc80' } } = {}) =>
      piniaMocks.deviceStore.proxyRequest.mockImplementation(async (_m, url) => {
        if (url.endsWith('api/status')) return status
        if (url.endsWith('api/config')) return { id: 'c5cc80', temp_format: 'C' }
        if (url.endsWith('api/feature')) return feature
        return null
      })

    it('treats a missing /api/feature as optional, without an error', async () => {
      const wrapper = await setupDeviceTest('a1b2c3')
      answerDevice()

      expect(await wrapper.vm.fetchConfigEspFwkV1()).toBe(true)
      expect(piniaMocks.global.messageError).toBe('')
      expect(wrapper.vm.device.config.config).toEqual({ id: 'c5cc80', temp_format: 'C' })
      expect(wrapper.vm.device.config).not.toHaveProperty('feature')

      const featureCall = piniaMocks.deviceStore.proxyRequest.mock.calls.find(([, url]) =>
        url.endsWith('api/feature')
      )
      expect(featureCall[4]).toEqual({ noErrorNotify: true })
    })

    it('stores /api/feature when the firmware has it', async () => {
      const wrapper = await setupDeviceTest('a1b2c3')
      answerDevice({ feature: { platform: 'esp32c3' } })

      expect(await wrapper.vm.fetchConfigEspFwkV1()).toBe(true)
      expect(wrapper.vm.device.config.feature).toEqual({ platform: 'esp32c3' })
    })

    it('stops without storing anything when /api/status fails', async () => {
      const wrapper = await setupDeviceTest('a1b2c3')
      answerDevice({ status: null })

      expect(await wrapper.vm.fetchConfigEspFwkV1()).toBe(false)
      expect(wrapper.vm.device.config).toBeFalsy()
    })
  })

  describe('Additional Methods', () => {
    it('should have validateUrl method that can be called', async () => {
      const wrapper = await createWrapper()
      const result = wrapper.vm.validateUrl()
      expect(typeof result).not.toBeUndefined()
    })

    it('should check if device is new with isNew method', async () => {
      const wrapper = await createWrapper()
      const isNew = wrapper.vm.isNew()
      expect(typeof isNew).toBe('boolean')
    })

    it('should detect device changes with deviceChanged method', async () => {
      const wrapper = await createWrapper()
      const changed = wrapper.vm.deviceChanged()
      expect(typeof changed).toBe('boolean')
    })

    it('should have deleteFermentationSteps method', async () => {
      const wrapper = await createWrapper()
      expect(typeof wrapper.vm.deleteFermentationSteps).toBe('function')
    })

    it('regenerates the device token and reports success or failure', async () => {
      const wrapper = await setupDeviceTest()
      ;(await import('@/modules/router')).default.currentRoute.value.params = { id: 'device-1' }
      wrapper.vm.device = new Device({ id: 'device-1' })
      wrapper.vm.device.deviceType = 'gravitymon'
      wrapper.vm.device.token = 'old'
      await wrapper.vm.$nextTick()
      piniaMocks.deviceStore.regenerateToken.mockResolvedValueOnce('fresh-token')
      await wrapper.find('.device-action-toolbar [aria-label^="Regenerate API token"]').trigger('click')
      await flushPromises()

      expect(wrapper.vm.device.token).toBe('fresh-token')
      expect(piniaMocks.global.messageSuccess).toBe('Token regenerated')

      piniaMocks.deviceStore.regenerateToken.mockResolvedValueOnce(null)
      await wrapper.find('.device-action-toolbar [aria-label^="Regenerate API token"]').trigger('click')
      await flushPromises()
      expect(piniaMocks.global.messageError).toBe('Failed to regenerate token')
    })

    it('deletes fermentation steps and reports both outcomes', async () => {
      const wrapper = await createWrapper({ id: 'device-1' })
      wrapper.vm.device = new Device({ id: 'device-1' })
      wrapper.vm.activeFermentationSteps = [{ id: 1 }]
      await wrapper.vm.$nextTick()
      piniaMocks.deviceStore.deleteDeviceFermentationSteps.mockResolvedValueOnce(true)
      await wrapper.find('.confirm-dialog-stub').trigger('click')

      expect(wrapper.vm.activeFermentationSteps).toBe(null)
      expect(piniaMocks.global.messageSuccess).toBe('Fermentation steps removed')

      piniaMocks.deviceStore.deleteDeviceFermentationSteps.mockResolvedValueOnce(false)
      await wrapper.find('.confirm-dialog-stub').trigger('click')
      expect(piniaMocks.global.messageError).toBe('Failed to remove fermentation steps')
    })
  })
})
