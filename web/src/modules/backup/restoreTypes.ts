/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

export interface RestoreReport {
  devices: { restored: number; failed: number }
  batches: { restored: number; failed: number }
  taps: { restored: number; failed: number }
  vessels: { restored: number; failed: number }
  /** Bulk-inserted gravity/pressure/temperature readings, across batches and vessels. */
  readings: { restored: number; failed: number }
  /** Bulk-inserted vessel pour events. */
  pours: { restored: number; failed: number }
  /** One line per rejected entity, naming it and why — shown to the user as-is. */
  problems: string[]
}

export interface RestoreDeps {
  baseURL: string
  token: string
  onProgress: () => void
  refreshDevices: () => Promise<boolean>
  refreshBatches: () => Promise<boolean>
  refreshTaps?: () => Promise<unknown>
  refreshVessels?: () => Promise<unknown>
}

export interface DeviceAssignment {
  batchId: string | null
  batchRole: string | null
  vesselId: string | null
}

export interface PendingArchive {
  id: string
  name: string
}
