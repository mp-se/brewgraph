/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { defineStore } from 'pinia'
import { fetchAllCursorPages } from '@brewgraph/core'
import { global } from '@/modules/pinia'
import { apiJson } from '@/modules/apiClient'
import { logDebug } from '@/ui'

export interface TemperatureReading {
  id: number
  createdAt: string
  temperature: number
  tempType: string
  battery: number | null
  rssi: number | null
  excluded: boolean
}

interface CursorResponse {
  items: TemperatureReading[]
  hasMore: boolean
  nextCursor: string | null
}

export const useTempReadingStore = defineStore('tempReadingStore', {
  state: () => ({
    readings: [] as TemperatureReading[]
  }),
  actions: {
    async getTempListForBatch(batchId: string, limit = 500): Promise<TemperatureReading[] | null> {
      logDebug('tempReadingStore.getTempListForBatch()', batchId)
      const releaseBusy = global.acquireBusy()
      try {
        const readings = await fetchAllCursorPages<TemperatureReading>(async (cursor) => {
          const path =
            'batches/' + batchId + '/temp?limit=' + limit + (cursor ? '&cursor=' + cursor : '')
          const json = await apiJson<CursorResponse>('GET', path, undefined, { busy: false })
          if (!json) return null
          return { items: json.items, hasMore: json.hasMore, nextCursor: json.nextCursor ?? null }
        })
        if (!readings) return null
        this.readings = readings
        return this.readings
      } finally {
        releaseBusy()
      }
    }
  }
})
