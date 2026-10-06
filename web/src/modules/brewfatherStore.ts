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
import { logDebug, logError } from '@/ui'
import { BrewfatherBatch } from '@/modules/classes'
import { apiFetch } from '@/modules/apiClient'
import type { PiniaModel } from '@/modules/piniaModel'

type StoredBrewfatherBatch = PiniaModel<BrewfatherBatch>

export const useBrewfatherStore = defineStore('brewfatherStore', {
  state: () => ({
    batches: [] as StoredBrewfatherBatch[],
    valid: false
  }),
  getters: {
    isValid(): boolean {
      return this.valid
    },
    batchList(): StoredBrewfatherBatch[] {
      return this.batches
    }
  },
  actions: {
    async getBatchList(): Promise<boolean> {
      if (this.isValid) {
        logDebug('brewfatherStore.getBatchList()', 'Cache is valid, skipping fetch!')
        return true
      }

      logDebug('brewfatherStore.getBatchList()')
      try {
        const res = await apiFetch(
          'GET',
          'brewfather/batch?planning=true&brewing=true&fermenting=true&completed=true&archived=false'
        )
        logDebug('brewfatherStore.getBatchList()', res.status)

        if (res.status === 424) {
          logDebug(
            'brewfatherStore.getBatchList()',
            'Brewfather keys not configured, returning empty array'
          )
          this.batches = []
          this.valid = true
          setTimeout(
            () => {
              this.valid = false
            },
            60 * 5 * 1000
          )
          return true
        }

        if (!res.ok) throw res
        const json = await res.json()
        this.batches = []

        json.forEach((b: Record<string, unknown>) => {
          this.batches.push(BrewfatherBatch.fromJson(b))
        })

        this.valid = true
        setTimeout(
          () => {
            this.valid = false
          },
          60 * 5 * 1000
        )
        return true
      } catch (err) {
        logError('brewfatherStore.getBatchList()', err)
        return false
      }
    }
  }
})
