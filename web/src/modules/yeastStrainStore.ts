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
import { logDebug } from '@/ui'
import { apiJson } from '@/modules/apiClient'

export interface YeastStrain {
  id: string
  productId: string
  name: string
  laboratory: string
  type: string
  form: string
  attenuationMin: number | null
  attenuationMax: number | null
  flocculation: string | null
  tempMinC: number | null
  tempMaxC: number | null
  alcoholTolerance: string | null
  notes: string | null
  bestFor: string | null
}

const MAX_RESULTS = 50

export const useYeastStrainStore = defineStore('yeastStrainStore', {
  state: () => ({
    strains: [] as YeastStrain[],
    loaded: false
  }),

  actions: {
    async load(): Promise<boolean> {
      if (this.loaded) return true
      logDebug('yeastStrainStore.load()')
      const data = await apiJson<YeastStrain[]>('GET', 'yeast-strains', undefined, {
        busy: false
      })
      if (Array.isArray(data)) {
        this.strains = data
        this.loaded = true
        logDebug('yeastStrainStore.load()', `loaded ${data.length} strains`)
        return true
      }
      logDebug('yeastStrainStore.load()', 'FAILED — data was', data)
      return false
    },

    search(query: string): YeastStrain[] {
      logDebug('yeastStrainStore.search()', `query="${query}" strains=${this.strains.length} loaded=${this.loaded}`)
      if (!query.trim()) return this.strains.slice(0, MAX_RESULTS)
      const q = query.toLowerCase()
      return this.strains
        .filter(
          (s: YeastStrain) =>
            s.name.toLowerCase().includes(q) ||
            s.productId.toLowerCase().includes(q) ||
            s.laboratory.toLowerCase().includes(q)
        )
        .slice(0, MAX_RESULTS)
    }
  }
})
