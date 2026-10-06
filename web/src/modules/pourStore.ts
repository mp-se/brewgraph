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
import { PourEvent } from '@/modules/classes'
import { fetchAllCursorPages } from '@brewgraph/core'
import { apiJson } from '@/modules/apiClient'
import type { PiniaModel } from '@/modules/piniaModel'

type StoredPourEvent = PiniaModel<PourEvent>

export const usePourStore = defineStore('pourStore', {
  state: () => ({
    pours: [] as StoredPourEvent[]
  }),
  actions: {
    async getLatestPour(limit = 5): Promise<StoredPourEvent[] | null> {
      logDebug('pourStore.getLatestPour()', limit)
      const json = await apiJson<Record<string, unknown>[]>(
        'GET',
        'vessels/pours/latest?limit=' + limit,
        undefined,
        { busy: false }
      )
      if (!json) return null
      this.pours = json.map((p) => PourEvent.fromJson(p))
      return this.pours
    },

    async listPours(vesselId: string): Promise<StoredPourEvent[] | null> {
      logDebug('pourStore.listPours()', vesselId)
      const releaseBusy = global.acquireBusy()
      try {
        const all = await fetchAllCursorPages<Record<string, unknown>>(async (cursor) => {
          const path =
            'vessels/' + vesselId + '/pours?limit=200' + (cursor ? '&cursor=' + cursor : '')
          const json = await apiJson<{
            items: Record<string, unknown>[]
            has_more: boolean
            next_cursor: string | null
          }>('GET', path, undefined, { busy: false })
          if (!json) return null
          return { items: json.items, hasMore: json.has_more, nextCursor: json.next_cursor ?? null }
        })
        if (!all) return null
        this.pours = all.map((p) => PourEvent.fromJson(p))
        return this.pours
      } finally {
        releaseBusy()
      }
    },

    async recordPour(vesselId: string, pourAmount: number): Promise<PourEvent | null> {
      logDebug('pourStore.recordPour()', vesselId, pourAmount)
      const json = await apiJson<Record<string, unknown>>(
        'POST',
        'vessels/' + vesselId + '/pours',
        { pourAmount },
        { okStatuses: [201] }
      )
      return json ? PourEvent.fromJson(json) : null
    },

    async recordBottlePour(vesselId: string, bottleCount: number): Promise<PourEvent | null> {
      logDebug('pourStore.recordBottlePour()', vesselId, bottleCount)
      const json = await apiJson<Record<string, unknown>>(
        'POST',
        'vessels/' + vesselId + '/pours/bottles',
        { bottleCount },
        { okStatuses: [201] }
      )
      return json ? PourEvent.fromJson(json) : null
    }
  }
})
