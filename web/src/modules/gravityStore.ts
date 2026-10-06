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
import { Gravity } from '@/modules/classes'
import { fetchAllCursorPages } from '@brewgraph/core'
import { apiJson, apiOk } from '@/modules/apiClient'
import type { PiniaModel } from '@/modules/piniaModel'

type StoredGravity = PiniaModel<Gravity>

interface CursorResponse {
  items: Record<string, unknown>[]
  hasMore: boolean
  nextCursor: string | null
}

export const useGravityStore = defineStore('gravityStore', {
  state: () => ({
    gravity: [] as StoredGravity[]
  }),
  actions: {
    async getGravityListForBatch(batchId: string, limit = 500): Promise<StoredGravity[] | null> {
      logDebug('gravityStore.getGravityListForBatch()', batchId)
      const releaseBusy = global.acquireBusy()
      try {
        const all = await fetchAllCursorPages<Record<string, unknown>>(async (cursor) => {
          const path =
            'batches/' + batchId + '/gravity?limit=' + limit + (cursor ? '&cursor=' + cursor : '')
          const json = await apiJson<CursorResponse>('GET', path, undefined, { busy: false })
          if (!json) return null
          return { items: json.items, hasMore: json.hasMore, nextCursor: json.nextCursor ?? null }
        })
        if (!all) return null
        this.gravity = all.map((g) => Gravity.fromJson(g))
        return this.gravity
      } finally {
        releaseBusy()
      }
    },

    async getLatestGravity(limit = 5): Promise<Gravity[] | null> {
      logDebug('gravityStore.getLatestGravity()', limit)
      const json = await apiJson<Record<string, unknown>[]>(
        'GET',
        'batches/gravity/latest?limit=' + limit,
        undefined,
        { busy: false }
      )
      return json ? json.map((g) => Gravity.fromJson(g)) : null
    },

    async updateGravity(g: Gravity): Promise<boolean> {
      logDebug('gravityStore.updateGravity()', JSON.stringify(g.toJson()))
      return apiOk('PATCH', 'batches/' + g.batchId + '/gravity/' + g.id, g.toJson(), {
        okStatuses: [200]
      })
    }
  }
})
