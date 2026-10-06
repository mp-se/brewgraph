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

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import BackupView from '../BackupView.vue'
import { nextTick } from 'vue'

const mockStores = vi.hoisted(() => ({
  batch: {
    getBatch: vi.fn(),
    getBatchList: vi.fn(),
    batchList: []
  },
  device: {
    getDeviceList: vi.fn(),
    deviceList: []
  },
  tap: {
    getTapList: vi.fn()
  },
  vessel: {
    getVesselList: vi.fn()
  },
  global: {
    disabled: false,
    acquireBusy() {
      this.disabled = true
      let released = false
      return () => { if (!released) { released = true; this.disabled = false } }
    },
    restoreInProgress: false,
    messageError: '',
    messageWarning: '',
    messageSuccess: '',
    baseURL: 'http://localhost/',
    apiURL: 'http://localhost/api/',
    fetchTimout: 5000,
    token: 'test-token',
    $subscribe: vi.fn(),
    $patch: vi.fn(),
    clearMessages: vi.fn()
  }
}))

vi.mock('@/modules/pinia', () => ({
  batchStore: mockStores.batch,
  deviceStore: mockStores.device,
  tapStore: mockStores.tap,
  vesselStore: mockStores.vessel,
  global: mockStores.global,
  default: {}
}))

vi.mock('@/ui', () => ({
  logDebug: vi.fn(),
  logError: vi.fn(),
  logInfo: vi.fn()
}))

vi.mock('@/modules/utils', () => ({
  download: vi.fn()
}))

vi.mock('@/modules/backup', () => ({
  createBrewGraphBackup: vi.fn(),
  processBrewGraphRestore: vi.fn(),
  processBrewLoggerRestore: vi.fn()
}))

global.fetch = vi.fn()

describe('BackupView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockStores.global.disabled = false
    mockStores.global.restoreInProgress = false
    // Reset every channel: the mocked store's clearMessages() is a spy, so state
    // written by one test would otherwise leak into the next.
    mockStores.global.messageError = ''
    mockStores.global.messageWarning = ''
    mockStores.global.messageSuccess = ''
    mockStores.global.messageInfo = ''
    global.fetch.mockResolvedValue({ ok: true, json: async () => [] })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  const mountWrapper = async () => {
    const wrapper = mount(BackupView, {
      global: {
        stubs: {
          AppProgress: true,
          AppConfirmDialog: {
            props: ['id', 'callback'],
            template:
              '<button type="button" :id="id" hidden style="display:none" @click="callback(true)"></button>'
          }
        }
      }
    })
    await nextTick()
    return wrapper
  }

  const stubFileReaderResult = (result) => {
    const mockReader = {
      readAsText: vi.fn(),
      addEventListener: vi.fn((_, cb) => {
        cb({ target: { result } })
      })
    }
    vi.stubGlobal(
      'FileReader',
      vi.fn(function () {
        return mockReader
      })
    )
    return mockReader
  }

  it('renders backup and restore sections', async () => {
    const wrapper = await mountWrapper()
    expect(wrapper.text()).toContain('Backup & Restore')
    expect(wrapper.text()).toContain('Create backup')
    expect(wrapper.text()).toContain('Restore')
  })

  it('shows an outlined file picker and enables Restore for an accepted backup file', async () => {
    const wrapper = await mountWrapper()
    const filePicker = wrapper.find('input[type="file"]')

    expect(filePicker.exists()).toBe(true)
    expect(filePicker.isVisible()).toBe(true)
    expect(filePicker.attributes('accept')).toBe('.txt,.json')
    expect(wrapper.find('.backup-restore-form > .row').exists()).toBe(true)
    expect(wrapper.find('label[for="restore-file"]').text()).toBe('Backup file')
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined()

    Object.defineProperty(filePicker.element, 'files', {
      configurable: true,
      value: [new File(['{}'], 'test.json', { type: 'application/json' })]
    })
    await filePicker.trigger('change')
    expect(wrapper.vm.fileSelected).toBe(true)
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeUndefined()
  })

  it('does not enable Restore for a file with an unsupported extension', async () => {
    const wrapper = await mountWrapper()
    wrapper.vm.restoreFile = new File(['{}'], 'backup.csv')
    await nextTick()

    expect(wrapper.vm.fileSelected).toBe(false)
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined()
  })

  it('previews the recognized format and handles malformed preview data', async () => {
    const wrapper = await mountWrapper()
    stubFileReaderResult(JSON.stringify({ source: 'brewgraph', schemaVersion: '1', mode: 'backup' }))
    wrapper.vm.restoreFile = new File(['{}'], 'backup.json')
    await flushPromises()

    expect(wrapper.vm.detectedFormat).toContain('BrewGraph')

    stubFileReaderResult('{ invalid json')
    wrapper.vm.restoreFile = new File(['{ invalid json'], 'broken.json')
    await flushPromises()

    expect(wrapper.vm.detectedFormat).toBe('Unknown (parse error)')
  })

  it('does not show Restore loading until a restore is running', async () => {
    const wrapper = await mountWrapper()

    expect(wrapper.find('.app-spinner--small').exists()).toBe(false)
    wrapper.vm.restoreInProgress = true
    await nextTick()
    expect(wrapper.find('.app-spinner--small').exists()).toBe(true)
  })

  it('finishes restore cleanup and resets progress after its feedback delay', async () => {
    const wrapper = await mountWrapper()
    const releaseBusy = vi.fn()
    const timeoutSpy = vi.spyOn(globalThis, 'setTimeout').mockImplementation((callback) => {
      callback()
      return 1
    })
    wrapper.vm.restoreProgress = 72
    wrapper.vm.restoreInProgress = true
    mockStores.global.restoreInProgress = true
    wrapper.vm.restoreFile = new File(['{}'], 'backup.json')

    wrapper.vm.finishRestore(releaseBusy)
    await nextTick()

    expect(releaseBusy).toHaveBeenCalledOnce()
    expect(wrapper.vm.restoreInProgress).toBe(false)
    expect(wrapper.vm.restoreFile).toBe(null)
    expect(wrapper.vm.restoreProgress).toBe(0)
    expect(mockStores.global.restoreInProgress).toBe(false)
    timeoutSpy.mockRestore()
  })

  it('updates only the mounted restore progress control during a restore', async () => {
    const wrapper = await mountWrapper()
    wrapper.vm.restoreInProgress = true
    mockStores.global.restoreInProgress = true
    const form = wrapper.get('.backup-restore-form').element
    const deps = wrapper.vm.buildRestoreDeps({ schemaVersion: '1', devices: [{}, {}] })

    deps.onProgress()
    deps.onProgress()
    await nextTick()

    expect(wrapper.get('.backup-restore-form').element).toBe(form)
    expect(wrapper.findComponent({ name: 'AppProgress' }).exists()).toBe(true)
    expect(mockStores.global.disabled).toBe(false)
  })

  it('wires the backup button, progress callback, and restore dependency refreshes', async () => {
    const { createBrewGraphBackup } = await import('@/modules/backup')
    createBrewGraphBackup.mockImplementation(async ({ onProgress }) => {
      onProgress()
      return { devices: [], batches: [], taps: [], vessels: [] }
    })
    global.fetch.mockResolvedValue({ ok: true, json: async () => [{ id: 'batch-1' }] })
    const wrapper = await mountWrapper()

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(createBrewGraphBackup).toHaveBeenCalledOnce()
    expect(mockStores.global.disabled).toBe(false)

    const deps = wrapper.vm.buildRestoreDeps({ meta: { software: 'BrewGraph' }, batches: [{}] })
    await deps.refreshDevices()
    await deps.refreshBatches()
    await deps.refreshTaps()
    await deps.refreshVessels()
    expect(mockStores.device.getDeviceList).toHaveBeenCalledOnce()
    expect(mockStores.batch.getBatchList).toHaveBeenCalledOnce()
    expect(mockStores.tap.getTapList).toHaveBeenCalledOnce()
    expect(mockStores.vessel.getVesselList).toHaveBeenCalledOnce()
  })

  it('createBackup calls createBrewGraphBackup and triggers download on success', async () => {
    const { createBrewGraphBackup } = await import('@/modules/backup')
    const { download } = await import('@/modules/utils')
    createBrewGraphBackup.mockResolvedValue({
      meta: { version: '2.0' },
      devices: [],
      batches: [],
      taps: [],
      vessels: []
    })
    global.fetch.mockResolvedValue({ ok: true, json: async () => [{ id: '1' }] })

    const wrapper = await mountWrapper()
    await wrapper.vm.createBackup()
    await flushPromises()

    expect(createBrewGraphBackup).toHaveBeenCalled()
    expect(download).toHaveBeenCalled()
  })

  it('createBackup shows error when batch fetch fails', async () => {
    global.fetch.mockResolvedValue({ ok: false, status: 500 })
    const wrapper = await mountWrapper()
    await wrapper.vm.createBackup()
    await flushPromises()
    expect(mockStores.global.messageError).toBe('Failed to fetch batches')
  })

  it('createBackup handles a rejected batch request and always releases busy state', async () => {
    global.fetch.mockRejectedValue(new Error('network unavailable'))
    const wrapper = await mountWrapper()
    await wrapper.vm.createBackup()

    expect(mockStores.global.messageError).toBe('Failed to fetch batches')
    expect(mockStores.global.disabled).toBe(false)
    expect(wrapper.vm.backupProgress).toBe(-1)
  })

  it('createBackup reports thrown errors from the backup writer', async () => {
    const { createBrewGraphBackup } = await import('@/modules/backup')
    createBrewGraphBackup.mockRejectedValue(new Error('disk full'))
    global.fetch.mockResolvedValue({ ok: true, json: async () => [] })
    const wrapper = await mountWrapper()
    await wrapper.vm.createBackup()

    expect(mockStores.global.messageError).toBe('Failed to create backup: disk full')
  })

  it('createBackup shows error when createBrewGraphBackup returns null', async () => {
    const { createBrewGraphBackup } = await import('@/modules/backup')
    createBrewGraphBackup.mockResolvedValue(null)
    global.fetch.mockResolvedValue({ ok: true, json: async () => [] })

    const wrapper = await mountWrapper()
    await wrapper.vm.createBackup()
    await flushPromises()
    expect(mockStores.global.messageError).toBe('Failed to create backup')
  })

  it('restore shows error when no file selected', async () => {
    const wrapper = await mountWrapper()
    await wrapper.vm.restore()
    expect(mockStores.global.messageError).toBe('You need to select a file to restore data from')
  })

  it('performRestore refuses to read when no valid file is selected', async () => {
    const wrapper = await mountWrapper()
    await wrapper.vm.performRestore()

    expect(mockStores.global.messageError).toBe('You need to select a file to restore data from')
    expect(mockStores.global.disabled).toBe(false)
  })

  it('restore opens the confirmation dialog instead of restoring immediately', async () => {
    const { processBrewGraphRestore } = await import('@/modules/backup')
    const clickSpy = vi.fn()
    vi.spyOn(document, 'getElementById').mockReturnValue({ click: clickSpy })

    const wrapper = await mountWrapper()
    wrapper.vm.restoreFile = new File([''], 'backup.json')
    await wrapper.vm.restore()

    expect(document.getElementById).toHaveBeenCalledWith('confirmRestore')
    expect(clickSpy).toHaveBeenCalled()
    // Nothing is read or restored until the dialog confirms.
    expect(processBrewGraphRestore).not.toHaveBeenCalled()
  })

  it('confirmRestoreCallback(false) leaves existing data untouched', async () => {
    const { processBrewGraphRestore, processBrewLoggerRestore } = await import('@/modules/backup')
    const wrapper = await mountWrapper()
    wrapper.vm.restoreFile = new File([''], 'backup.json')
    await wrapper.vm.confirmRestoreCallback(false)

    expect(processBrewGraphRestore).not.toHaveBeenCalled()
    expect(processBrewLoggerRestore).not.toHaveBeenCalled()
  })

  it('restore dispatches to processBrewGraphRestore for a v1 backup document', async () => {
    const { processBrewGraphRestore } = await import('@/modules/backup')
    processBrewGraphRestore.mockResolvedValue(undefined)
    mockStores.device.getDeviceList.mockResolvedValue(true)
    mockStores.batch.getBatchList.mockResolvedValue(true)
    mockStores.tap.getTapList.mockResolvedValue([])
    mockStores.vessel.getVesselList.mockResolvedValue([])

    const backupData = {
      schemaVersion: '1',
      source: 'oss',
      mode: 'backup',
      settings: {},
      devices: [],
      batches: [],
      taps: [],
      vessels: []
    }
    const wrapper = await mountWrapper()
    stubFileReaderResult(JSON.stringify(backupData))

    wrapper.vm.restoreFile = new File([''], 'backup.json')
    await wrapper.vm.performRestore()
    await flushPromises()

    expect(processBrewGraphRestore).toHaveBeenCalledWith(backupData, expect.any(Object))
  })

  it('restore refuses an ml export rather than half-restoring from it', async () => {
    const { processBrewGraphRestore } = await import('@/modules/backup')
    processBrewGraphRestore.mockResolvedValue(undefined)
    mockStores.device.getDeviceList.mockResolvedValue(true)
    mockStores.batch.getBatchList.mockResolvedValue(true)
    mockStores.tap.getTapList.mockResolvedValue([])
    mockStores.vessel.getVesselList.mockResolvedValue([])

    // An ml/archive document records what was measured, not what was stored:
    // no ids, no device configuration, no vessels or taps.
    const backupData = {
      schemaVersion: '1',
      source: 'brewgraph',
      mode: 'ml',
      settings: {},
      devices: [],
      batches: []
    }
    const wrapper = await mountWrapper()
    stubFileReaderResult(JSON.stringify(backupData))

    wrapper.vm.restoreFile = new File([''], 'backup.json')
    await wrapper.vm.performRestore()
    await flushPromises()

    expect(processBrewGraphRestore).not.toHaveBeenCalled()
    expect(mockStores.global.messageError).toContain('not a backup')
  })

  it('restore dispatches to processBrewLoggerRestore for BrewLogger format', async () => {
    const { processBrewLoggerRestore } = await import('@/modules/backup')
    processBrewLoggerRestore.mockResolvedValue(undefined)
    mockStores.device.getDeviceList.mockResolvedValue(true)
    mockStores.batch.getBatchList.mockResolvedValue(true)

    const backupData = {
      meta: { software: 'BrewLogger', version: '0.8' },
      devices: [],
      batches: [],
      pressure: [],
      pour: []
    }
    const wrapper = await mountWrapper()
    stubFileReaderResult(JSON.stringify(backupData))

    wrapper.vm.restoreFile = new File([''], 'brewlogger.txt')
    await wrapper.vm.performRestore()
    await flushPromises()

    expect(processBrewLoggerRestore).toHaveBeenCalledWith(backupData, expect.any(Object))
  })

  it('restore shows error for unknown software format', async () => {
    const backupData = { meta: { software: 'SomethingElse', version: '1.0' } }
    const wrapper = await mountWrapper()
    stubFileReaderResult(JSON.stringify(backupData))

    wrapper.vm.restoreFile = new File([''], 'unknown.json')
    await wrapper.vm.performRestore()
    await flushPromises()

    expect(mockStores.global.messageError).toBe('Unknown format, unable to process')
  })

  it('restore explains that the retired 2.0 container is no longer supported', async () => {
    const backupData = { meta: { software: 'BrewGraph', version: '99.9' } }
    const wrapper = await mountWrapper()
    stubFileReaderResult(JSON.stringify(backupData))

    wrapper.vm.restoreFile = new File([''], 'backup.json')
    await wrapper.vm.performRestore()
    await flushPromises()

    expect(mockStores.global.messageError).toContain('no longer supported')
  })

  it('reports malformed restore contents and releases the busy state', async () => {
    const wrapper = await mountWrapper()
    stubFileReaderResult('{ invalid json')
    wrapper.vm.restoreFile = new File(['{ invalid json'], 'broken.json')
    await wrapper.vm.performRestore()
    await flushPromises()

    expect(mockStores.global.messageError).toBe('Unable to parse backup file.')
    expect(mockStores.global.disabled).toBe(false)
    expect(mockStores.global.restoreInProgress).toBe(false)
  })

  it('runRestore warns instead of claiming success when entities failed', async () => {
    /*
     * The error must name what was lost — a restore where individual POST
     * failures do not throw could otherwise report "Restore successful" even
     * when every entity was rejected, giving the user no reason to look.
     */
    mockStores.device.getDeviceList.mockResolvedValue(true)
    mockStores.batch.getBatchList.mockResolvedValue(true)
    mockStores.tap.getTapList.mockResolvedValue([])
    mockStores.vessel.getVesselList.mockResolvedValue([])

    const wrapper = await mountWrapper()
    await wrapper.vm.runRestore(async () => ({
      devices: { restored: 0, failed: 17 },
      batches: { restored: 38, failed: 0 },
      taps: { restored: 0, failed: 0 },
      vessels: { restored: 0, failed: 0 }
    }))
    await flushPromises()

    expect(mockStores.global.messageSuccess).toBe('')
    expect(mockStores.global.messageError).toContain('17 of 17 devices')
    expect(mockStores.global.messageError).not.toContain('batch')
  })

  it('runRestore lists every failing category, singular where appropriate', async () => {
    mockStores.device.getDeviceList.mockResolvedValue(true)
    mockStores.batch.getBatchList.mockResolvedValue(true)
    mockStores.tap.getTapList.mockResolvedValue([])
    mockStores.vessel.getVesselList.mockResolvedValue([])

    const wrapper = await mountWrapper()
    await wrapper.vm.runRestore(async () => ({
      devices: { restored: 0, failed: 0 },
      batches: { restored: 5, failed: 1 },
      taps: { restored: 0, failed: 0 },
      vessels: { restored: 2, failed: 3 }
    }))
    await flushPromises()

    expect(mockStores.global.messageError).toContain('1 of 6 batches')
    expect(mockStores.global.messageError).toContain('3 of 5 vessels')
  })

  it('runRestore keeps the noun singular when there was only one of them', async () => {
    // The noun agrees with the total, not the failure count — "1 of 17 devices"
    // reads correctly, "1 of 17 device" does not.
    mockStores.device.getDeviceList.mockResolvedValue(true)
    mockStores.batch.getBatchList.mockResolvedValue(true)
    mockStores.tap.getTapList.mockResolvedValue([])
    mockStores.vessel.getVesselList.mockResolvedValue([])

    const wrapper = await mountWrapper()
    await wrapper.vm.runRestore(async () => ({
      devices: { restored: 0, failed: 0 },
      batches: { restored: 0, failed: 0 },
      taps: { restored: 0, failed: 1 },
      vessels: { restored: 0, failed: 0 }
    }))
    await flushPromises()

    expect(mockStores.global.messageError).toContain('1 of 1 tap.')
  })

  it('runRestore still reports success when a report shows no failures', async () => {
    mockStores.device.getDeviceList.mockResolvedValue(true)
    mockStores.batch.getBatchList.mockResolvedValue(true)
    mockStores.tap.getTapList.mockResolvedValue([])
    mockStores.vessel.getVesselList.mockResolvedValue([])

    const wrapper = await mountWrapper()
    await wrapper.vm.runRestore(async () => ({
      devices: { restored: 3, failed: 0 },
      batches: { restored: 4, failed: 0 },
      taps: { restored: 1, failed: 0 },
      vessels: { restored: 2, failed: 0 }
    }))
    await flushPromises()

    expect(mockStores.global.messageSuccess).toBe('Restore successful')
    expect(mockStores.global.messageError).toBe('')
  })

  it('runRestore sets messageSuccess on success', async () => {
    mockStores.device.getDeviceList.mockResolvedValue(true)
    mockStores.batch.getBatchList.mockResolvedValue(true)
    mockStores.tap.getTapList.mockResolvedValue([])
    mockStores.vessel.getVesselList.mockResolvedValue([])

    const wrapper = await mountWrapper()
    await wrapper.vm.runRestore(async () => {})
    await flushPromises()

    expect(mockStores.global.messageSuccess).toBe('Restore successful')
  })

  it('runRestore sets messageError on failure', async () => {
    const wrapper = await mountWrapper()
    await wrapper.vm.runRestore(async () => {
      throw new Error('boom')
    })
    await flushPromises()

    expect(mockStores.global.messageError).toBe('Restore failed: boom')
  })

  it('runRestore names what was rejected and why, not a pointer to the console', async () => {
    mockStores.device.getDeviceList.mockResolvedValue(true)
    mockStores.batch.getBatchList.mockResolvedValue(true)
    mockStores.tap.getTapList.mockResolvedValue([])
    mockStores.vessel.getVesselList.mockResolvedValue([])

    const wrapper = await mountWrapper()
    await wrapper.vm.runRestore(async () => ({
      devices: { restored: 0, failed: 0 },
      batches: { restored: 0, failed: 1 },
      taps: { restored: 0, failed: 0 },
      vessels: { restored: 0, failed: 0 },
      problems: ['batch "IPA": the server rejected its data as invalid']
    }))
    await flushPromises()

    const msg = mockStores.global.messageError
    expect(msg).toContain('1 of 1 batch')
    expect(msg).toContain('Batch "IPA": the server rejected its data as invalid.')
    expect(msg).toContain('API server log')
    expect(msg).not.toContain('console')
  })

  it('runRestore reports problems even when nothing was lost', async () => {
    const wrapper = await mountWrapper()
    await wrapper.vm.runRestore(async () => ({
      batches: { restored: 1, failed: 0 },
      problems: ['archiving batch "IPA" (it was restored as fermenting): server error']
    }))
    await flushPromises()

    expect(mockStores.global.messageSuccess).toBe('')
    expect(mockStores.global.messageError).toBe(
      'Restore incomplete. Archiving batch "IPA" (it was restored as fermenting): server error.'
    )
  })

  it('runRestore caps the listed problems', async () => {
    const wrapper = await mountWrapper()
    await wrapper.vm.runRestore(async () => ({
      batches: { restored: 0, failed: 8 },
      problems: Array.from({ length: 8 }, (_, i) => `batch "B${i}": server error`)
    }))
    await flushPromises()

    const msg = mockStores.global.messageError
    expect(msg).toContain('Batch "B4"')
    expect(msg).not.toContain('Batch "B5"')
    expect(msg).toContain('…and 3 more.')
  })
})
