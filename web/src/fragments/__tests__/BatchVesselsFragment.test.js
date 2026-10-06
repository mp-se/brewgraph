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

// deps ../BatchVesselsFragment.vue

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import BatchVesselsFragment from '../BatchVesselsFragment.vue'

vi.mock('@/ui', async (importActual) => {
  const actual = await importActual()
  return { ...actual, logDebug: vi.fn(), logInfo: vi.fn(), logError: vi.fn() }
})

const mockVesselList = []
const mockGlobal = { disabled: false, messageError: '' }
const mockVesselStore = {
  get vesselList() { return mockVesselList },
  getVesselList: vi.fn().mockResolvedValue([]),
  listEmptyKegs: vi.fn().mockResolvedValue([]),
  addVessel: vi.fn().mockResolvedValue({ id: 'v-new' }),
  updateVessel: vi.fn().mockResolvedValue(true),
  assignBatch: vi.fn().mockResolvedValue({ id: 'keg-empty' })
}

const mockConfig = { precision: { volume: 3 } }

vi.mock('@/modules/pinia', () => ({
  get global() { return mockGlobal },
  get vesselStore() { return mockVesselStore },
  get config() { return mockConfig }
}))

vi.mock('bootstrap', () => ({
  Modal: class {
    static getInstance() { return { hide: vi.fn() } }
    show = vi.fn()
  }
}))

const BATCH_ID = 'batch-xyz-001'

const keg = (overrides = {}) => ({
  id: 'keg-1', batchId: BATCH_ID, vesselType: 'keg',
  name: 'Primary Keg', status: 'filled', totalVolume: 20, volumeRemaining: 18,
  bottleCount: null, bottlesRemaining: null, bottleVolume: null,
  ...overrides
})

const bottle = (overrides = {}) => ({
  id: 'btl-1', batchId: BATCH_ID, vesselType: 'bottles',
  name: 'Batch Bottles', status: 'filled', totalVolume: 10, volumeRemaining: 10,
  bottleCount: 30, bottlesRemaining: 28, bottleVolume: 0.33,
  ...overrides
})

function mountFragment() {
  return mount(BatchVesselsFragment, {
    props: { batchId: BATCH_ID },
    global: { stubs: { 'router-link': true, AppSelect: true, AppTextInput: { template: '<input required />' }, AppInputNumber: true } }
  })
}

describe('BatchVesselsFragment', () => {
  beforeEach(() => {
    mockVesselList.length = 0
    mockGlobal.disabled = false
    mockGlobal.messageError = ''
    vi.clearAllMocks()
    mockVesselStore.getVesselList.mockResolvedValue([])
    mockVesselStore.listEmptyKegs.mockResolvedValue([])
    mockVesselStore.addVessel.mockResolvedValue({ id: 'v-new' })
    mockVesselStore.updateVessel.mockResolvedValue(true)
    mockVesselStore.assignBatch.mockResolvedValue({ id: 'keg-empty' })
  })

  describe('Section headers', () => {
    it('renders Kegs label', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('Kegs')
    })

    it('renders Bottles label', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('Bottles')
    })

    it('renders Assign and Add buttons for kegs', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('Assign')
      expect(wrapper.text()).toContain('Add')
    })
  })

  describe('Empty state', () => {
    it('shows empty message when no kegs', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('No kegs assigned to this batch.')
    })

    it('shows empty message when no bottles', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('No bottle batches for this batch.')
    })

    it('does not render keg table when empty', () => {
      const wrapper = mountFragment()
      const tables = wrapper.findAll('table')
      expect(tables.length).toBe(0)
    })
  })

  describe('Keg list rendering', () => {
    beforeEach(() => { mockVesselList.push(keg()) })

    it('renders keg table when kegs exist', () => {
      const wrapper = mountFragment()
      expect(wrapper.findAll('table').length).toBeGreaterThanOrEqual(1)
    })

    it('displays keg name', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('Primary Keg')
    })

    it('displays keg status', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('filled')
    })

    it('displays keg volume as remaining/total', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('18.0 / 20.0 L')
    })

    it('does not show no-kegs message when kegs exist', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).not.toContain('No kegs assigned to this batch.')
    })
  })

  describe('Empty keg', () => {
    beforeEach(() => { mockVesselList.push(keg()) })

    it('labels the action so the icon is not the only affordance', () => {
      const wrapper = mountFragment()
      const button = wrapper.get('button[aria-label="Empty keg"]')
      expect(button.text()).toContain('Empty')
      expect(button.attributes('aria-label')).toBe('Empty keg')
    })

    it('detaches the keg from the batch by assigning a null batchId', async () => {
      const wrapper = mountFragment()
      await wrapper.vm.emptyKeg(keg())
      expect(mockVesselStore.assignBatch).toHaveBeenCalledExactlyOnceWith('keg-1', null)
    })

    it('refreshes the vessel list after emptying', async () => {
      const wrapper = mountFragment()
      vi.clearAllMocks()
      mockVesselStore.assignBatch.mockResolvedValue({ id: 'keg-1' })
      await wrapper.vm.emptyKeg(keg())
      expect(mockVesselStore.getVesselList).toHaveBeenCalledWith(BATCH_ID)
    })

    it('sets messageError when emptying fails', async () => {
      mockVesselStore.assignBatch.mockResolvedValue(null)
      const wrapper = mountFragment()
      await wrapper.vm.emptyKeg(keg())
      expect(mockGlobal.messageError).toBe('Failed to empty keg')
    })
  })

  describe('Bottle list rendering', () => {
    beforeEach(() => { mockVesselList.push(bottle()) })

    it('renders bottle table when bottles exist', () => {
      const wrapper = mountFragment()
      expect(wrapper.findAll('table').length).toBeGreaterThanOrEqual(1)
    })

    it('displays bottle batch name', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('Batch Bottles')
    })

    it('displays remaining/total bottle count', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('28 / 30')
    })

    it('displays bottle volume', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('0.33 L')
    })
  })

  describe('Mixed kegs and bottles', () => {
    beforeEach(() => {
      mockVesselList.push(keg(), bottle())
    })

    it('renders two tables', () => {
      const wrapper = mountFragment()
      expect(wrapper.findAll('table').length).toBe(2)
    })

    it('kegs only appear in keg table', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('Primary Keg')
    })

    it('bottles only appear in bottle table', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('Batch Bottles')
    })
  })

  describe('vesselAmount helper', () => {
    it('shows bottle count string for bottle type', () => {
      mockVesselList.push(bottle())
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('28 / 30')
    })

    it('shows — when bottlesRemaining is null', () => {
      const wrapper = mountFragment()
      const result = wrapper.vm.vesselAmount(bottle({ bottlesRemaining: null }))
      expect(result).toBe('—')
    })

    it('shows volume string for keg type', () => {
      mockVesselList.push(keg())
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('18.0 / 20.0 L')
    })
  })

  describe('Disabled state', () => {
    beforeEach(() => { mockGlobal.disabled = true })

    it('disables Assign button', () => {
      const wrapper = mountFragment()
      const assignBtn = wrapper.findAll('button').find((b) => b.text().includes('Assign'))
      expect(assignBtn.attributes('disabled')).toBeDefined()
    })

    it('disables keg Add button', () => {
      const wrapper = mountFragment()
      const addBtns = wrapper.findAll('button').filter((b) => b.text().includes('Add'))
      addBtns.forEach((b) => expect(b.attributes('disabled')).toBeDefined())
    })
  })

  describe('Assign keg availability', () => {
    it('disables Assign when no empty keg is available', async () => {
      const wrapper = mountFragment()
      await wrapper.vm.$nextTick()

      const assignButton = wrapper.findAll('button').find((b) => b.text().includes('Assign'))
      expect(assignButton.attributes('disabled')).toBeDefined()
    })

    it('enables Assign after an empty keg is loaded', async () => {
      mockVesselStore.listEmptyKegs.mockResolvedValue([keg({ id: 'empty-keg', batchId: null, status: 'empty' })])
      const wrapper = mountFragment()
      await new Promise((resolve) => setTimeout(resolve, 0))

      const assignButton = wrapper.findAll('button').find((b) => b.text().includes('Assign'))
      expect(assignButton.attributes('disabled')).toBeUndefined()
    })
  })

  describe('Add Keg modal', () => {
    it('marks the name as required and keeps Add disabled for blank names', async () => {
      const wrapper = mountFragment()
      const nameInput = wrapper.findAll('input[required]')[0]
      const addButton = wrapper.findAll('button').find((b) => b.text().includes('Add Keg'))

      expect(nameInput.attributes('required')).toBeDefined()
      expect(addButton.attributes('disabled')).toBeDefined()

      wrapper.vm.newKeg.name = '   '
      await wrapper.vm.$nextTick()
      expect(addButton.attributes('disabled')).toBeDefined()
    })

    it('does not create a keg when called with a blank name', async () => {
      const wrapper = mountFragment()
      wrapper.vm.newKeg.name = '   '

      await wrapper.vm.addKeg()

      expect(mockVesselStore.addVessel).not.toHaveBeenCalled()
    })

    it('calls addVessel with keg type on submit', async () => {
      const wrapper = mountFragment()
      wrapper.vm.newKeg.name = 'My Keg'
      wrapper.vm.newKeg.totalVolume = 19
      wrapper.vm.newKeg.fillDate = '2026-01-01'
      await wrapper.vm.addKeg()
      expect(mockVesselStore.addVessel).toHaveBeenCalledOnce()
      const arg = mockVesselStore.addVessel.mock.calls[0][0]
      expect(arg.vesselType).toBe('keg')
      expect(arg.name).toBe('My Keg')
      expect(arg.totalVolume).toBe(19)
      expect(arg.batchId).toBe(BATCH_ID)
    })

    it('sets messageError on addVessel failure', async () => {
      mockVesselStore.addVessel.mockResolvedValue(null)
      const wrapper = mountFragment()
      wrapper.vm.newKeg.name = 'My Keg'
      await wrapper.vm.addKeg()
      await wrapper.vm.$nextTick()
      expect(mockGlobal.messageError).toBe('Failed to add keg')
    })
  })

  describe('Add Bottles modal', () => {
    it('marks the name as required and keeps Add disabled for blank names', async () => {
      const wrapper = mountFragment()
      const nameInput = wrapper.findAll('input[required]')[1]
      const addButton = wrapper.findAll('button').find((b) => b.text().includes('Add Bottles'))

      expect(nameInput.attributes('required')).toBeDefined()
      expect(addButton.attributes('disabled')).toBeDefined()

      wrapper.vm.newBottles.name = '   '
      await wrapper.vm.$nextTick()
      expect(addButton.attributes('disabled')).toBeDefined()
    })

    it('does not create bottles when called with a blank name', async () => {
      const wrapper = mountFragment()
      wrapper.vm.newBottles.name = '   '

      await wrapper.vm.addBottles()

      expect(mockVesselStore.addVessel).not.toHaveBeenCalled()
    })

    it('calls addVessel with bottle type on submit', async () => {
      const wrapper = mountFragment()
      wrapper.vm.newBottles.name = 'My Bottles'
      wrapper.vm.newBottles.bottleCount = 24
      wrapper.vm.newBottles.bottleVolume = 0.5
      wrapper.vm.newBottles.fillDate = '2026-01-01'
      await wrapper.vm.addBottles()
      expect(mockVesselStore.addVessel).toHaveBeenCalledOnce()
      const arg = mockVesselStore.addVessel.mock.calls[0][0]
      expect(arg.vesselType).toBe('bottles')
      expect(arg.bottleCount).toBe(24)
      expect(arg.totalVolume).toBe(12)
      expect(arg.batchId).toBe(BATCH_ID)
    })

    it('sets messageError on addVessel failure', async () => {
      mockVesselStore.addVessel.mockResolvedValue(null)
      const wrapper = mountFragment()
      wrapper.vm.newBottles.name = 'My Bottles'
      await wrapper.vm.addBottles()
      await wrapper.vm.$nextTick()
      expect(mockGlobal.messageError).toBe('Failed to add bottle batch')
    })
  })

  describe('Assign Keg modal', () => {
    it('calls assignBatch with batchId set', async () => {
      const emptyKeg = { id: 'keg-empty', vesselType: 'keg', batchId: null, name: 'Empty Keg' }
      mockVesselStore.listEmptyKegs.mockResolvedValue([emptyKeg])
      const wrapper = mountFragment()
      await new Promise((resolve) => setTimeout(resolve, 0))
      await wrapper.vm.openAssignKegModal()
      wrapper.vm.selectedKegId = 'keg-empty'
      await wrapper.vm.assignKeg()
      expect(mockVesselStore.assignBatch).toHaveBeenCalledExactlyOnceWith('keg-empty', BATCH_ID)
    })

    it('sets messageError on assignBatch failure', async () => {
      mockVesselStore.assignBatch.mockResolvedValue(null)
      const emptyKeg = { id: 'keg-empty', vesselType: 'keg', batchId: null, name: 'Empty Keg' }
      mockVesselStore.listEmptyKegs.mockResolvedValue([emptyKeg])
      const wrapper = mountFragment()
      await new Promise((resolve) => setTimeout(resolve, 0))
      await wrapper.vm.openAssignKegModal()
      wrapper.vm.selectedKegId = 'keg-empty'
      await wrapper.vm.assignKeg()
      await wrapper.vm.$nextTick()
      expect(mockGlobal.messageError).toBe('Failed to assign keg')
    })

    it('does nothing when no keg is selected', async () => {
      const wrapper = mountFragment()
      wrapper.vm.selectedKegId = ''
      await wrapper.vm.assignKeg()
      expect(mockVesselStore.updateVessel).not.toHaveBeenCalled()
    })
  })
})
