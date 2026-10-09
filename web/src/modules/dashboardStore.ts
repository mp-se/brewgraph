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

export interface DashboardPrediction {
  id: number
  batchId: string | null
  deviceId: string | null
  vesselId: string | null
  predictionType: string
  outcome: string
  hoursLeft: number | null
  createdAt: string
}

export interface DashboardLatestReading {
  gravity: number | null
  angle?: number | null
  pressure: number | null
  temperature: number | null
  battery: number | null
  rssi: number | null
  recordedAt: string | null
}

export interface DashboardDevice {
  id: string
  name: string
  chipFamily: string | null
  software: string | null
  batchId: string | null
  batchRole: string | null
  vesselId: string | null
  status: string | null
  lastSeenAt: string | null
  latestReading: DashboardLatestReading | null
  predictions: DashboardPrediction[]
}

export interface DashboardBatch {
  id: string
  name: string
  status: string | null
  brewDate: string | null
  dayCount: number | null
  og: number | null
  fg: number | null
  currentGravity: number | null
  currentPressure: number | null
  currentTemp: number | null
  tempDeviceId: string | null
  battery: number | null
  rssi: number | null
  firstReadingAt: string | null
  lastReadingAt: string | null
  gravityCount: number
  pressureCount: number
  predictions: DashboardPrediction[]
}

export interface DashboardTap {
  id: string
  name: string
  tapNumber: number | null
  location: string | null
  vesselId: string | null
  vesselName: string | null
  batchName: string | null
  batchId: string | null
  volumeRemaining: number | null
}

export interface DashboardVessel {
  id: string
  name: string
  vesselType: string | null
  status: string | null
  tapId: string | null
  batchId: string | null
  batchName: string | null
  totalVolume: number | null
  volumeRemaining: number | null
  fillDate: string | null
  predictions: DashboardPrediction[]
}


export interface DashboardReadyItem {
  id: string
  name: string
  kind: string
  readyDate: string | null
}

export interface DashboardData {
  devices: DashboardDevice[]
  batches: DashboardBatch[]
  taps: DashboardTap[]
  vessels: DashboardVessel[]
  readyBatches: DashboardReadyItem[]
  readyVessels: DashboardReadyItem[]
}

export const useDashboardStore = defineStore('dashboardStore', {
  state: () => ({
    data: null as DashboardData | null
  }),

  getters: {
    batches(): DashboardBatch[] {
      return this.data?.batches ?? []
    },
    devices(): DashboardDevice[] {
      return this.data?.devices ?? []
    },
    taps(): DashboardTap[] {
      return this.data?.taps ?? []
    },
    vessels(): DashboardVessel[] {
      return this.data?.vessels ?? []
    },
    readyBatches(): DashboardReadyItem[] {
      return this.data?.readyBatches ?? []
    },
    readyVessels(): DashboardReadyItem[] {
      return this.data?.readyVessels ?? []
    }
  },

  actions: {
    async fetch(): Promise<DashboardData | null> {
      logDebug('dashboardStore.fetch()')
      const data = await apiJson<DashboardData>('GET', 'dashboard')
      if (!data) return null
      this.data = data
      return data
    },

    latestPredictionForBatch(batchId: string): DashboardPrediction | null {
      const batch = this.data?.batches.find((b: DashboardBatch) => b.id === batchId)
      return batch?.predictions[0] ?? null
    }
  }
})
