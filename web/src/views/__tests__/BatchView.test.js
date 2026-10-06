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
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import BatchView from '../BatchView.vue'
import { Batch } from '@/modules/classes'

import routerMock from '@/modules/router'

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
    batchChanged: false
  },
  deviceStore: {
    deviceList: [],
    devices: [],
    getDevice: vi.fn(),
    getFermentationSteps: vi.fn().mockResolvedValue(''),
    deleteFermentationSteps: vi.fn().mockResolvedValue(true),
    updateDevice: vi.fn().mockResolvedValue(true)
  },
  batchStore: {
    batchList: [],
    getBatch: vi.fn(),
    addBatch: vi.fn(),
    updateBatch: vi.fn(),
    deleteFermentationSteps: vi.fn(),
    archiveBatch: vi.fn(),
    unarchiveBatch: vi.fn()
  },
  brewfatherStore: {
    getBatchList: vi.fn(),
    batches: []
  },
  configStore: {
    config: {
      brewfatherEnabled: false,
      isGravitySG: true
    }
  }
}))
const utilsMock = vi.hoisted(() => ({
  download: vi.fn(),
  roundValue: vi.fn((val) => val),
  tempToF: vi.fn((c) => (c * 9) / 5 + 32),
  tempToC: vi.fn((f) => ((f - 32) * 5) / 9)
}))
const dryHopMocks = vi.hoisted(() => ({
  persistDryHops: vi.fn()
}))

vi.mock('@/modules/router', () => ({
  default: {
    currentRoute: {
      value: {
        params: { id: 'new' },
        name: 'batch-view'
      }
    },
    push: vi.fn()
  }
}))

vi.mock('@/ui', () => ({
  logDebug: vi.fn(),
  logError: vi.fn(),
  logInfo: vi.fn()
}))
vi.mock('@/modules/utils', () => utilsMock)
vi.mock('@/modules/dryHopEditor', () => ({
  persistDryHops: dryHopMocks.persistDryHops
}))
vi.mock('@/modules/pinia', () => ({
  global: piniaMocks.global,
  deviceStore: piniaMocks.deviceStore,
  batchStore: piniaMocks.batchStore,
  brewfatherStore: piniaMocks.brewfatherStore,
  configStore: piniaMocks.configStore,
  config: piniaMocks.configStore.config,
  vesselStore: { vesselList: [], getVesselList: vi.fn().mockResolvedValue([]) },
  batchNoteStore: { notes: [], getNotes: vi.fn().mockResolvedValue([]), addNote: vi.fn(), updateNote: vi.fn(), deleteNote: vi.fn() },
  yeastStrainStore: { strains: [], load: vi.fn().mockResolvedValue(undefined), search: vi.fn(() => []) }
}))

vi.mock('@/fragments/FermentationStepFragment.vue', () => ({
  default: { name: 'FermentationStepFragment', template: '<div>FermentationStepFragment</div>', props: ['fermentationSteps'] }
}))
vi.mock('@/fragments/BatchNotesFragment.vue', () => ({
  default: { name: 'BatchNotesFragment', template: '<div>BatchNotesFragment</div>', props: ['batchId'] }
}))
vi.mock('@/fragments/BatchVesselsFragment.vue', () => ({
  default: { name: 'BatchVesselsFragment', template: '<div>BatchVesselsFragment</div>', props: ['batchId'] }
}))
vi.mock('@/fragments/BatchYeastSelectorFragment.vue', () => ({
  default: { name: 'BatchYeastSelectorFragment', template: '<div>BatchYeastSelectorFragment</div>', props: ['yeast', 'yeastProductId'] }
}))
vi.mock('@/fragments/BatchBeerXmlImportFragment.vue', () => ({
  default: { name: 'BatchBeerXmlImportFragment', template: '<div>BatchBeerXmlImportFragment</div>' }
}))

describe('BatchView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    piniaMocks.batchStore.batchList = []
    piniaMocks.batchStore.getBatch.mockResolvedValue(null)
    piniaMocks.batchStore.addBatch.mockResolvedValue(null)
    piniaMocks.batchStore.updateBatch.mockResolvedValue(false)
    piniaMocks.batchStore.archiveBatch.mockResolvedValue(null)
    piniaMocks.batchStore.unarchiveBatch.mockResolvedValue(null)
    piniaMocks.deviceStore.devices = []
    piniaMocks.deviceStore.deleteFermentationSteps.mockResolvedValue(true)
    piniaMocks.deviceStore.getFermentationSteps.mockResolvedValue('')
    piniaMocks.deviceStore.updateDevice.mockResolvedValue(true)
    dryHopMocks.persistDryHops.mockResolvedValue(true)
    piniaMocks.brewfatherStore.getBatchList.mockResolvedValue(true)
    piniaMocks.brewfatherStore.batches = []
    piniaMocks.global.messageError = ''
    piniaMocks.global.messageSuccess = ''
    piniaMocks.global.disabled = false
    piniaMocks.global.updatedBatchData = ref(0)

    // Default mock behavior for router
    routerMock.currentRoute.value.params.id = 'new'
    routerMock.push.mockClear()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  const mountWrapper = () =>
    mount(BatchView, {
      global: {
        stubs: {
          AppTextInput: true,
          AppInputNumber: true,
          AppInputDate: true,
          AppRadioGroup: true,
          AppSelect: true,
          AppCard: true,
          AppToggle: true,
          AppField: true,
          AppConfirmDialog: true,
          'router-link': true
        }
      }
    })

  describe('Rendering', () => {
    it('should render batch view container', () => {
      const wrapper = mountWrapper()
      expect(wrapper.find('.app-page').exists()).toBe(true)
    })

    it('should render page title', () => {
      const wrapper = mountWrapper()
      expect(wrapper.text()).toContain('Batch')
    })

    it('uses the editor spacing layout for form fields and section breaks', async () => {
      const wrapper = mountWrapper()
      await flushPromises()

      expect(wrapper.find('.batch-editor-layout').exists()).toBe(true)
      expect(wrapper.find('.batch-editor-form-grid').exists()).toBe(true)
      expect(wrapper.findAll('.batch-editor-section-divider')).not.toHaveLength(0)
    })
  })

  describe('Save operations', () => {
    it('keeps a disabled no-change save idle', async () => {
      const wrapper = mountWrapper()
      await flushPromises()
      expect(wrapper.vm.batchForm).toBeTruthy()
      piniaMocks.global.disabled = true
      await wrapper.vm.$nextTick()

      const saveButton = wrapper.get('button[type="submit"]')
      expect(saveButton.attributes('aria-busy')).toBe('false')
      expect(wrapper.find('.app-spinner').exists()).toBe(false)
    })

    it('shows a save spinner only while its mutation is pending', async () => {
      let finishSave
      routerMock.currentRoute.value.params.id = '123'
      const existing = new Batch({ id: '123', name: 'Existing' })
      piniaMocks.batchStore.getBatch.mockResolvedValue(existing)
      piniaMocks.batchStore.updateBatch.mockReturnValue(new Promise((resolve) => { finishSave = resolve }))
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = existing
      wrapper.vm.batchSaved = new Batch({ id: '123', name: 'Original' })

      const savePromise = wrapper.vm.save()
      await wrapper.vm.$nextTick()

      expect(wrapper.get('button[type="submit"]').attributes('aria-busy')).toBe('true')
      expect(wrapper.find('.app-spinner').exists()).toBe(true)

      finishSave(true)
      await savePromise
      expect(wrapper.find('.app-spinner').exists()).toBe(false)
    })

    it('adds new batch on save when ID is new', async () => {
      routerMock.currentRoute.value.params.id = 'new'

      const newBatch = new Batch(999, 'New')
      newBatch.id = 999
      newBatch.name = 'New'
      newBatch.fermentationSteps = '[]'
      newBatch.toJson = vi.fn().mockReturnValue({ id: 999, name: 'New', fermentationSteps: '[]' })
      piniaMocks.batchStore.addBatch.mockResolvedValue(newBatch)

      const wrapper = mountWrapper()
      await flushPromises()

      wrapper.vm.batch = new Batch(0, 'New')
      wrapper.vm.batch.fermentationSteps = '[]'
      wrapper.vm.batch.toJson = vi
        .fn()
        .mockReturnValue({ id: 0, name: 'New', fermentationSteps: '[]' })
      wrapper.vm.batchSaved = new Batch(0, 'New')
      piniaMocks.global.batchChanged = true
      routerMock.push.mockImplementation(() => {
        expect(piniaMocks.global.batchChanged).toBe(false)
      })

      await wrapper.vm.save()
      expect(piniaMocks.batchStore.addBatch).toHaveBeenCalled()
      expect(routerMock.push).toHaveBeenCalled()
    })

    it('handles addBatch failure', async () => {
      routerMock.currentRoute.value.params.id = 'new'
      piniaMocks.batchStore.addBatch.mockResolvedValue(null)

      const wrapper = mountWrapper()
      await flushPromises()

      wrapper.vm.batch = new Batch(0, 'New')
      wrapper.vm.batch.toJson = vi.fn().mockReturnValue({ id: 0, name: 'New' })
      wrapper.vm.batchSaved = new Batch(0, 'New')

      await wrapper.vm.save()
      expect(piniaMocks.global.messageError).toBe('Failed to add batch')
    })

    it('reports when the new batch is created but fermentation steps fail to persist', async () => {
      routerMock.currentRoute.value.params.id = 'new'
      const created = new Batch({ id: 'created-1', name: 'Created' })
      piniaMocks.batchStore.addBatch.mockResolvedValue(created)
      piniaMocks.deviceStore.deleteFermentationSteps.mockResolvedValue(false)
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = new Batch({ name: 'Created' })

      await wrapper.vm.save()

      expect(piniaMocks.global.messageError).toBe(
        'Batch created, but failed to save fermentation steps'
      )
      expect(routerMock.push).not.toHaveBeenCalled()
    })

    it('reports when imported dry hops fail to persist after batch creation', async () => {
      routerMock.currentRoute.value.params.id = 'new'
      const created = new Batch({ id: 'created-dry-hop', name: 'Created' })
      piniaMocks.batchStore.addBatch.mockResolvedValue(created)
      dryHopMocks.persistDryHops.mockResolvedValue(false)
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = new Batch({ name: 'Created' })
      wrapper.vm.stagedDryHops = [{ name: 'Citra', amount: 20, triggerHoursBefore: 24 }]

      await wrapper.vm.save()

      expect(dryHopMocks.persistDryHops).toHaveBeenCalledWith(created.id, wrapper.vm.stagedDryHops)
      expect(piniaMocks.global.messageError).toBe('Batch created, but failed to save dry hops')
      expect(routerMock.push).not.toHaveBeenCalled()
    })

    it('persists imported dry hops and clears the staged entries after successful creation', async () => {
      routerMock.currentRoute.value.params.id = 'new'
      const created = new Batch({ id: 'created-with-hops', name: 'Created' })
      piniaMocks.batchStore.addBatch.mockResolvedValue(created)
      dryHopMocks.persistDryHops.mockResolvedValue(true)
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = new Batch({ name: 'Created' })
      wrapper.vm.stagedDryHops = [{ name: 'Citra', amount: 20, triggerHoursBefore: 24 }]

      await wrapper.vm.save()

      expect(dryHopMocks.persistDryHops).toHaveBeenCalledWith(created.id, [
        { name: 'Citra', amount: 20, triggerHoursBefore: 24 }
      ])
      expect(wrapper.vm.stagedDryHops).toEqual([])
      expect(routerMock.push).toHaveBeenCalledWith({ name: 'batch', params: { id: created.id } })
    })

    it('reports when existing-batch fermentation steps fail to persist', async () => {
      routerMock.currentRoute.value.params.id = 'existing-steps'
      const existing = new Batch({ id: 'existing-steps', name: 'Existing' })
      piniaMocks.batchStore.getBatch.mockResolvedValue(existing)
      piniaMocks.batchStore.updateBatch.mockResolvedValue(true)
      piniaMocks.deviceStore.deleteFermentationSteps.mockResolvedValue(false)
      const wrapper = mountWrapper()
      await flushPromises()

      await wrapper.vm.save()

      expect(piniaMocks.global.messageError).toBe('Saved batch, but failed to save fermentation steps')
      expect(piniaMocks.global.messageSuccess).toBe('')
    })


    it('updates existing batch on save', async () => {
      routerMock.currentRoute.value.params.id = '123'

      const existing = new Batch(123, 'Existing')
      existing.toJson = vi.fn().mockReturnValue({ id: 123, name: 'Existing' })
      piniaMocks.batchStore.updateBatch.mockResolvedValue(true)
      piniaMocks.batchStore.getBatch.mockResolvedValue(existing)

      const wrapper = mountWrapper()
      await flushPromises()

      wrapper.vm.batch = existing
      wrapper.vm.batchSaved = new Batch(123, 'Old')

      await wrapper.vm.save()
      expect(piniaMocks.batchStore.updateBatch).toHaveBeenCalled()
      expect(piniaMocks.global.messageSuccess).toBe('Saved batch')
    })

    it('handles save failure for existing batch', async () => {
      piniaMocks.batchStore.updateBatch.mockResolvedValue(false)
      piniaMocks.batchStore.getBatch.mockResolvedValue(new Batch(1, 'E'))
      routerMock.currentRoute.value.params.id = '1'
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batchSaved = new Batch(1, 'E')
      await wrapper.vm.save()
      expect(piniaMocks.global.messageError).toBe('Failed to save batch')
    })

    it('ignores required controls in closed modals', async () => {
      const wrapper = mountWrapper()
      await flushPromises()
      const modal = document.createElement('div')
      modal.className = 'modal'
      const input = document.createElement('input')
      input.required = true
      modal.appendChild(input)
      wrapper.find('form').element.appendChild(modal)
      piniaMocks.batchStore.addBatch.mockResolvedValue(new Batch(1, 'Saved'))

      await wrapper.vm.save()

      expect(piniaMocks.batchStore.addBatch).toHaveBeenCalled()
    })

  })

  describe('Fermentation steps operations', () => {
    it('updates the batch when the fermentation-step editor emits changes', async () => {
      const wrapper = mountWrapper()
      await flushPromises()
      const editor = wrapper.findComponent({ name: 'FermentationStepFragment' })
      editor.vm.$emit('update:fermentationSteps', [{ name: 'Primary' }])
      await flushPromises()

      expect(wrapper.vm.batch.fermentationSteps).toContain('Primary')
    })

    it('loads device stepList if existing batch has fermentationChamber', async () => {
      const existing = new Batch(1, 'Existing')
      existing.fermentationChamber = 10
      piniaMocks.batchStore.getBatch.mockResolvedValue(existing)
      piniaMocks.deviceStore.getFermentationSteps.mockResolvedValue('[step1]')

      routerMock.currentRoute.value.params.id = '1'
      const wrapper = mountWrapper()
      await flushPromises()
      expect(wrapper.vm.activeFermentationSteps).toBe('[step1]')
    })
  })

  describe('Batch loading and initialization', () => {
    it('uses the cached batch when it is already in the list', async () => {
      const existing = new Batch({ id: 'cached-1', name: 'Cached batch' })
      piniaMocks.batchStore.batchList = [existing]
      piniaMocks.batchStore.getBatch.mockResolvedValue(null)
      routerMock.currentRoute.value.params.id = 'cached-1'

      const wrapper = mountWrapper()
      await flushPromises()

      expect(wrapper.vm.batch.name).toBe('Cached batch')
      expect(piniaMocks.batchStore.getBatch).not.toHaveBeenCalled()
    })

    it('handles successful batch load on mount', async () => {
      const existing = new Batch(1, 'Existing')
      piniaMocks.batchStore.getBatch.mockResolvedValue(existing)
      routerMock.currentRoute.value.params.id = '1'
      const wrapper = mountWrapper()
      await flushPromises()
      expect(wrapper.vm.batch).toEqual(existing)
    })

    it('handles failed batch load in onMounted', async () => {
      routerMock.currentRoute.value.params.id = '456'
      piniaMocks.batchStore.getBatch.mockResolvedValue(null)
      mountWrapper()
      await flushPromises()
      expect(piniaMocks.global.messageError).toContain('Failed to load batch')
    })

    it('refreshes cached batch data and fermentation steps after a batch update event', async () => {
      routerMock.currentRoute.value.params.id = 'batch-refresh'
      const original = new Batch({ id: 'batch-refresh', name: 'Original' })
      const refreshed = new Batch({ id: 'batch-refresh', name: 'Refreshed' })
      piniaMocks.batchStore.batchList = [refreshed]
      piniaMocks.batchStore.getBatch.mockResolvedValue(original)
      piniaMocks.deviceStore.getFermentationSteps.mockResolvedValue([])
      const wrapper = mountWrapper()
      await flushPromises()

      piniaMocks.deviceStore.getFermentationSteps.mockResolvedValueOnce(null)
      piniaMocks.global.updatedBatchData.value += 1
      await flushPromises()

      expect(wrapper.vm.batch.name).toBe('Refreshed')
      expect(piniaMocks.deviceStore.getFermentationSteps).toHaveBeenCalledWith('batch-refresh')
      expect(wrapper.vm.batch.fermentationSteps).toBe('')
    })
  })

  describe('Batch export', () => {
    it('downloads a JSON export for the persisted batch', async () => {
      const stored = new Batch({ id: 'batch-1', name: 'Export batch' })
      piniaMocks.batchStore.getBatch.mockResolvedValue(stored)
      routerMock.currentRoute.value.params.id = 'batch-1'
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = stored

      await wrapper.vm.exportBatchJson()

      expect(utilsMock.download).toHaveBeenCalledWith(
        expect.any(String),
        'application/json',
        'brewgraph_Export_batch.json'
      )
    })
  })

  describe('Status actions and server updates', () => {
    it('ignores status refresh when there is no batch or no server result', async () => {
      const wrapper = mountWrapper()
      await flushPromises()

      wrapper.vm.batch = null
      await wrapper.vm.reloadBatchStatus()
      expect(piniaMocks.batchStore.getBatch).not.toHaveBeenCalled()

      wrapper.vm.batch = new Batch({ id: 'batch-1', name: 'Current' })
      piniaMocks.batchStore.getBatch.mockResolvedValue(null)
      await wrapper.vm.reloadBatchStatus()
      expect(wrapper.vm.batch.name).toBe('Current')
    })

    it('does nothing for archive actions when the batch has not loaded', async () => {
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = null

      await wrapper.vm.archiveBatch()
      await wrapper.vm.unarchiveBatch()

      expect(piniaMocks.batchStore.archiveBatch).not.toHaveBeenCalled()
      expect(piniaMocks.batchStore.unarchiveBatch).not.toHaveBeenCalled()
    })

    it('refreshes server-owned status fields and saved baseline', async () => {
      const current = new Batch({ id: 'batch-1', name: 'Current', status: 'fermenting' })
      const saved = new Batch({ id: 'batch-1', name: 'Current', status: 'fermenting' })
      piniaMocks.batchStore.getBatch.mockResolvedValue({
        status: 'packaged', packageDate: '2026-01-01', ogMeasured: 1.05, fgMeasured: 1.01
      })
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = current
      wrapper.vm.batchSaved = saved

      await wrapper.vm.reloadBatchStatus()

      expect(current.status).toBe('packaged')
      expect(saved.status).toBe('packaged')
      expect(saved.packageDate).toBe('2026-01-01')
      expect(saved.ogMeasured).toBe(1.05)
      expect(saved.fgMeasured).toBe(1.01)
    })

    it.each([
      ['archiveBatch', 'archiveBatch', 'archived', 'Batch archived', 'Failed to archive batch'],
      ['unarchiveBatch', 'unarchiveBatch', 'fermenting', 'Batch un-archived', 'Failed to un-archive batch']
    ])('%s updates saved state on success and reports failure', async (_label, method, status, success, failure) => {
      const batch = new Batch({ id: 'batch-1', name: 'Current', status: 'fermenting' })
      const saved = new Batch({ id: 'batch-1', name: 'Current', status: 'fermenting' })
      const action = piniaMocks.batchStore[method]
      action.mockResolvedValue({ status })
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = batch
      wrapper.vm.batchSaved = saved

      await wrapper.vm[method]()
      expect(batch.status).toBe(status)
      expect(saved.status).toBe(status)
      expect(piniaMocks.global.messageSuccess).toBe(success)

      action.mockResolvedValue(null)
      await wrapper.vm[method]()
      expect(piniaMocks.global.messageError).toBe(failure)
    })
  })

  describe('BeerXML import application', () => {
    it('ignores imports before a batch has loaded and preserves absent values', async () => {
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = null
      wrapper.vm.applyBeerXmlImport({ name: 'Ignored' })
      expect(wrapper.vm.batch).toBeNull()

      wrapper.vm.batch = new Batch({ name: 'Existing', ibu: 10, ebc: 5, volume: 20 })
      wrapper.vm.applyBeerXmlImport({ ibu: null, ebc: null, volume: null, carbonation: null })
      expect(wrapper.vm.batch).toMatchObject({ name: 'Existing', ibu: 10, ebc: 5, volume: 20 })
    })

    it('applies present import values and leaves omitted values untouched', async () => {
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = new Batch({ name: 'Before', ibu: 10, ebc: 5, volume: 20 })

      wrapper.vm.applyBeerXmlImport({
        name: 'Imported', style: 'West Coast IPA', brewer: 'Morgan', og: 1.06, fg: 1.012,
        ibu: 23.6, ebc: 11.2, volume: 19, carbonation: 2.4,
        notes: 'notes', yeast: 'yeast', fermentationSteps: [{ name: 'Primary' }],
        dryHops: [{ name: 'Citra', amount: 20, triggerHoursBefore: 24 }]
      })

      expect(wrapper.vm.batch).toMatchObject({
        name: 'Imported', style: 'West Coast IPA', brewer: 'Morgan', og: 1.06, fg: 1.012
      })
      expect(wrapper.vm.batch.ibu).toBe(24)
      expect(wrapper.vm.batch.ebc).toBe(11)
      expect(wrapper.vm.batch.volume).toBe(19)
      expect(wrapper.vm.batch.carbonationVolumes).toBe(2.4)
      expect(wrapper.vm.batch.notes).toBe('notes')
      expect(wrapper.vm.batch.yeast).toBe('yeast')
      expect(wrapper.vm.parsedFermentationSteps).toEqual([{ name: 'Primary' }])
      expect(wrapper.vm.stagedDryHops).toHaveLength(1)
    })

    it('ignores empty and zero-valued optional BeerXML fields', async () => {
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = new Batch({ name: 'Keep', style: 'IPA', brewer: 'Brewer', og: 1.05, fg: 1.01 })
      wrapper.vm.parsedFermentationSteps = [{ name: 'Keep step' }]
      wrapper.vm.stagedDryHops = [{ name: 'Keep hop', amount: 10, triggerHoursBefore: 12 }]

      wrapper.vm.applyBeerXmlImport({
        name: '', style: '', brewer: '', og: 0, fg: 0, ibu: null, ebc: null,
        volume: null, carbonation: null, notes: '', yeast: '',
        fermentationSteps: [], dryHops: []
      })

      expect(wrapper.vm.batch).toMatchObject({ name: 'Keep', style: 'IPA', brewer: 'Brewer', og: 1.05, fg: 1.01 })
      expect(wrapper.vm.parsedFermentationSteps).toEqual([{ name: 'Keep step' }])
      expect(wrapper.vm.stagedDryHops).toEqual([{ name: 'Keep hop', amount: 10, triggerHoursBefore: 12 }])
    })
  })

  it('resolves assigned gravity, pressure and chamber devices from the device list', async () => {
    piniaMocks.deviceStore.devices = [
      { id: 'gravity-1', deviceType: 'gravitymon', token: 'g' },
      { id: 'pressure-1', deviceType: 'pressuremon', token: 'p' },
      { id: 'chamber-1', deviceType: 'chamber_controller', token: 'c' }
    ]
    const wrapper = mountWrapper()
    await flushPromises()
    wrapper.vm.batch = new Batch({
      gravityDeviceId: 'gravity-1',
      pressureDeviceId: 'pressure-1',
      chamberDeviceId: 'chamber-1'
    })

    expect(wrapper.vm.gravityDevice.token).toBe('g')
    expect(wrapper.vm.pressureDevice.token).toBe('p')
    expect(wrapper.vm.chamberDevice.token).toBe('c')
  })

  it('restores device roles from the device list when loading a batch outside the batch store', async () => {
    routerMock.currentRoute.value.params.id = 'loaded-batch'
    piniaMocks.batchStore.getBatch.mockResolvedValue(new Batch({ id: 'loaded-batch', name: 'Loaded' }))
    piniaMocks.deviceStore.devices = [
      { id: 'gravity-loaded', batchId: 'loaded-batch', batchRole: 'gravity' },
      { id: 'pressure-loaded', batchId: 'loaded-batch', batchRole: 'pressure' },
      { id: 'chamber-loaded', batchId: 'loaded-batch', batchRole: 'chamber' }
    ]

    const wrapper = mountWrapper()
    await flushPromises()

    expect(wrapper.vm.batch).toMatchObject({
      gravityDeviceId: 'gravity-loaded',
      pressureDeviceId: 'pressure-loaded',
      chamberDeviceId: 'chamber-loaded'
    })
  })

  it('reports a failed batch load when no matching batch is available', async () => {
    routerMock.currentRoute.value.params.id = 'missing-batch'
    piniaMocks.batchStore.getBatch.mockResolvedValue(null)

    const wrapper = mountWrapper()
    await flushPromises()

    expect(wrapper.vm.batch).toBeNull()
    expect(piniaMocks.global.messageError).toBe('Failed to load batch missing-batch')
  })

  describe('Device assignment synchronization', () => {
    it('unlinks changed old devices and assigns selected new devices', async () => {
      const oldDevice = { id: 'old-gravity', batchId: 'batch-old', batchRole: 'gravity' }
      const newDevice = { id: 'new-gravity' }
      piniaMocks.deviceStore.devices = [oldDevice, newDevice]
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = new Batch({ id: 'batch-1', gravityDeviceId: 'new-gravity' })
      wrapper.vm.batchSaved = new Batch({ id: 'batch-1', gravityDeviceId: 'old-gravity' })

      await wrapper.vm.syncDeviceAssignments('batch-1')

      expect(oldDevice).toMatchObject({ batchId: null, batchRole: null })
      expect(newDevice).toMatchObject({ batchId: 'batch-1', batchRole: 'gravity' })
      expect(piniaMocks.deviceStore.updateDevice).toHaveBeenCalledTimes(2)
    })
  })

  describe('Device options management', () => {
    it('updates device options with multiple device types', async () => {
      piniaMocks.deviceStore.devices = [
        { deviceType: 'gravitymon', chipId: 'g1', mdns: 'g.local', url: '', description: '' },
        { deviceType: 'pressuremon', chipId: 'p1', mdns: '', url: 'http://p', description: '' },
        { deviceType: 'chamber_controller', id: 10, mdns: '', url: 'http://c', description: 'desc' },
        { deviceType: 'gravitymon', chipId: 'g2', mdns: '', url: 'http://g2', description: '' },
        { deviceType: 'pressuremon', chipId: 'p2', mdns: '', url: '', description: 'desc' }
      ]
      const wrapper = mountWrapper()
      await flushPromises()
      expect(wrapper.vm.gravityDeviceOptions.length).toBeGreaterThan(1)
    })

    it('updates device options with empty URLs', async () => {
      piniaMocks.deviceStore.devices = [
        { deviceType: 'chamber_controller', id: 22, mdns: 'c.local', url: '', description: 'desc' }
      ]
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.updateDeviceOptions()
      expect(wrapper.vm.tempControlDeviceOptions.length).toBe(1)
    })

    it('updates device options with only MDNS entries', async () => {
      piniaMocks.deviceStore.devices = [
        { deviceType: 'gravitymon', chipId: 'g3', mdns: '', url: '', description: 'desc3' },
        { deviceType: 'pressuremon', chipId: 'p3', mdns: '', url: '', description: 'desc3' }
      ]
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.updateDeviceOptions()
      expect(wrapper.vm.gravityDeviceOptions.length).toBeGreaterThan(1)
    })
  })

  describe('Brewfather integration', () => {
    // The lookup-by-id-in-the-store step now lives in BatchBrewfatherLinkFragment
    // (see its own test file); BatchView only receives the already-matched batch
    // and applies it, mirroring applyBeerXmlImport's shape.
    it('updates batch from Brewfather match', async () => {
      const b1 = new Batch(1, 'B1')
      const match = {
        brewfatherId: 'bf1',
        name: 'BF Name',
        brewDate: '2023',
        brewer: 'M',
        style: 'S',
        ebc: 1,
        abv: 5,
        ibu: 30,
        og: 1.05,
        fg: 1.01,
        fermentationSteps: '[]',
        dryHops: [{ name: 'Citra', amount: 25, triggerHoursBefore: 12 }]
      }
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = b1
      wrapper.vm.applyBrewfatherLink(match)
      expect(wrapper.vm.batch.name).toBe('BF Name')
      expect(wrapper.vm.stagedDryHops).toEqual([
        { name: 'Citra', amount: 25, triggerHoursBefore: 12 }
      ])
    })

    it('clears the Brewfather link', async () => {
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = new Batch(1, 'B1')
      wrapper.vm.batch.brewfatherBatchId = 'bf1'
      wrapper.vm.clearBrewfatherLink()
      expect(wrapper.vm.batch.brewfatherBatchId).toBe('')
    })

    it('handles brewfatherStore.getBatchList failure', async () => {
      piniaMocks.brewfatherStore.getBatchList.mockResolvedValue(false)
      const wrapper = mountWrapper()
      await flushPromises()
      // Should handle gracefully
      expect(wrapper.exists()).toBe(true)
    })
  })

  describe('Batch state tracking', () => {
    it('detects batch changes when batch differs from saved', async () => {
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = new Batch({ id: 1, name: 'Updated' })
      wrapper.vm.batchSaved = new Batch({ id: 1, name: 'Original' })
      expect(wrapper.vm.batchChanged()).toBe(true)
    })

    it('returns false when batch is null', async () => {
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = null
      expect(wrapper.vm.batchChanged()).toBe(false)
    })

    it('handles fermentationChamber and fermentationSteps interaction', async () => {
      const wrapper = mountWrapper()
      await flushPromises()
      wrapper.vm.batch = new Batch(1, 'Test')
      wrapper.vm.batch.fermentationChamber = 1
      wrapper.vm.batch.fermentationSteps = '[]'
      await flushPromises()
      expect(wrapper.vm.batch.fermentationChamber).toBe(1)
    })
  })
})
