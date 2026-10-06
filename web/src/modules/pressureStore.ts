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
import { Pressure } from '@/modules/classes'
import { fetchAllCursorPages } from '@brewgraph/core'
import { apiJson, apiOk } from '@/modules/apiClient'
import type { PiniaModel } from '@/modules/piniaModel'

type StoredPressure = PiniaModel<Pressure>

interface CursorResponse {
  items: Record<string, unknown>[]
  hasMore: boolean
  nextCursor: string | null
}

export const usePressureStore = defineStore('pressureStore', {
  state: () => ({
    pressure: [] as StoredPressure[]
  }),
  actions: {
    async getPressureListForBatch(batchId: string, limit = 500): Promise<StoredPressure[] | null> {
      logDebug('pressureStore.getPressureListForBatch()', batchId)
      const releaseBusy = global.acquireBusy()
      try {
        const all = await fetchAllCursorPages<Record<string, unknown>>(async (cursor) => {
          const path =
            'batches/' + batchId + '/pressure?limit=' + limit + (cursor ? '&cursor=' + cursor : '')
          const json = await apiJson<CursorResponse>('GET', path, undefined, { busy: false })
          if (!json) return null
          return { items: json.items, hasMore: json.hasMore, nextCursor: json.nextCursor ?? null }
        })
        if (!all) return null
        this.pressure = all.map((p) => Pressure.fromJson(p))
        return this.pressure
      } finally {
        releaseBusy()
      }
    },

    async getLatestPressure(limit = 5): Promise<Pressure[] | null> {
      logDebug('pressureStore.getLatestPressure()', limit)
      const json = await apiJson<Record<string, unknown>[]>(
        'GET',
        'batches/pressure/latest?limit=' + limit,
        undefined,
        { busy: false }
      )
      return json ? json.map((p) => Pressure.fromJson(p)) : null
    },

    async updatePressure(p: Pressure): Promise<boolean> {
      logDebug('pressureStore.updatePressure()', JSON.stringify(p.toJson()))
      return apiOk('PATCH', 'batches/' + p.batchId + '/pressure/' + p.id, p.toJson(), {
        okStatuses: [200]
      })
    }
  }
})
