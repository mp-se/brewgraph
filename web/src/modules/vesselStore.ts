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
import { logDebug, logError } from '@/ui'
import { StorageVessel } from '@/modules/classes'
import { fetchAllNumberedPages } from '@brewgraph/core'
import { apiJson, apiOk } from '@/modules/apiClient'
import type { PiniaModel } from '@/modules/piniaModel'

type StoredVessel = PiniaModel<StorageVessel>

export const useVesselStore = defineStore('vesselStore', {
  state: () => ({
    vessels: [] as StoredVessel[]
  }),
  getters: {
    vesselList(): StoredVessel[] {
      return this.vessels
    }
  },
  actions: {
    /** Return available kegs without replacing the current vessel-list view. */
    async listEmptyKegs(): Promise<StorageVessel[] | null> {
      const all = await fetchAllNumberedPages<Record<string, unknown>>((page) =>
        apiJson('GET', 'vessels?page=' + page + '&pageSize=100&status=empty', undefined, {
          busy: false
        })
      )
      return all
        ? all.map(StorageVessel.fromJson).filter((v) => v.vesselType === 'keg' && !v.batchId)
        : null
    },

    async processEvent(method: string, id: string): Promise<void> {
      logDebug('vesselStore.processEvent()', method, id)
      const vesselId = String(id ?? '').trim()
      if (!vesselId || vesselId === 'undefined' || vesselId === 'null') {
        logError('vesselStore.processEvent()', 'Invalid vessel id', id)
        return
      }
      if (method === 'delete') {
        this.vessels = this.vessels.filter((v) => v.id !== vesselId)
        logDebug('vesselStore.processEvent()', 'Removed vessel with', vesselId)
        global.updatedVesselData += 1
      } else if (method === 'update') {
        const vessel = await this.getVessel(vesselId)
        if (vessel && vessel.id) {
          const idx = this.vessels.findIndex((v) => v.id === vesselId)
          if (idx !== -1) this.vessels.splice(idx, 1, vessel)
          else this.vessels.push(vessel)
          logDebug('vesselStore.processEvent()', 'Updated vessel with', vesselId)
          global.updatedVesselData += 1
        }
      } else if (method === 'create') {
        const vessel = await this.getVessel(vesselId)
        if (vessel && vessel.id) {
          this.vessels.push(vessel)
          logDebug('vesselStore.processEvent()', 'Added vessel with', vesselId)
          global.updatedVesselData += 1
        }
      }
    },

    async getVesselList(
      batchId: string | null = null,
      status: string | null = null
    ): Promise<StoredVessel[] | null> {
      logDebug('vesselStore.getVesselList()', { batchId, status })
      const releaseBusy = global.acquireBusy()
      try {
        const all = await fetchAllNumberedPages<Record<string, unknown>>((page) => {
          const path =
            'vessels?page=' +
            page +
            '&pageSize=100' +
            (batchId ? '&batchId=' + batchId : '') +
            (status ? '&status=' + status : '')
          return apiJson('GET', path, undefined, { busy: false })
        })
        if (!all) return null
        this.vessels = all.map((v) => StorageVessel.fromJson(v))
        return this.vessels
      } finally {
        releaseBusy()
      }
    },

    async getVessel(id: string): Promise<StorageVessel | null> {
      logDebug('vesselStore.getVessel()', id)
      const vesselId = String(id ?? '').trim()
      if (!vesselId || vesselId === 'undefined' || vesselId === 'null') {
        logError('vesselStore.getVessel()', 'Invalid vessel id', id)
        return null
      }
      const json = await apiJson<Record<string, unknown>>('GET', 'vessels/' + vesselId)
      return json ? StorageVessel.fromJson(json) : null
    },

    async addVessel(v: StorageVessel): Promise<StorageVessel | null> {
      logDebug('vesselStore.addVessel()', v.toJson())
      const json = await apiJson<Record<string, unknown>>('POST', 'vessels', v.toJson(), {
        okStatuses: [201]
      })
      return json ? StorageVessel.fromJson(json) : null
    },

    async updateVessel(v: StorageVessel): Promise<StorageVessel | null> {
      logDebug('vesselStore.updateVessel()', v.id, v.toJson())
      const json = await apiJson<Record<string, unknown>>('PATCH', 'vessels/' + v.id, v.toJson(), {
        okStatuses: [200]
      })
      return json ? StorageVessel.fromJson(json) : null
    },

    /*
     * Assignment is a field write, so it goes through the ordinary vessel PATCH —
     * the dedicated /assign-batch and /assign-tap endpoints were removed.
     *
     * Both send **only** the one field, never the whole vessel. The server reads
     * `exclude_unset`, so a null here is the command "empty this keg" / "release this
     * tap"; sending the full object would make every field an assertion and turn an
     * unrelated stale value into an unintended change.
     */
    async assignBatch(vesselId: string, batchId: string | null): Promise<StorageVessel | null> {
      logDebug('vesselStore.assignBatch()', vesselId, batchId)
      const json = await apiJson<Record<string, unknown>>(
        'PATCH',
        'vessels/' + vesselId,
        { batchId },
        { okStatuses: [200] }
      )
      return json ? StorageVessel.fromJson(json) : null
    },

    async assignTap(vesselId: string, tapId: string | null): Promise<StorageVessel | null> {
      logDebug('vesselStore.assignTap()', vesselId, tapId)
      const json = await apiJson<Record<string, unknown>>(
        'PATCH',
        'vessels/' + vesselId,
        { tapId },
        { okStatuses: [200] }
      )
      return json ? StorageVessel.fromJson(json) : null
    },

    async deleteVessel(id: string): Promise<boolean> {
      logDebug('vesselStore.deleteVessel()', id)
      return apiOk('DELETE', 'vessels/' + id, undefined, { okStatuses: [204] })
    }
  }
})
