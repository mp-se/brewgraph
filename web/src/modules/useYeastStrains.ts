/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { ref } from 'vue'
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

const _strains = ref<YeastStrain[]>([])
let _loaded = false

export function useYeastStrains() {
  async function load(): Promise<void> {
    if (_loaded) return
    const data = await apiJson<YeastStrain[]>('GET', 'yeast-strains', undefined, {
      busy: false
    })
    if (Array.isArray(data)) {
      _strains.value = data
      _loaded = true
    }
  }

  function search(query: string): YeastStrain[] {
    if (!query.trim()) return _strains.value.slice(0, 50)
    const q = query.toLowerCase()
    return _strains.value
      .filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.productId.toLowerCase().includes(q) ||
          s.laboratory.toLowerCase().includes(q)
      )
      .slice(0, 50)
  }

  return { strains: _strains, load, search }
}
