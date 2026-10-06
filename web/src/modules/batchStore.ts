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

import { defineStore } from 'pinia'
import { global } from '@/modules/pinia'
import { logDebug } from '@/ui'
import { Batch } from '@/modules/classes'
import { fetchAllNumberedPages } from '@brewgraph/core'
import { useDeviceStore } from '@/modules/deviceStore'
import { apiJson, apiOk } from '@/modules/apiClient'
import type { PiniaModel } from '@/modules/piniaModel'

type StoredBatch = PiniaModel<Batch>

export const useBatchStore = defineStore('batchStore', {
  state: () => ({
    batches: [] as StoredBatch[],
    total: 0
  }),
  getters: {
    batchList(): StoredBatch[] {
      return this.batches
    }
  },
  actions: {
    async processEvent(method: string, id: string): Promise<void> {
      logDebug('batchStore.processEvent()', method, id)
      if (method === 'delete') {
        this.batches = this.batches.filter((b) => b.id !== id)
        logDebug('batchStore.processEvent()', 'Removed batch with', id)
        global.updatedBatchData += 1
      } else if (method === 'update') {
        const batch = await this.getBatch(id)
        if (batch && batch.id) {
          const idx = this.batches.findIndex((b) => b.id === id)
          if (idx !== -1) this.batches.splice(idx, 1, batch)
          else this.batches.push(batch)
          logDebug('batchStore.processEvent()', 'Updated batch with', id)
          global.updatedBatchData += 1
        }
      } else if (method === 'create') {
        const batch = await this.getBatch(id)
        if (batch && batch.id) {
          this.batches.push(batch)
          logDebug('batchStore.processEvent()', 'Added batch with', id)
          global.updatedBatchData += 1
        }
      }
    },

    anyBatchesForDevice(deviceId: string): boolean {
      const deviceStore = useDeviceStore()
      const device = deviceStore.devices.find((d) => d.id === deviceId)
      return device != null && device.batchId != null
    },

    async getBatchList(pageSize = 200, status: string | null = null): Promise<StoredBatch[] | null> {
      logDebug('batchStore.getBatchList()', { pageSize, status })
      const releaseBusy = global.acquireBusy()
      try {
        const all = await fetchAllNumberedPages<Record<string, unknown>>((page) => {
          const path =
            'batches?page=' + page + '&pageSize=' + pageSize + (status ? '&status=' + status : '')
          return apiJson('GET', path, undefined, { busy: false })
        })
        if (!all) return null
        this.batches = all.map((b) => Batch.fromJson(b))
        this.total = this.batches.length
        const deviceStore = useDeviceStore()
        for (const device of deviceStore.devices) {
          if (!device.batchId) continue
          const batch = this.batches.find((b) => b.id === device.batchId)
          if (!batch) continue
          if (device.batchRole === 'gravity') batch.gravityDeviceId = device.id
          else if (device.batchRole === 'pressure') batch.pressureDeviceId = device.id
          else if (device.batchRole === 'chamber') batch.chamberDeviceId = device.id
        }
        return this.batches
      } finally {
        releaseBusy()
      }
    },

    async getBatch(id: string): Promise<Batch | null> {
      logDebug('batchStore.getBatch()', id)
      const json = await apiJson<Record<string, unknown>>('GET', 'batches/' + id)
      return json ? Batch.fromJson(json) : null
    },

    async updateBatch(b: Batch): Promise<Batch | null> {
      logDebug('batchStore.updateBatch()', b.id, b.toJson())
      const json = await apiJson<Record<string, unknown>>('PATCH', 'batches/' + b.id, b.toJson(), {
        okStatuses: [200]
      })
      return json ? Batch.fromJson(json) : null
    },

    /*
     * Archiving is a status-only transition. `updateBatch()` PATCHes `b.toJson()`,
     * which deliberately excludes `status` — sending the full batch fields alongside
     * a status change risks clobbering server-computed fields, and a status change
     * should not silently carry along whatever else the in-memory object holds.
     * These two send exactly `{ status }`.
     */
    async archiveBatch(id: string): Promise<Batch | null> {
      logDebug('batchStore.archiveBatch()', id)
      const json = await apiJson<Record<string, unknown>>(
        'PATCH',
        'batches/' + id,
        { status: 'archived' },
        { okStatuses: [200] }
      )
      return json ? Batch.fromJson(json) : null
    },

    /*
     * The server ignores the specific non-archived value sent and derives the real
     * resulting status (fermenting/packaged) from live vessel-connection state —
     * see docs/spec-api-batches.md "Un-archiving". 'packaged' here is just a
     * placeholder to signal "take this out of archived", not a status assertion.
     */
    async unarchiveBatch(id: string): Promise<Batch | null> {
      logDebug('batchStore.unarchiveBatch()', id)
      const json = await apiJson<Record<string, unknown>>(
        'PATCH',
        'batches/' + id,
        { status: 'packaged' },
        { okStatuses: [200] }
      )
      return json ? Batch.fromJson(json) : null
    },

    async addBatch(b: Batch): Promise<Batch | null> {
      logDebug('batchStore.addBatch()', b.toJson())
      const json = await apiJson<Record<string, unknown>>('POST', 'batches', b.toJson(), {
        okStatuses: [201]
      })
      return json ? Batch.fromJson(json) : null
    },

    async deleteBatch(id: string): Promise<boolean> {
      logDebug('batchStore.deleteBatch()', id)
      return apiOk('DELETE', 'batches/' + id, undefined, { okStatuses: [204] })
    }
  }
})
