/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { restoreBatches, restoreDevices, restoreDeviceAssignments, restoreVessels } from '../restoreEntities'
import { apiPatch, apiPost } from '../restoreApiAdapter'

vi.mock('@/ui', () => ({ logDebug: vi.fn(), logError: vi.fn() }))
vi.mock('../restoreApiAdapter', () => ({ apiPost: vi.fn(), apiPatch: vi.fn() }))

describe('restoreDeviceAssignments', () => {
  beforeEach(() => vi.clearAllMocks())

  it('skips a device when the backup contains no assignment', async () => {
    await restoreDeviceAssignments(
      new Map([['device-1', { batchId: null, batchRole: null, vesselId: null }]]),
      new Map(),
      new Map(),
      'http://test/api/',
      { token: 'token' }
    )

    expect(apiPatch).not.toHaveBeenCalled()
  })

  it('logs a rejected assignment update without aborting restore', async () => {
    vi.mocked(apiPatch).mockResolvedValue({ ok: false, status: 500 })

    await expect(
      restoreDeviceAssignments(
        new Map([['device-1', { batchId: 'old-batch', batchRole: 'gravity', vesselId: null }]]),
        new Map([['old-batch', 'new-batch']]),
        new Map(),
        'http://test/api/',
        { token: 'token' }
      )
    ).resolves.toBeUndefined()

    expect(apiPatch).toHaveBeenCalledWith(
      'http://test/api/devices/device-1',
      'token',
      { batchId: 'new-batch', batchRole: 'gravity', vesselId: null }
    )
  })
})

const makeReport = () => ({
  devices: { restored: 0, failed: 0 },
  batches: { restored: 0, failed: 0 },
  taps: { restored: 0, failed: 0 },
  vessels: { restored: 0, failed: 0 },
  readings: { restored: 0, failed: 0 },
  pours: { restored: 0, failed: 0 },
  problems: []
})

const makeDeps = () => ({
  baseURL: 'http://test/',
  token: 'token',
  onProgress: vi.fn(),
  refreshDevices: vi.fn(),
  refreshBatches: vi.fn()
})

describe('restore entity edge cases', () => {
  beforeEach(() => vi.clearAllMocks())

  it('tracks restored and rejected devices when backup identifiers are optional', async () => {
    vi.mocked(apiPost)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ id: 'new-1' }) })
      .mockResolvedValueOnce({ ok: false, status: 422 })
    const report = makeReport()
    const result = await restoreDevices(
      [
        { id: 'old-1', chipId: 'ABC123', name: 'Sensor' },
        { name: '', chipId: '', id: '' }
      ],
      makeDeps(),
      report
    )

    expect(result.oldToNew.get('old-1')).toBe('new-1')
    expect(result.chipToNew.get('ABC123')).toBe('new-1')
    expect(report.devices).toEqual({ restored: 1, failed: 1 })
  })

  it('accounts for missing readings and notes when restoring batches and vessels', async () => {
    vi.mocked(apiPost)
      .mockResolvedValueOnce({ ok: false, status: 422, text: async () => 'invalid batch' })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ id: 'new-batch' }) })
      .mockResolvedValueOnce({ ok: true }) // note create
    const report = makeReport()
    const batches = await restoreBatches(
      [
        { name: 'Rejected', gravityReadings: null, pressureReadings: null, temperatureReadings: null },
        {
          id: '', name: 'Restored', status: 'fermenting',
          batchNotes: [{ content: '' }, { content: 'A note' }]
        }
      ],
      new Map(),
      makeDeps(),
      report,
      []
    )

    expect(batches.size).toBe(0)
    expect(report.batches).toEqual({ restored: 1, failed: 1 })

    vi.mocked(apiPost)
      .mockResolvedValueOnce({ ok: false, status: 500, text: async () => 'unavailable' })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ id: 'new-vessel' }) })
    const vessels = await restoreVessels(
      [
        { name: 'Rejected keg', pourEvents: null, temperatureReadings: null, pressureReadings: null },
        { name: 'Restored keg', pourEvents: null, temperatureReadings: null, pressureReadings: null }
      ],
      new Map(), new Map(), new Map(), 'http://test/api/', makeDeps(), report
    )

    expect(vessels.size).toBe(0)
    expect(report.vessels).toEqual({ restored: 1, failed: 1 })
  })
})
