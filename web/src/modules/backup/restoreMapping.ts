/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import type { ExportDocument } from './exportDocument'
import type { BrewGraphTapRecord, BrewGraphVesselRecord } from './types'
import type { DeviceAssignment } from './restoreTypes'

export function mapDevicePayload(device: ExportDocument['devices'][number]): {
  payload: Record<string, unknown>
  assignment: DeviceAssignment
} {
  const payload: Record<string, unknown> = { ...device, fermentationStep: [] }
  if (payload.collectLogs === undefined) payload.collectLogs = false
  delete payload.role
  delete payload.board
  delete payload.gyroModel
  delete payload.deviceFiltered
  delete payload.batchId
  delete payload.batchRole
  delete payload.vesselId

  return {
    payload,
    assignment: {
      batchId: device.batchId ?? null,
      batchRole: device.batchRole ?? null,
      vesselId: device.vesselId ?? null
    }
  }
}

export function mapDeviceAssignment(
  assignment: DeviceAssignment,
  batchIdMap: Map<string, string>,
  vesselIdMap: Map<string, string>
): Record<string, unknown> | null {
  if (!assignment.batchId && !assignment.vesselId && !assignment.batchRole) return null
  return {
    batchId: assignment.batchId ? (batchIdMap.get(assignment.batchId) ?? null) : null,
    batchRole: assignment.batchRole ?? null,
    vesselId: assignment.vesselId ? (vesselIdMap.get(assignment.vesselId) ?? null) : null
  }
}

export function mapBatchPayload(batch: ExportDocument['batches'][number]): {
  payload: Record<string, unknown>
  archived: boolean
} {
  const payload: Record<string, unknown> = { ...batch }
  const archived = batch.status === 'archived'
  if (archived) payload.status = 'fermenting'
  delete payload.id
  delete payload.gravityReadings
  delete payload.pressureReadings
  delete payload.temperatureReadings
  delete payload.fermentation
  delete payload.fermentationSteps
  delete payload.fermentationChamber
  // dryHops intentionally stays in the payload; BatchCreate persists them.
  return { payload, archived }
}

type ChipReading = { deviceChipId?: string | null }

export function mapBatchReading<T extends ChipReading>(
  reading: T,
  batchId: string,
  chipToNew: Map<string, string>
): Omit<T, 'deviceChipId'> & { batchId: string; deviceId: string | null } {
  const { deviceChipId, ...rest } = reading
  return {
    ...rest,
    batchId,
    deviceId: deviceChipId ? (chipToNew.get(deviceChipId) ?? null) : null
  }
}

export function mapTapPayload(tap: BrewGraphTapRecord): Record<string, unknown> {
  return { name: tap.name, tapNumber: tap.tapNumber, location: tap.location, notes: tap.notes }
}

export function mapVesselPayload(
  vessel: BrewGraphVesselRecord,
  batchIdMap: Map<string, string>,
  tapIdMap: Map<string, string>
): Record<string, unknown> {
  return {
    batchId: vessel.batchId ? (batchIdMap.get(vessel.batchId) ?? null) : null,
    tapId: vessel.tapId ? (tapIdMap.get(vessel.tapId) ?? null) : null,
    vesselNumber: vessel.vesselNumber ?? null,
    vesselType: vessel.vesselType,
    name: vessel.name,
    fillDate: vessel.fillDate,
    totalVolume: vessel.totalVolume,
    volumeRemaining: vessel.volumeRemaining,
    bottleVolume: vessel.bottleVolume,
    bottleCount: vessel.bottleCount,
    bottlesRemaining: vessel.bottlesRemaining,
    status: vessel.status,
    location: vessel.location,
    notes: vessel.notes
  }
}

export function mapPourEvent(event: BrewGraphVesselRecord['pourEvents'][number]) {
  return {
    pourAmount: event.pourAmount,
    volumeRemaining: event.volumeRemaining,
    isManual: event.isManual ?? false,
    createdAt: event.createdAt
  }
}

export function mapVesselReading<T extends ChipReading>(
  reading: T,
  vesselId: string,
  chipToNew: Map<string, string>
): Omit<T, 'deviceChipId'> & { vesselId: string; deviceId: string | null } {
  const { deviceChipId, ...rest } = reading
  return {
    ...rest,
    vesselId,
    deviceId: deviceChipId ? (chipToNew.get(deviceChipId) ?? null) : null
  }
}
