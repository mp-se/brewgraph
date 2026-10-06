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
import { global, saveConfigState } from '@/modules/pinia'
import { logDebug, logError } from '@/ui'
import { apiFetch, apiOk } from '@/modules/apiClient'

export const useConfigStore = defineStore('config', {
  state: () => ({
    id: '',
    temperatureFormat: '',
    pressureFormat: '',
    gravityFormat: '',
    volumeFormat: '',
    // Read-only decimal-precision metadata sourced from GET /tenant/settings'
    // `precision` field (api/oss/precision.py DECIMALS) -- never PATCHed back.
    precision: {} as Record<string, number>
  }),
  getters: {
    tempUnit(): string {
      return this.temperatureFormat
    },
    isTempC(): boolean {
      return this.temperatureFormat === 'C'
    },
    isTempF(): boolean {
      return this.temperatureFormat === 'F'
    },
    isGravitySG(): boolean {
      return this.gravityFormat === 'SG'
    },
    isGravityP(): boolean {
      return this.gravityFormat === 'P'
    },
    isVolumeMetric(): boolean {
      return this.volumeFormat === 'metric'
    },
    isVolumeUs(): boolean {
      return this.volumeFormat === 'US'
    },
    isVolumeUk(): boolean {
      return this.volumeFormat === 'UK'
    },
    isPressureBAR(): boolean {
      return this.pressureFormat === 'BAR'
    },
    isPressureKPA(): boolean {
      return this.pressureFormat === 'KPA'
    },
    isPressurePSI(): boolean {
      return this.pressureFormat === 'PSI'
    }
  },
  actions: {
    async load(): Promise<boolean> {
      logDebug('configStore.load()')
      // Note: load intentionally parses the body without a status check (legacy
      // behaviour), so it uses apiFetch rather than apiJson.
      const releaseBusy = global.acquireBusy()
      try {
        const res = await apiFetch('GET', 'tenant/settings')
        const json = await res.json()
        this.id = json.id
        this.precision = (json.precision as Record<string, number>) ?? {}
        const volumeMap: Record<string, string> = { metric: 'metric', us: 'US', uk: 'UK' }
        this.temperatureFormat = (json.temperatureFormat as string).toUpperCase()
        this.pressureFormat = (json.pressureFormat as string).toUpperCase()
        this.gravityFormat = (json.gravityFormat as string).toUpperCase()
        this.volumeFormat = volumeMap[(json.volumeFormat as string).toLowerCase()] ?? json.volumeFormat
        saveConfigState()
        return true
      } catch (err) {
        logError('configStore.load()', err)
        return false
      } finally {
        releaseBusy()
      }
    },

    async save(): Promise<boolean> {
      logDebug('configStore.save()')
      const ok = await apiOk(
        'PATCH',
        'tenant/settings',
        {
          temperatureFormat: this.temperatureFormat.toLowerCase(),
          pressureFormat: this.pressureFormat.toLowerCase(),
          gravityFormat: this.gravityFormat.toLowerCase(),
          volumeFormat: this.volumeFormat.toLowerCase()
        },
        { okStatuses: [200] }
      )
      if (ok) saveConfigState()
      return ok
    }
  }
})
