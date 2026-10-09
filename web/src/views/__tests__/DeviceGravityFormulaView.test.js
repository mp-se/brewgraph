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
import { mount, flushPromises } from '@vue/test-utils'
import DeviceGravityFormulaView from '../DeviceGravityFormulaView.vue'
import GravityFormulaEditor from '@/components/device/GravityFormulaEditor.vue'
import { Device } from '@/modules/classes'

const mocks = vi.hoisted(() => ({
  global: {
    disabled: false,
    deviceChanged: false,
    messageSuccess: '',
    messageError: '',
    clearMessages: vi.fn()
  },
  deviceStore: { deviceList: [], getDevice: vi.fn(), updateDevice: vi.fn() },
  config: { gravityFormat: 'SG', temperatureFormat: 'C' },
  router: { currentRoute: { value: { params: { id: 'device-1' } } }, replace: vi.fn(), push: vi.fn() }
}))

vi.mock('@/modules/pinia', () => ({
  global: mocks.global,
  deviceStore: mocks.deviceStore,
  config: mocks.config,
}))
vi.mock('@/modules/router', () => ({ default: mocks.router }))

const editorActions = vi.hoisted(() => ({ openImport: vi.fn(), exportProfile: vi.fn() }))
const stubs = {
  AppPageHeader: true,
  GravityFormulaEditor: true,
  'router-link': { props: ['to'], template: '<a class="router-link-stub"><slot /></a>' }
}

const gravityDevice = (type = 'ispindel') =>
  new Device({ id: 'device-1', name: 'Sensor', deviceType: type, gravityFormula: 'tilt' })

const mountView = async () => {
  const wrapper = mount(DeviceGravityFormulaView, {
    global: { stubs: { ...stubs, AppButton: false } }
  })
  await flushPromises()
  return wrapper
}

describe('DeviceGravityFormulaView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.global.deviceChanged = false
    mocks.global.messageSuccess = ''
    mocks.global.messageError = ''
    mocks.deviceStore.deviceList = []
  })

  it('opens a stored gravity device with the latest angle and no unsaved state', async () => {
    mocks.deviceStore.deviceList = [gravityDevice()]
    const wrapper = await mountView()

    const editor = wrapper.findComponent(GravityFormulaEditor)
    expect(editor.exists()).toBe(true)
    expect(editor.props('formula')).toBe('tilt')
    expect(wrapper.vm.changed).toBe(false)
    expect(mocks.router.replace).not.toHaveBeenCalled()
  })

  it('places import and export as buttons that call the editor', async () => {
    mocks.deviceStore.deviceList = [gravityDevice()]
    const wrapper = await mountView()
    wrapper.vm.editor = editorActions
    await wrapper.get('[data-testid="gravity-formula-import"]').trigger('click')
    await wrapper.get('[data-testid="gravity-formula-export"]').trigger('click')
    expect(editorActions.openImport).toHaveBeenCalledTimes(1)
    expect(editorActions.exportProfile).toHaveBeenCalledTimes(1)
  })

  it('loads a device that is not in the list from the API', async () => {
    mocks.deviceStore.getDevice.mockResolvedValue(gravityDevice('gravitymon'))
    const wrapper = await mountView()
    expect(mocks.deviceStore.getDevice).toHaveBeenCalledWith('device-1')
    expect(wrapper.findComponent(GravityFormulaEditor).exists()).toBe(true)
  })

  it('redirects to the device when it cannot carry a formula, and to the list when it is unknown', async () => {
    mocks.deviceStore.deviceList = [gravityDevice('kegmon')]
    await mountView()
    expect(mocks.router.replace).toHaveBeenCalledWith({ name: 'device', params: { id: 'device-1' } })

    mocks.router.replace.mockClear()
    mocks.deviceStore.deviceList = []
    mocks.deviceStore.getDevice.mockResolvedValue(null)
    await mountView()
    expect(mocks.router.replace).toHaveBeenCalledWith({ name: 'device-list' })
  })

  it('tracks edits, blocks saving while invalid or editing, and saves only through the device update', async () => {
    mocks.deviceStore.deviceList = [gravityDevice()]
    const saved = gravityDevice()
    saved.gravityFormula = 'tilt*2'
    mocks.deviceStore.updateDevice.mockResolvedValue(saved)
    const wrapper = await mountView()
    const editor = wrapper.findComponent(GravityFormulaEditor)

    editor.vm.$emit('update:formula', 'tilt*2')
    editor.vm.$emit('update:unit', 'plato')
    editor.vm.$emit('update:points', [{ angle: 30, gravity: 1.01 }])
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.changed).toBe(true)
    expect(mocks.global.deviceChanged).toBe(true)

    editor.vm.$emit('valid', false)
    await wrapper.vm.save()
    expect(mocks.deviceStore.updateDevice).not.toHaveBeenCalled()
    editor.vm.$emit('valid', true)
    editor.vm.$emit('editing', true)
    await wrapper.vm.save()
    expect(mocks.deviceStore.updateDevice).not.toHaveBeenCalled()

    editor.vm.$emit('editing', false)
    await wrapper.vm.save()
    expect(mocks.deviceStore.updateDevice).toHaveBeenCalledTimes(1)
    expect(mocks.global.messageSuccess).toBe('Gravity formula saved')
    expect(wrapper.vm.changed).toBe(false)
    expect(mocks.global.deviceChanged).toBe(false)
  })

  it('reports a failed save and keeps the edits', async () => {
    mocks.deviceStore.deviceList = [gravityDevice()]
    mocks.deviceStore.updateDevice.mockResolvedValue(null)
    const wrapper = await mountView()
    wrapper.findComponent(GravityFormulaEditor).vm.$emit('update:formula', 'tilt*3')
    await wrapper.vm.$nextTick()
    await wrapper.vm.save()
    expect(mocks.global.messageError).toBe('Failed to save the gravity formula')
    expect(wrapper.vm.changed).toBe(true)
  })

  it('clears the unsaved flag when it is left', async () => {
    mocks.deviceStore.deviceList = [gravityDevice()]
    const wrapper = await mountView()
    wrapper.findComponent(GravityFormulaEditor).vm.$emit('update:formula', 'tilt*3')
    await wrapper.vm.$nextTick()
    expect(mocks.global.deviceChanged).toBe(true)
    wrapper.unmount()
    expect(mocks.global.deviceChanged).toBe(false)
  })
})
