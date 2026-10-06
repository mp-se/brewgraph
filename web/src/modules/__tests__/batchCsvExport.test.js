import { describe, expect, it, vi } from 'vitest'
import { createBatchCsvExports } from '../batchCsvExport'

function createHarness() {
  const dependencies = {
    apiFetch: vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: 'batch-1', name: 'Test batch' })
    }),
    gravityStore: { getGravityListForBatch: vi.fn() },
    pressureStore: { getPressureListForBatch: vi.fn() },
    tempReadingStore: { getTempListForBatch: vi.fn() },
    download: vi.fn(),
    global: { messageError: '' },
    logDebug: vi.fn(),
    logError: vi.fn()
  }
  return { dependencies, actions: createBatchCsvExports(dependencies) }
}

describe('batch CSV exports', () => {
  it('exports gravity readings with the established columns and filename', async () => {
    const { dependencies, actions } = createHarness()
    dependencies.gravityStore.getGravityListForBatch.mockResolvedValue([
      { createdAt: '2026-01-01', gravity: 1.05, temperature: 20 }
    ])

    await actions.exportBatchGravityCSV('batch-1')

    expect(dependencies.download).toHaveBeenCalledWith(
      expect.stringContaining('Test batch,2026-01-01,20,1.05'),
      'text/csv',
      'brewgraph_gravity_batch_batch-1.csv'
    )
  })

  it('exports pressure readings with the established filename', async () => {
    const { dependencies, actions } = createHarness()
    dependencies.pressureStore.getPressureListForBatch.mockResolvedValue([
      { createdAt: '2026-01-01', pressure: 12 }
    ])

    await actions.exportBatchPressureCSV('batch-1')

    expect(dependencies.download).toHaveBeenCalledWith(
      expect.stringContaining('Test batch,2026-01-01,,12'),
      'text/csv',
      'brewgraph_pressure_batch_batch-1.csv'
    )
  })

  it('exports temperature readings with the established filename', async () => {
    const { dependencies, actions } = createHarness()
    dependencies.tempReadingStore.getTempListForBatch.mockResolvedValue([
      { createdAt: '2026-01-01', temperature: 19, tempType: 'beer' }
    ])

    await actions.exportBatchTemperatureCSV('batch-1')

    expect(dependencies.download).toHaveBeenCalledWith(
      expect.stringContaining('Test batch,2026-01-01,19,beer'),
      'text/csv',
      'brewgraph_temperature_batch_batch-1.csv'
    )
  })

  it('reports a failed batch request and skips reading collection', async () => {
    const { dependencies, actions } = createHarness()
    dependencies.apiFetch.mockResolvedValue({ ok: false, status: 404 })

    await actions.exportBatchGravityCSV('missing')

    expect(dependencies.global.messageError).toContain('Failed to fetch batch')
    expect(dependencies.gravityStore.getGravityListForBatch).not.toHaveBeenCalled()
    expect(dependencies.download).not.toHaveBeenCalled()
  })

  it.each([undefined, []])('does not download absent or empty reading collections (%s)', async (readings) => {
    const { dependencies, actions } = createHarness()
    dependencies.gravityStore.getGravityListForBatch.mockResolvedValue(readings)

    await actions.exportBatchGravityCSV('batch-1')

    expect(dependencies.global.messageError).toContain('gravity readings')
    expect(dependencies.download).not.toHaveBeenCalled()
  })
})
