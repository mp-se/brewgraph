/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import type { apiFetch } from '@/modules/apiClient'

type CsvValue = string | number | boolean | null | undefined

interface BatchCsvBatch {
  name: string
}

interface ExportReading {
  createdAt?: CsvValue
  temperature?: CsvValue
  gravity?: CsvValue
  angle?: CsvValue
  battery?: CsvValue
  rssi?: CsvValue
  corrGravity?: CsvValue
  runTime?: CsvValue
  chamberTemperature?: CsvValue
  beerTemperature?: CsvValue
  velocity?: CsvValue
  pressure?: CsvValue
  pressure1?: CsvValue
  tempType?: CsvValue
  excluded?: CsvValue
}

interface BatchCsvGlobal {
  messageError: string
}

interface BatchCsvExportDependencies {
  apiFetch: typeof apiFetch
  gravityStore: {
    getGravityListForBatch: (id: string) => Promise<ExportReading[] | null>
  }
  pressureStore: {
    getPressureListForBatch: (id: string) => Promise<ExportReading[] | null>
  }
  tempReadingStore: {
    getTempListForBatch: (id: string) => Promise<ExportReading[] | null>
  }
  download: (content: string, mimeType: string, filename: string) => void
  global: BatchCsvGlobal
  logDebug: (message: string, ...args: unknown[]) => void
  logError: (message: string, ...args: unknown[]) => void
}

const csvValue = (value: CsvValue): string | number | boolean => value ?? ''

/**
 * Create the per-batch CSV export actions. API, stores, download and UI state
 * are injected so data collection/serialization can be tested without mounting
 * the list view or relying on browser download behavior.
 */
export function createBatchCsvExports({
  apiFetch,
  gravityStore,
  pressureStore,
  tempReadingStore,
  download,
  global,
  logDebug,
  logError
}: BatchCsvExportDependencies) {
  async function getBatch(id: string): Promise<BatchCsvBatch | false> {
    try {
      const res = await apiFetch('GET', 'batches/' + id)
      logDebug('BatchListView.getBatch()', res.status)
      if (!res.ok) throw res
      return (await res.json()) as BatchCsvBatch
    } catch (err) {
      logError('BatchListView.getBatch()', err)
      return false
    }
  }

  async function loadReadings(
    id: string,
    kind: string,
    getReadings: (batchId: string) => Promise<ExportReading[] | null>
  ): Promise<{ batch: BatchCsvBatch; readings: ExportReading[] } | null> {
    const batch = await getBatch(id)
    if (!batch) {
      global.messageError = 'Failed to fetch batch with id ' + id
      return null
    }

    const readings = await getReadings(id)
    if (!Array.isArray(readings)) {
      global.messageError = 'Failed to fetch ' + kind + ' readings for batch ' + id
      return null
    }
    if (readings.length === 0) {
      global.messageError = 'There are no ' + kind + ' readings to export for batch ' + id
      return null
    }
    return { batch, readings }
  }

  async function exportBatchGravityCSV(id: string): Promise<void> {
    logDebug('BatchListView.exportBatchGravityCSV()', id)
    const result = await loadReadings(id, 'gravity', (batchId) =>
      gravityStore.getGravityListForBatch(batchId)
    )
    if (!result) return

    const { batch, readings } = result
    logDebug('BatchListView.exportBatchGravityCSV()', 'Collected batch readings')
    const rows = readings.map((reading) => [
      batch.name,
      reading.createdAt,
      reading.temperature,
      reading.gravity,
      reading.angle,
      reading.battery,
      reading.rssi,
      reading.corrGravity,
      reading.runTime,
      reading.chamberTemperature,
      reading.beerTemperature,
      reading.velocity
    ])
    const csv = [
      'Name,Created,Temperature,Gravity,Angle,Battery,RSSI,CorrGravity,RunTime,ChamberTemperature,BeerTemperature,GravityVelocity',
      ...rows.map((row) => row.map(csvValue).join(','))
    ].join('\n') + '\n'
    download(csv, 'text/csv', 'brewgraph_gravity_batch_' + id + '.csv')
  }

  async function exportBatchPressureCSV(id: string): Promise<void> {
    logDebug('BatchListView.exportBatchPressureCSV()', id)
    const result = await loadReadings(id, 'pressure', (batchId) =>
      pressureStore.getPressureListForBatch(batchId)
    )
    if (!result) return

    const { batch, readings } = result
    logDebug('BatchListView.exportBatchPressureCSV()', 'Collected batch readings')
    const rows = readings.map((reading) => [
      batch.name,
      reading.createdAt,
      reading.temperature,
      reading.pressure,
      reading.pressure1,
      reading.battery,
      reading.rssi,
      reading.runTime
    ])
    const csv = [
      'Name,Created,Temperature,Pressure,Pressure1,Battery,RSSI,RunTime',
      ...rows.map((row) => row.map(csvValue).join(','))
    ].join('\n') + '\n'
    download(csv, 'text/csv', 'brewgraph_pressure_batch_' + id + '.csv')
  }

  async function exportBatchTemperatureCSV(id: string): Promise<void> {
    logDebug('BatchListView.exportBatchTemperatureCSV()', id)
    const result = await loadReadings(id, 'temperature', (batchId) =>
      tempReadingStore.getTempListForBatch(batchId)
    )
    if (!result) return

    const { batch, readings } = result
    const rows = readings.map((reading) => [
      batch.name,
      reading.createdAt,
      reading.temperature,
      reading.tempType,
      reading.battery,
      reading.rssi,
      reading.excluded
    ])
    const csv = [
      'Name,Created,Temperature,Probe,Battery,RSSI,Excluded',
      ...rows.map((row) => row.map(csvValue).join(','))
    ].join('\n') + '\n'
    download(csv, 'text/csv', 'brewgraph_temperature_batch_' + id + '.csv')
  }

  return { exportBatchGravityCSV, exportBatchPressureCSV, exportBatchTemperatureCSV }
}
