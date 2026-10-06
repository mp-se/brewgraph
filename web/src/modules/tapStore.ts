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
import { Tap } from '@/modules/classes'
import { fetchAllNumberedPages } from '@brewgraph/core'
import { apiJson, apiOk } from '@/modules/apiClient'
import type { PiniaModel } from '@/modules/piniaModel'

type StoredTap = PiniaModel<Tap>

export const useTapStore = defineStore('tapStore', {
  state: () => ({
    taps: [] as StoredTap[]
  }),
  getters: {
    tapList(): StoredTap[] {
      return this.taps
    }
  },
  actions: {
    async processEvent(method: string, id: string): Promise<void> {
      logDebug('tapStore.processEvent()', method, id)
      if (method === 'delete') {
        this.taps = this.taps.filter((t) => t.id !== id)
        logDebug('tapStore.processEvent()', 'Removed tap with', id)
        global.updatedTapData += 1
      } else if (method === 'update') {
        const tap = await this.getTap(id)
        if (tap && tap.id) {
          const idx = this.taps.findIndex((t) => t.id === id)
          if (idx !== -1) this.taps.splice(idx, 1, tap)
          else this.taps.push(tap)
          logDebug('tapStore.processEvent()', 'Updated tap with', id)
          global.updatedTapData += 1
        }
      } else if (method === 'create') {
        const tap = await this.getTap(id)
        if (tap && tap.id) {
          this.taps.push(tap)
          logDebug('tapStore.processEvent()', 'Added tap with', id)
          global.updatedTapData += 1
        }
      }
    },

    async getTapList(): Promise<StoredTap[] | null> {
      logDebug('tapStore.getTapList()')
      const releaseBusy = global.acquireBusy()
      try {
        const all = await fetchAllNumberedPages<Record<string, unknown>>((page) =>
          apiJson('GET', 'taps?page=' + page + '&pageSize=100', undefined, { busy: false })
        )
        if (!all) return null
        this.taps = all.map((t) => Tap.fromJson(t))
        return this.taps
      } finally {
        releaseBusy()
      }
    },

    async getTap(id: string): Promise<Tap | null> {
      logDebug('tapStore.getTap()', id)
      const tapId = String(id ?? '').trim()
      if (!tapId || tapId === 'undefined' || tapId === 'null') {
        logError('tapStore.getTap()', 'Invalid tap id', id)
        return null
      }
      const json = await apiJson<Record<string, unknown>>('GET', 'taps/' + tapId)
      return json ? Tap.fromJson(json) : null
    },

    async addTap(t: Tap): Promise<Tap | null> {
      logDebug('tapStore.addTap()', t.toJson())
      const json = await apiJson<Record<string, unknown>>('POST', 'taps', t.toJson(), {
        okStatuses: [201]
      })
      return json ? Tap.fromJson(json) : null
    },

    async updateTap(t: Tap): Promise<Tap | null> {
      logDebug('tapStore.updateTap()', t.id, t.toJson())
      const json = await apiJson<Record<string, unknown>>('PATCH', 'taps/' + t.id, t.toJson(), {
        okStatuses: [200]
      })
      return json ? Tap.fromJson(json) : null
    },

    async regenerateToken(id: string): Promise<string | null> {
      logDebug('tapStore.regenerateToken()', id)
      const json = await apiJson<{ token: string }>(
        'POST',
        'taps/' + id + '/token',
        undefined,
        { okStatuses: [200] }
      )
      return json ? json.token : null
    },

    async deleteTap(id: string): Promise<boolean> {
      logDebug('tapStore.deleteTap()', id)
      return apiOk('DELETE', 'taps/' + id, undefined, { okStatuses: [204] })
    }
  }
})
