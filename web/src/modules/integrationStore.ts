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
import { Integration } from '@/modules/classes'
import { apiJson, apiOk } from '@/modules/apiClient'
import type { PiniaModel } from '@/modules/piniaModel'

type StoredIntegration = PiniaModel<Integration>

export const useIntegrationStore = defineStore('integrationStore', {
  state: () => ({
    integrations: [] as StoredIntegration[]
  }),
  getters: {
    integrationList(): StoredIntegration[] {
      return this.integrations
    }
  },
  actions: {
    async getIntegrationList(): Promise<StoredIntegration[] | null> {
      logDebug('integrationStore.getIntegrationList()')
      const json = await apiJson<Record<string, unknown>[]>('GET', 'integrations')
      if (!json) return null
      this.integrations = json.map((i) => Integration.fromJson(i))
      return this.integrations
    },

    async addIntegration(i: Integration): Promise<Integration | null> {
      logDebug('integrationStore.addIntegration()', i.toJson())
      const json = await apiJson<Record<string, unknown>>('POST', 'integrations', i.toJson(), {
        okStatuses: [201]
      })
      if (!json) return null
      const created = Integration.fromJson(json)
      this.integrations.push(created)
      return created
    },

    async updateIntegration(
      id: string,
      patch: Record<string, unknown>
    ): Promise<Integration | null> {
      logDebug('integrationStore.updateIntegration()', id, patch)
      const json = await apiJson<Record<string, unknown>>(
        'PATCH',
        'integrations/' + id,
        patch,
        { okStatuses: [200] }
      )
      if (!json) return null
      const updated = Integration.fromJson(json)
      const idx = this.integrations.findIndex((x) => x.id === id)
      if (idx !== -1) this.integrations.splice(idx, 1, updated)
      return updated
    },

    async deleteIntegration(id: string): Promise<boolean> {
      logDebug('integrationStore.deleteIntegration()', id)
      const ok = await apiOk('DELETE', 'integrations/' + id, undefined, { okStatuses: [204] })
      if (ok) this.integrations = this.integrations.filter((x) => x.id !== id)
      return ok
    },

    async testIntegration(id: string): Promise<string | null> {
      const json = await apiJson<Record<string, unknown>>('POST', 'integrations/' + id + '/test', undefined, { okStatuses: [200] })
      if (!json) return null
      await this.getIntegrationList()
      return (json.outcome as string) ?? null
    }
  }
})
