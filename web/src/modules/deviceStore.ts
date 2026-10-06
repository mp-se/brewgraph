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
import { Device, Gravity, Pressure } from '@/modules/classes'
import { fetchAllNumberedPages } from '@brewgraph/core'
import { apiJson, apiOk } from '@/modules/apiClient'
import type { PiniaModel } from '@/modules/piniaModel'

type StoredDevice = PiniaModel<Device>

export const useDeviceStore = defineStore('deviceStore', {
  state: () => ({
    devices: [] as StoredDevice[]
  }),
  getters: {
    deviceList(): StoredDevice[] {
      return this.devices
    }
  },
  actions: {
    async processEvent(method: string, id: string): Promise<void> {
      logDebug('deviceStore.processEvent()', method, id)
      if (method === 'delete') {
        this.devices = this.devices.filter((d) => d.id !== id)
        logDebug('deviceStore.processEvent()', 'Removed device with', id)
        global.updatedDeviceData += 1
      } else if (method === 'update') {
        const device = await this.getDevice(id)
        if (device) {
          this.devices = this.devices.filter((d) => d.id !== id)
          this.devices.push(device)
          logDebug('deviceStore.processEvent()', 'Updated device with', id)
          global.updatedDeviceData += 1
        }
      } else if (method === 'create') {
        const device = await this.getDevice(id)
        if (device) {
          this.devices.push(device)
          logDebug('deviceStore.processEvent()', 'Added device with', id)
          global.updatedDeviceData += 1
        }
      }
    },

    async getDeviceList(): Promise<StoredDevice[] | null> {
      logDebug('deviceStore.getDeviceList()')
      const releaseBusy = global.acquireBusy()
      try {
        const all = await fetchAllNumberedPages<Record<string, unknown>>((page) =>
          apiJson('GET', `devices?page=${page}&pageSize=100`, undefined, { busy: false })
        )
        if (!all) return null
        this.devices = all.map((d) => Device.fromJson(d))
        return this.devices
      } finally {
        releaseBusy()
      }
    },

    async getDevice(id: string): Promise<Device | null> {
      logDebug('deviceStore.getDevice()', id)
      if (!id) return null
      const json = await apiJson<Record<string, unknown>>('GET', 'devices/' + id)
      return json ? Device.fromJson(json) : null
    },

    async updateDevice(d: Device): Promise<Device | null> {
      logDebug('deviceStore.updateDevice()', d.id, d.toJson())
      const json = await apiJson<Record<string, unknown>>(
        'PATCH',
        'devices/' + d.id,
        d.toJson(),
        { okStatuses: [200] }
      )
      return json ? Device.fromJson(json) : null
    },

    async addDevice(d: Device): Promise<Device | null> {
      logDebug('deviceStore.addDevice()', d.toJson())
      const json = await apiJson<Record<string, unknown>>('POST', 'devices', d.toJson(), {
        okStatuses: [201]
      })
      return json ? Device.fromJson(json) : null
    },

    async deleteDevice(id: string): Promise<boolean> {
      logDebug('deviceStore.deleteDevice()', id)
      return apiOk('DELETE', 'devices/' + id, undefined, { okStatuses: [204] })
    },

    async regenerateToken(id: string): Promise<string | null> {
      logDebug('deviceStore.regenerateToken()', id)
      const json = await apiJson<{ token: string }>(
        'POST',
        'devices/' + id + '/token',
        undefined,
        { okStatuses: [200] }
      )
      return json ? json.token : null
    },

    async getLatestGravity(deviceId: string): Promise<Gravity | null> {
      logDebug('deviceStore.getLatestGravity()', deviceId)
      const json = await apiJson<Record<string, unknown>>(
        'GET',
        'devices/' + deviceId + '/gravity/latest',
        undefined,
        { busy: false, notFoundAsNull: true }
      )
      return json ? Gravity.fromJson(json) : null
    },

    async getLatestPressure(deviceId: string): Promise<Pressure | null> {
      logDebug('deviceStore.getLatestPressure()', deviceId)
      const json = await apiJson<Record<string, unknown>>(
        'GET',
        'devices/' + deviceId + '/pressure/latest',
        undefined,
        { busy: false, notFoundAsNull: true }
      )
      return json ? Pressure.fromJson(json) : null
    },

    async proxyRequest(
      method: string,
      url: string,
      header: string,
      body: unknown,
      options: { noErrorNotify?: boolean } = {}
    ): Promise<unknown> {
      const reqBody = { url, method, header, body }
      logDebug('deviceStore.proxyRequest()', url, reqBody)
      return apiJson('POST', 'devices/proxy-fetch', reqBody, {
        busy: false,
        okStatuses: [200],
        noErrorNotify: options.noErrorNotify
      })
    },

    async getFermentationSteps(batchId: string): Promise<unknown[] | null> {
      logDebug('deviceStore.getFermentationSteps()', batchId)
      return apiJson<unknown[]>('GET', 'batches/' + batchId + '/fermentation-steps', undefined, {
        busy: false,
        okStatuses: [200]
      })
    },

    async addFermentationSteps(batchId: string, steps: unknown[]): Promise<boolean> {
      logDebug('deviceStore.addFermentationSteps()', batchId, steps)
      return apiOk('POST', 'batches/' + batchId + '/fermentation-steps', steps, {
        busy: false,
        okStatuses: [201]
      })
    },

    async searchNetwork(): Promise<unknown[] | null> {
      logDebug('deviceStore.searchNetwork()')
      return apiJson<unknown[]>('GET', 'devices/mdns', undefined, { busy: false })
    },

    /**
     * Turn on chamber control for a batch's saved steps.
     *
     * Creating the steps is not enough: `chamber_control_active` is set here and
     * nowhere else, and the chamber ingest returns mode `R` until it is. Returns the
     * steps with their computed absolute dates, or null on failure.
     */
    async activateFermentationSteps(batchId: string): Promise<unknown[] | null> {
      logDebug('deviceStore.activateFermentationSteps()', batchId)
      return apiJson<unknown[]>(
        'POST',
        'batches/' + batchId + '/fermentation-steps/activate',
        undefined,
        { busy: false, okStatuses: [200] }
      )
    },

    async deactivateFermentationSteps(batchId: string): Promise<boolean> {
      logDebug('deviceStore.deactivateFermentationSteps()', batchId)
      return apiOk(
        'POST',
        'batches/' + batchId + '/fermentation-steps/deactivate',
        undefined,
        { busy: false, okStatuses: [204] }
      )
    },

    async advanceFermentationStep(batchId: string): Promise<unknown | null> {
      logDebug('deviceStore.advanceFermentationStep()', batchId)
      return apiJson<unknown>(
        'POST',
        'batches/' + batchId + '/fermentation-steps/advance',
        undefined,
        { busy: false, okStatuses: [200] }
      )
    },

    async deleteFermentationSteps(batchId: string): Promise<boolean> {
      logDebug('deviceStore.deleteFermentationSteps()', batchId)
      return apiOk('DELETE', 'batches/' + batchId + '/fermentation-steps', undefined, {
        busy: false,
        okStatuses: [204]
      })
    }
  }
})
