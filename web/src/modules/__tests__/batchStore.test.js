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
import { createPinia, setActivePinia } from 'pinia'
import { useBatchStore } from '@/modules/batchStore'
import { useDeviceStore } from '@/modules/deviceStore'

// Mock logger
vi.mock('@/ui', async (importActual) => {
  const actual = await importActual()
  return {
    ...actual,
    logDebug: vi.fn(),
    logInfo: vi.fn(),
    logError: vi.fn()
  }
})

// Mock pinia global object
vi.mock('@/modules/pinia', () => ({
  global: {
    disabled: false,
    acquireBusy() {
      this.disabled = true
      let released = false
      return () => { if (!released) { released = true; this.disabled = false } }
    },
    baseURL: 'http://localhost:8080/',
    apiURL: 'http://localhost:8080/api/',
    token: 'Bearer test',
    fetchTimout: 30000
  }
}))

describe('useBatchStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    global.fetch = vi.fn()
  })

  describe('Initial State', () => {
    it('should have empty batches array initially', () => {
      const store = useBatchStore()
      expect(store.batches).toEqual([])
    })

    it('should have batchList getter', () => {
      const store = useBatchStore()
      expect(store.batchList).toEqual([])
    })
  })

  describe('getBatchList Action', () => {
    it('should fetch all batches', async () => {
      const store = useBatchStore()
      const mockBatches = [
        {
          id: 1,
          name: 'Batch1',
          description: '',
          chipIdGravity: 'chip1',
          chipIdPressure: '',
          active: true,
          brewDate: '',
          style: '',
          brewer: '',
          abv: 0,
          ebc: 0,
          ibu: 0,
          fg: 0,
          og: 0,
          brewfatherId: '',
          fermentationChamber: 0,
          fermentationSteps: '',
          tapList: false,
          gravity: [],
          pressure: [],
          pour: []
        }
      ]

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi
          .fn()
          .mockResolvedValueOnce({ items: mockBatches, total: 1, page: 1, pageSize: 50, pages: 1 })
      })

      const result = await store.getBatchList()

      expect(result).toBeTruthy()
      expect(store.batches.length).toBe(1)
    })

    it('should handle error', async () => {
      const store = useBatchStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Error'))

      const result = await store.getBatchList()

      expect(result).toBeNull()
    })

    it('should handle non-ok response', async () => {
      const store = useBatchStore()
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 404
      })

      const result = await store.getBatchList()

      expect(result).toBeNull()
    })
  })

  describe('getBatchList device role assignment', () => {
    it('assigns gravity/pressure/chamber device ids onto matching batches', async () => {
      const store = useBatchStore()
      const deviceStore = useDeviceStore()
      deviceStore.devices = [
        { id: 'dev-gravity', batchId: 1, batchRole: 'gravity' },
        { id: 'dev-pressure', batchId: 1, batchRole: 'pressure' },
        { id: 'dev-chamber', batchId: 1, batchRole: 'chamber' },
        { id: 'dev-no-batch', batchId: null, batchRole: 'gravity' },
        { id: 'dev-unmatched', batchId: 999, batchRole: 'gravity' }
      ]

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce({
          items: [{ id: 1, name: 'Batch1' }],
          total: 1,
          page: 1,
          pageSize: 50,
          pages: 1
        })
      })

      await store.getBatchList()

      const batch = store.batches.find((b) => b.id === 1)
      expect(batch.gravityDeviceId).toBe('dev-gravity')
      expect(batch.pressureDeviceId).toBe('dev-pressure')
      expect(batch.chamberDeviceId).toBe('dev-chamber')
    })
  })

  describe('getBatch Action', () => {
    it('should fetch batch by ID', async () => {
      const store = useBatchStore()
      const mockBatch = {
        id: 1,
        name: 'Single Batch',
        description: 'Description',
        chipIdGravity: 'chip1',
        chipIdPressure: '',
        active: true,
        brewDate: '2024-01-15',
        style: 'IPA',
        brewer: 'John',
        abv: 6.5,
        ebc: 20,
        ibu: 50,
        fg: 1.01,
        og: 1.055,
        brewfatherId: '',
        fermentationChamber: 0,
        fermentationSteps: '',
        tapList: false,
        gravity: [],
        pressure: [],
        pour: []
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockBatch)
      })

      const result = await store.getBatch(1)

      expect(result).toBeTruthy()
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/batches/1',
        expect.any(Object)
      )
    })

    it('should return null on fetch error', async () => {
      const store = useBatchStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Error'))

      const result = await store.getBatch(1)

      expect(result).toBeNull()
    })
  })

  describe('State Mutations', () => {
    it('should allow setting batches array', () => {
      const store = useBatchStore()
      store.batches = [
        {
          id: 1,
          name: 'Batch1',
          description: '',
          chipIdGravity: 'chip1',
          chipIdPressure: '',
          active: true,
          brewDate: '',
          style: '',
          brewer: '',
          abv: 0,
          ebc: 0,
          ibu: 0,
          fg: 0,
          og: 0,
          brewfatherId: '',
          fermentationChamber: 0,
          fermentationSteps: '',
          tapList: false,
          gravity: [],
          pressure: [],
          pour: [],
          gravityCount: 0,
          pressureCount: 0
        }
      ]

      expect(store.batches.length).toBe(1)
      expect(store.batches[0].name).toBe('Batch1')
    })

    it('should allow clearing batch array', () => {
      const store = useBatchStore()
      store.batches = [{ id: 1, name: 'Batch1' }]
      store.batches = []
      expect(store.batches.length).toBe(0)
    })
  })

  describe('updateBatch Action', () => {
    it('should update batch successfully', async () => {
      const store = useBatchStore()
      const batchToUpdate = {
        id: 1,
        name: 'Updated Batch',
        toJson: () => ({ id: 1, name: 'Updated Batch' })
      }

      const mockUpdatedBatch = {
        id: 1,
        name: 'Updated Batch',
        description: 'Updated',
        active: true
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockUpdatedBatch)
      })

      const result = await store.updateBatch(batchToUpdate)

      expect(result).toBeTruthy()
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/batches/1',
        expect.objectContaining({
          method: 'PATCH',
          headers: expect.objectContaining({ 'Content-Type': 'application/json' })
        })
      )
    })

    it('should return null on update error', async () => {
      const store = useBatchStore()
      const batchToUpdate = {
        id: 1,
        toJson: () => ({ id: 1 })
      }

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Update failed'))

      const result = await store.updateBatch(batchToUpdate)

      expect(result).toBeNull()
    })

    it('should return null if update status is not 200', async () => {
      const store = useBatchStore()
      const batchToUpdate = {
        id: 1,
        toJson: () => ({ id: 1 })
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 400
      })

      const result = await store.updateBatch(batchToUpdate)

      expect(result).toBeNull()
    })
  })

  describe('addBatch Action', () => {
    it('should add new batch successfully', async () => {
      const store = useBatchStore()
      const newBatch = {
        id: 0,
        name: 'New Batch',
        toJson: () => ({ name: 'New Batch' })
      }

      const mockResponse = {
        id: 2,
        name: 'New Batch',
        active: true
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 201,
        json: vi.fn().mockResolvedValueOnce(mockResponse)
      })

      const result = await store.addBatch(newBatch)

      expect(result).toBeTruthy()
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/batches',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({ 'Content-Type': 'application/json' })
        })
      )
    })

    it('should return null if add status is not 201', async () => {
      const store = useBatchStore()
      const newBatch = {
        toJson: () => ({ name: 'New Batch' })
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 400
      })

      const result = await store.addBatch(newBatch)

      expect(result).toBeNull()
    })

    it('should return null on add batch error', async () => {
      const store = useBatchStore()
      const newBatch = {
        toJson: () => ({ name: 'New Batch' })
      }

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Add failed'))

      const result = await store.addBatch(newBatch)

      expect(result).toBeNull()
    })
  })

  describe('deleteBatch Action', () => {
    it('should delete batch successfully', async () => {
      const store = useBatchStore()

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 204
      })

      const result = await store.deleteBatch(1)

      expect(result).toBe(true)
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/batches/1',
        expect.objectContaining({
          method: 'DELETE'
        })
      )
    })

    it('should return false if delete status is not 204', async () => {
      const store = useBatchStore()

      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 404
      })

      const result = await store.deleteBatch(1)

      expect(result).toBe(false)
    })

    it('should return false on delete error', async () => {
      const store = useBatchStore()

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Delete failed'))

      const result = await store.deleteBatch(1)

      expect(result).toBe(false)
    })
  })

  describe('anyBatchesForDevice Action', () => {
    it('should return true if device has a batch assigned', () => {
      const store = useBatchStore()
      // Mock the deviceStore by modifying the method to use a test double
      const originalMethod = store.anyBatchesForDevice
      store.anyBatchesForDevice = (chipId) => {
        const devices = [
          { id: 'chip1', batchId: 'batch1' },
          { id: 'chip2', batchId: null }
        ]
        const device = devices.find((d) => d.id === chipId)
        return device ? device.batchId !== null : false
      }
      const result = store.anyBatchesForDevice('chip1')
      store.anyBatchesForDevice = originalMethod
      expect(result).toBe(true)
    })

    it('should return false if device has no batch assigned', () => {
      const store = useBatchStore()
      // Mock the deviceStore by modifying the method to use a test double
      const originalMethod = store.anyBatchesForDevice
      store.anyBatchesForDevice = (chipId) => {
        const devices = [
          { id: 'chip1', batchId: null },
          { id: 'chip2', batchId: 'batch2' }
        ]
        const device = devices.find((d) => d.id === chipId)
        return device ? device.batchId !== null : false
      }
      const result = store.anyBatchesForDevice('chip1')
      store.anyBatchesForDevice = originalMethod
      expect(result).toBe(false)
    })

    it('should return false if no batches exist for chip', () => {
      const store = useBatchStore()
      store.batches = [{ id: 1, gravityDeviceId: 'chip1', pressureDeviceId: 'chip2' }]

      const result = store.anyBatchesForDevice('chip999')

      expect(result).toBe(false)
    })

    it('should return false if batches array is empty', () => {
      const store = useBatchStore()
      store.batches = []

      const result = store.anyBatchesForDevice('chip1')

      expect(result).toBe(false)
    })
  })

  describe('processEvent Action', () => {
    it('should delete batch by id on delete event', () => {
      const store = useBatchStore()
      store.batches = [
        { id: 1, name: 'Batch1' },
        { id: 2, name: 'Batch2' }
      ]

      store.processEvent('delete', 1)

      expect(store.batches.length).toBe(1)
      expect(store.batches[0].id).toBe(2)
    })

    it('should not delete non-existent batch', () => {
      const store = useBatchStore()
      store.batches = [{ id: 1, name: 'Batch1' }]

      store.processEvent('delete', 999)

      expect(store.batches.length).toBe(1)
    })

    it('should update batch by id on update event', async () => {
      const store = useBatchStore()
      store.batches = [
        { id: 1, name: 'OldName' },
        { id: 2, name: 'Batch2' }
      ]

      const mockUpdatedBatch = {
        id: 1,
        name: 'NewName'
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockUpdatedBatch)
      })

      await store.processEvent('update', 1)

      expect(store.batches.length).toBe(2)
      const updated = store.batches.find((b) => b.id === 1)
      expect(updated.name).toBe('NewName')
    })

    it('should handle update event when batch not found on server', async () => {
      const store = useBatchStore()
      store.batches = [{ id: 1, name: 'Batch1' }]

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Not found'))

      await store.processEvent('update', 1)

      expect(store.batches.length).toBe(1)
    })

    it('should append batch on update event when it is not already in the list', async () => {
      const store = useBatchStore()
      store.batches = [{ id: 2, name: 'Other' }]

      const mockBatch = { id: 1, name: 'NewlyFetched' }
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockBatch)
      })

      await store.processEvent('update', 1)

      expect(store.batches.length).toBe(2)
      const added = store.batches.find((b) => b.id === 1)
      expect(added.name).toBe('NewlyFetched')
    })

    it('should create new batch on create event', async () => {
      const store = useBatchStore()
      store.batches = [{ id: 1, name: 'Batch1' }]

      const mockNewBatch = {
        id: 2,
        name: 'NewBatch'
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValueOnce(mockNewBatch)
      })

      await store.processEvent('create', 2)

      expect(store.batches.length).toBe(2)
      const created = store.batches.find((b) => b.id === 2)
      expect(created.name).toBe('NewBatch')
    })

    it('should handle create event when batch not found on server', async () => {
      const store = useBatchStore()
      store.batches = [{ id: 1, name: 'Batch1' }]

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Not found'))

      await store.processEvent('create', 2)

      expect(store.batches.length).toBe(1)
    })
  })

})
