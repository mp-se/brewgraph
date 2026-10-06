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

export interface BackupMeta {
  version: string
  software: string
  created: string
}

// ---- BrewGraph v2.0 backup shapes ----

export interface BrewGraphPredictionRecord {
  id: number
  batchId: string
  outcome: string
  hoursLeft: number | null
  createdAt: string
}

export interface BrewGraphGravityRecord {
  id: number
  batchId: string
  temperature: number | null
  gravity: number
  velocity: number | null
  angle: number | null
  battery: number | null
  rssi: number | null
  runTime: number | null
  excluded: boolean
  createdAt: string
  deviceId: string | null
}

export interface BrewGraphPressureRecord {
  id: number
  batchId: string
  temperature: number | null
  pressure: number
  battery: number | null
  rssi: number | null
  runTime: number | null
  excluded: boolean
  createdAt: string
  deviceId: string | null
}

export interface BrewGraphPourEventRecord {
  id: string
  vesselId: string
  pourAmount: number
  volumeRemaining: number
  isManual: boolean
  excluded: boolean
  createdAt: string
}

export interface BrewGraphBatchRecord {
  id: string
  name: string
  description: string
  acceptIngest: boolean
  status: string
  brewDate: string | null
  style: string
  brewer: string
  abv: number
  ebc: number
  ibu: number
  fg: number
  og: number
  carbonationVolumes: number | null
  brewfatherBatchId: string
  notes: string
  fermentationChamber: string | null
  fermentationSteps: string
  gravity: BrewGraphGravityRecord[]
  pressure: BrewGraphPressureRecord[]
  /** Present at `archive` and `backup` depth; older files may not carry it. */
  batchNotes?: BrewGraphBatchNoteRecord[]
}

export interface BrewGraphBatchNoteRecord {
  content: string
  createdAt: string | null
  noteType: string | null
  testResult: string | null
}

export interface BrewGraphDeviceRecord {
  id: string
  name: string
  chipId: string
  chipFamily: string
  deviceType: string | null
  mdns: string
  config: string
  deviceColor: string
  url: string
  description: string
  collectLogs: boolean
  token: string
  fermentationStep: unknown[]
  batchId: string | null
  batchRole: string | null
  vesselId: string | null
}

export interface BrewGraphVesselTempReading {
  deviceChipId: string | null
  temperature: number | null
  tempType: string | null
  battery: number | null
  rssi: number | null
  excluded: boolean
  isAggregate: boolean
  createdAt: string | null
}

export interface BrewGraphVesselPressureReading {
  deviceChipId: string | null
  pressure: number | null
  temperature: number | null
  battery: number | null
  rssi: number | null
  runTime: number | null
  excluded: boolean
  isAggregate: boolean
  createdAt: string | null
}

export interface BrewGraphVesselRecord {
  id: string
  batchId: string
  tapId: string | null
  vesselNumber: number | null
  vesselType: string
  name: string
  fillDate: string
  totalVolume: number
  volumeRemaining: number
  bottleVolume: number | null
  bottleCount: number | null
  bottlesRemaining: number | null
  status: string
  location: string
  notes: string
  pourEvents: BrewGraphPourEventRecord[]
  temperatureReadings?: BrewGraphVesselTempReading[]
  pressureReadings?: BrewGraphVesselPressureReading[]
}

export interface BrewGraphTapRecord {
  id: string
  name: string
  tapNumber: number | null
  location: string
  notes: string
}

export interface BrewGraphBackup {
  meta: BackupMeta
  devices: BrewGraphDeviceRecord[]
  batches: BrewGraphBatchRecord[]
  taps: BrewGraphTapRecord[]
  vessels: BrewGraphVesselRecord[]
}

// ---- BrewLogger v0.8 backup shapes ----

export interface BrewLoggerGravityRecord {
  id: number
  batchId: number
  temperature: number
  gravity: number
  velocity: number
  angle: number
  battery: number
  rssi: number
  corrGravity: number
  runTime: number
  created: string
  active: boolean
}

export interface BrewLoggerPressureRecord {
  id: number
  batchId: number
  temperature: number
  pressure: number
  pressure1: number
  battery: number
  rssi: number
  runTime: number
  created: string
  active: boolean
}

export interface BrewLoggerPourRecord {
  id: number
  batchId: number
  pour: number
  volume: number
  maxVolume: number
  created: string
  active: boolean
}

export interface BrewLoggerBatchRecord {
  id: number
  name: string
  description: string
  chipIdGravity: string
  chipIdPressure: string
  active: boolean
  tapList: boolean
  brewDate: string
  style: string
  brewer: string
  abv: number
  ebc: number
  ibu: number
  fg: number
  og: number
  brewfatherId: string
  fermentationChamber: number
  fermentationSteps: string
  gravity: BrewLoggerGravityRecord[]
  pressure: BrewLoggerPressureRecord[]
  pour: BrewLoggerPourRecord[]
}

export interface BrewLoggerDeviceRecord {
  id: number
  chipId: string
  chipFamily: string
  software: string
  mdns: string
  config: string
  url: string
  description: string
  bleColor: string
  collectLogs: boolean
  fermentationStep: unknown[]
}

export interface BrewLoggerBackup {
  meta: BackupMeta
  devices: BrewLoggerDeviceRecord[]
  batches: BrewLoggerBatchRecord[]
  pressure: BrewLoggerPressureRecord[]
  pour: BrewLoggerPourRecord[]
}
