/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { processBrewGraphRestore, rejectionReason } from '../brewgraphRestore'

vi.mock('@/ui', () => ({
  logDebug: vi.fn(),
  logInfo: vi.fn(),
  logError: vi.fn()
}))

const BASE_DEPS = {
  baseURL: 'http://test/',
  token: 'Bearer t',
  onProgress: vi.fn(),
  refreshDevices: vi.fn().mockResolvedValue(true),
  refreshBatches: vi.fn().mockResolvedValue(true)
}

// Named for what it holds, not for a retired file version: a
// brewgraph-batch-export-v1 document in `backup` mode, carrying taps and vessels.
function makeBackupWithVessels(overrides = {}) {
  return {
    schemaVersion: '1',
    exportedAt: '2026-01-01T00:00:00Z',
    source: 'oss',
    mode: 'backup',
    settings: {},
    devices: [],
    batches: [],
    taps: [{ id: 'tap-1', name: 'Tap 1', tapNumber: 1, location: 'Bar', notes: '' }],
    vessels: [
      {
        id: 'v-1',
        batchId: 'b-1',
        tapId: 'tap-1',
        vesselNumber: 1,
        vesselType: 'keg',
        name: 'Keg 1',
        fillDate: '2026-01-01',
        totalVolume: 19,
        volumeRemaining: 15,
        bottleVolume: null,
        bottleCount: null,
        bottlesRemaining: null,
        status: 'serving',
        location: '',
        notes: '',
        pourEvents: [
          {
            id: 'pe-1',
            vesselId: 'v-1',
            pourAmount: 0.5,
            volumeRemaining: 14.5,
            isManual: false,
            excluded: false,
            createdAt: '2026-01-02T10:00:00'
          }
        ]
      }
    ],
    ...overrides
  }
}

// A minimal backup document: one device, one batch, no taps or vessels.
function makeMinimalBackup() {
  return {
    schemaVersion: '1',
    exportedAt: '2026-01-01T00:00:00Z',
    source: 'oss',
    mode: 'backup',
    settings: {},
    devices: [{ id: 'd-1', chipId: 'chip1', name: 'Dev1' }],
    batches: [
      {
        id: 'b-1',
        name: 'Batch 1',
        desc: 'desc',
        status: 'fermenting',
        gravityDeviceId: 'd-1',
        pressureDeviceId: null,
        chamberDeviceId: null,
        brewDate: '2026-01-01',
        style: 'IPA',
        brewer: 'Magnus',
        abv: 5,
        ebc: 10,
        ibu: 20,
        fg: 1.01,
        og: 1.055,
        carbonationVolumes: null,
        brewfatherBatchId: '',
        notes: '',
        fermentationChamber: null,
        // An array, not the batch record's serialised-JSON string. No producer
        // emits a string here — `normaliseFermentationSteps` converts on the way
        // out — so the old `''` described a document that cannot exist. It went
        // unnoticed because the restore deletes this key before posting.
        fermentationSteps: [],
        gravityReadings: [],
        pressureReadings: []
      }
    ],
    taps: [],
    vessels: []
  }
}

// Build a flexible fetch mock from an array of response specs or a handler fn
function buildFetchMock(responses) {
  let call = 0
  return vi.fn().mockImplementation((url, opts) => {
    const r = typeof responses === 'function' ? responses(url, opts, call++) : responses[call++]
    if (!r) {
      // default: 204 for DELETE, 200 JSON {} for others
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    }
    if (r instanceof Error) return Promise.reject(r)
    return Promise.resolve({
      ok: r.ok ?? true,
      status: r.status ?? 200,
      json: () => Promise.resolve(r.body ?? {})
    })
  })
}

describe('processBrewGraphRestore', () => {
  let deps

  beforeEach(() => {
    deps = {
      ...BASE_DEPS,
      onProgress: vi.fn(),
      refreshDevices: vi.fn().mockResolvedValue(true),
      refreshBatches: vi.fn().mockResolvedValue(true)
    }
  })

  it('processes a v1 backup (no taps/vessels)', async () => {
    const backup = makeMinimalBackup()

    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('devices')) return { body: [] }
        if (url.includes('vessels')) return { body: [] }
        if (url.includes('taps')) return { body: [] }
        if (url.includes('batches')) return { body: { items: [], pages: 1 } }
        return { body: [] }
      }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST') return { body: { id: 'new-id' } }
      return { body: {} }
    })

    await expect(processBrewGraphRestore(backup, deps)).resolves.toBeDefined()
    expect(deps.refreshDevices).toHaveBeenCalled()
    expect(deps.refreshBatches).toHaveBeenCalled()
  })

  it('processes a v2 backup (has taps + vessels)', async () => {
    const backup = makeBackupWithVessels()

    const refreshTaps = vi.fn().mockResolvedValue(undefined)
    const refreshVessels = vi.fn().mockResolvedValue(undefined)
    deps.refreshTaps = refreshTaps
    deps.refreshVessels = refreshVessels

    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('devices')) return { body: [] }
        if (url.includes('vessels') && !url.includes('pours')) return { body: [] }
        if (url.includes('taps')) return { body: [] }
        if (url.includes('batches')) return { body: { items: [], pages: 1 } }
        return { body: [] }
      }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST') {
        if (url.includes('vessels') && url.includes('/pours/bulk')) return { ok: true, body: {} }
        if (url.includes('vessels')) return { body: { id: 'new-vessel' } }
        if (url.includes('taps')) return { body: { id: 'new-tap' } }
        return { body: { id: 'new-id' } }
      }
      return { body: {} }
    })

    await expect(processBrewGraphRestore(backup, deps)).resolves.toBeDefined()
    expect(refreshTaps).toHaveBeenCalled()
    expect(refreshVessels).toHaveBeenCalled()
  })

  it('calls refreshTaps only if defined for v2 backup', async () => {
    const backup = makeBackupWithVessels({ vessels: [], taps: [] })
    // No refreshTaps or refreshVessels in deps

    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') return { body: [] }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      return { body: { id: 'new-id' } }
    })

    await expect(processBrewGraphRestore(backup, deps)).resolves.toBeDefined()
    // No crash without optional refreshTaps/refreshVessels
  })

  it('logs error when refreshDevices returns false', async () => {
    const backup = makeMinimalBackup()
    deps.refreshDevices = vi.fn().mockResolvedValue(false)
    deps.refreshBatches = vi.fn().mockResolvedValue(true)

    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('batches')) return { body: { items: [], pages: 1 } }
        return { body: [] }
      }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      return { body: { id: 'new-id' } }
    })

    const { logError } = await import('@/ui')
    await processBrewGraphRestore(backup, deps)
    expect(logError).toHaveBeenCalledWith(
      expect.stringContaining('processBrewGraphRestore'),
      expect.stringContaining('device')
    )
  })

  it('handles deleteAll with paginated batches', async () => {
    const backup = makeMinimalBackup()
    backup.devices = []
    backup.batches = []

    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('batches') && !url.includes('page=')) {
          // First page returns 2 pages
          return { body: { items: [{ id: '1' }], pages: 2 } }
        }
        if (url.includes('batches') && url.includes('page=2')) {
          return { body: { items: [{ id: '2' }], pages: 2 } }
        }
        return { body: [] }
      }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      return { body: { id: 'new-id' } }
    })

    await expect(processBrewGraphRestore(backup, deps)).resolves.toBeDefined()
  })

  /*
   * Regression: deleteAll() used to build the per-id DELETE url as `url + id`
   * with no separator, so a resource collection url with no trailing slash
   * (e.g. `.../api/devices`) produced `.../api/devicesd-1` instead of
   * `.../api/devices/d-1`. That 404s, deleteAll() logs it and moves on, and
   * restore proceeds to recreate every entity anyway — so a restore run twice
   * silently doubled the data instead of replacing it.
   */
  it('deletes existing entities at a properly-separated url before restoring', async () => {
    const backup = makeMinimalBackup()
    backup.devices = []
    backup.batches = []
    const deleteUrls = []

    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('devices')) return { body: [{ id: 'd-1' }] }
        if (url.includes('vessels')) return { body: [{ id: 'v-1' }] }
        if (url.includes('taps')) return { body: [{ id: 't-1' }] }
        if (url.includes('batches')) return { body: { items: [{ id: 'b-1' }], pages: 1 } }
        return { body: [] }
      }
      if (method === 'DELETE') {
        deleteUrls.push(url)
        return { ok: true, status: 204, body: null }
      }
      return { body: { id: 'new-id' } }
    })

    await processBrewGraphRestore(backup, deps)

    expect(deleteUrls).toEqual(
      expect.arrayContaining([
        expect.stringMatching(/\/devices\/d-1$/),
        expect.stringMatching(/\/vessels\/v-1$/),
        expect.stringMatching(/\/taps\/t-1$/),
        expect.stringMatching(/\/batches\/b-1$/)
      ])
    )
    // None of the ids concatenated straight onto the collection name.
    for (const url of deleteUrls) {
      expect(url).not.toMatch(/(devices|vessels|taps|batches)[a-z0-9-]+$/i)
    }
  })

  /*
   * Regression: deleteAll() only soft-deletes (that's what DELETE .../{id} does
   * on the backend). A soft-deleted row still occupies its unique constraints
   * (a device's device_type+chip_id, its token, ...), so recreating the same
   * device below would conflict unless the soft-deleted rows are hard-purged
   * first.
   */
  it('purges soft-deleted data after the deletes and before recreating anything', async () => {
    const backup = makeMinimalBackup()
    const calls = []

    global.fetch = buildFetchMock((url, opts) => {
      calls.push({ url, method: opts?.method })
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('batches')) return { body: { items: [], pages: 1 } }
        return { body: [] }
      }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      return { body: { id: 'new-id' } }
    })

    await processBrewGraphRestore(backup, deps)

    const purgeIndex = calls.findIndex(
      (c) => c.method === 'POST' && c.url.includes('system/purge-deleted')
    )
    const firstCreateIndex = calls.findIndex(
      (c) => c.method === 'POST' && c.url.includes('api/devices')
    )
    expect(purgeIndex).toBeGreaterThan(-1)
    expect(purgeIndex).toBeLessThan(firstCreateIndex)
  })

  it('aborts before recreating anything when purge-deleted fails', async () => {
    const backup = makeMinimalBackup()

    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('batches')) return { body: { items: [], pages: 1 } }
        return { body: [] }
      }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST' && url.includes('system/purge-deleted')) {
        return { ok: false, status: 500, body: {} }
      }
      return { body: { id: 'new-id' } }
    })

    await expect(processBrewGraphRestore(backup, deps)).rejects.toThrow(
      /Could not clear existing data/
    )
    expect(
      global.fetch.mock.calls.some(([url, opts]) => {
        return opts?.method === 'POST' && url.includes('api/devices')
      })
    ).toBe(false)
  })

  it('restores the role of a device that is not assigned to a batch or vessel', async () => {
    const backup = makeMinimalBackup()
    backup.devices = [{ id: 'd1', chipId: 'chip1', name: 'Dev1', batchRole: 'gravity' }]
    backup.batches = []
    const patches = []
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('batches')) return { body: { items: [], pages: 1 } }
        return { body: [] }
      }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'PATCH') patches.push({ url, body: JSON.parse(opts.body) })
      return { body: { id: 'new-id' } }
    })
    await processBrewGraphRestore(backup, deps)
    const devicePatch = patches.find((p) => p.url.includes('devices/new-id'))
    expect(devicePatch?.body).toEqual({ batchId: null, batchRole: 'gravity', vesselId: null })
  })

  it('logs error and continues when device POST fails', async () => {
    const backup = makeMinimalBackup()
    backup.devices = [{ id: 'd1', chipId: 'chip1', name: 'Dev1' }] // no fermentationStep
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('batches')) return { body: { items: [], pages: 1 } }
        return { body: [] }
      }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST' && url.includes('devices')) return { ok: false, status: 422, body: {} }
      return { body: { id: 'new-id' } }
    })
    await expect(processBrewGraphRestore(backup, deps)).resolves.toBeDefined()
  })

  it('logs error when refreshBatches returns false', async () => {
    const backup = makeMinimalBackup()
    backup.devices = []
    backup.batches = []
    deps.refreshBatches = vi.fn().mockResolvedValue(false)
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') return { body: [] }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      return { body: { id: 'new-id' } }
    })
    const { logError } = await import('@/ui')
    await processBrewGraphRestore(backup, deps)
    expect(logError).toHaveBeenCalledWith(
      expect.stringContaining('processBrewGraphRestore'),
      expect.stringContaining('batch')
    )
  })

  it('posts gravity and pressure bulk for batches with readings', async () => {
    const backup = makeMinimalBackup()
    backup.batches[0].gravityReadings = [
      { id: 'g1', batchId: 'b1', gravity: 1.05, createdAt: '2026-01-01' }
    ]
    backup.batches[0].pressureReadings = [
      { id: 'p1', batchId: 'b1', pressure: 12, createdAt: '2026-01-01' }
    ]
    backup.devices = []
    let gravityBulkCalled = false
    let pressureBulkCalled = false
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('batches')) return { body: { items: [], pages: 1 } }
        return { body: [] }
      }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST') {
        if (url.includes('/gravity/bulk')) {
          gravityBulkCalled = true
          return { ok: true, body: {} }
        }
        if (url.includes('/pressure/bulk')) {
          pressureBulkCalled = true
          return { ok: true, body: {} }
        }
        return { body: { id: 'new-id' } }
      }
      return { body: {} }
    })
    await processBrewGraphRestore(backup, deps)
    expect(gravityBulkCalled).toBe(true)
    expect(pressureBulkCalled).toBe(true)
  })

  it('counts a rejected batch\'s readings as failed, not silently dropped', async () => {
    const backup = makeMinimalBackup()
    backup.batches[0].gravityReadings = [
      { id: 'g1', batchId: 'b1', gravity: 1.05, createdAt: '2026-01-01' },
      { id: 'g2', batchId: 'b1', gravity: 1.04, createdAt: '2026-01-02' }
    ]
    backup.batches[0].pressureReadings = [
      { id: 'p1', batchId: 'b1', pressure: 12, createdAt: '2026-01-01' }
    ]
    backup.devices = []
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') return { body: { items: [], pages: 1 } }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST' && url.endsWith('api/batches')) return { ok: false, status: 422 }
      return { body: { id: 'new-id' } }
    })
    const report = await processBrewGraphRestore(backup, deps)
    expect(report.batches).toEqual({ restored: 0, failed: 1 })
    expect(report.readings).toEqual({ restored: 0, failed: 3 })
    expect(report.problems).toEqual([
      `batch "${backup.batches[0].name}": the server rejected its data as invalid`
    ])
  })

  it('preserves null fg and og instead of coercing to 0', async () => {
    // Coercing to 0 would silently turn "not yet measured" into "measured as
    // zero" — a real, wrong value, not a missing one.
    const backup = makeMinimalBackup()
    backup.batches[0].fg = null
    backup.batches[0].og = null
    backup.devices = []
    let postedBatchPayload = null
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('batches')) return { body: { items: [], pages: 1 } }
        return { body: [] }
      }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST' && url.endsWith('/api/batches')) {
        postedBatchPayload = JSON.parse(opts.body)
        return { body: { id: 'new-id' } }
      }
      return { body: { id: 'new-id' } }
    })
    await expect(processBrewGraphRestore(backup, deps)).resolves.toBeDefined()
    expect(postedBatchPayload.fg).toBeNull()
    expect(postedBatchPayload.og).toBeNull()
  })

  it('keeps dryHops in the batch payload so BatchCreate can restore them', async () => {
    // Deleting `dryHops` before posting, as this used to, meant an exported
    // batch's dry hops were never restored at all.
    const backup = makeMinimalBackup()
    backup.batches[0].dryHops = [{ name: 'Citra', amount: 50, triggerMethod: 'hours_before_completion', triggerHoursBefore: 24 }]
    backup.devices = []
    let postedBatchPayload = null
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('batches')) return { body: { items: [], pages: 1 } }
        return { body: [] }
      }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST' && url.endsWith('/api/batches')) {
        postedBatchPayload = JSON.parse(opts.body)
        return { body: { id: 'new-id' } }
      }
      return { body: { id: 'new-id' } }
    })
    await processBrewGraphRestore(backup, deps)
    expect(postedBatchPayload.dryHops).toEqual([
      { name: 'Citra', amount: 50, triggerMethod: 'hours_before_completion', triggerHoursBefore: 24 }
    ])
  })

  it('posts temperature bulk for batches with temperature readings', async () => {
    const backup = makeMinimalBackup()
    backup.batches[0].temperatureReadings = [
      { deviceChipId: null, temperature: 18.5, tempType: 'beer', createdAt: '2026-01-01' }
    ]
    backup.devices = []
    let tempBulkCalled = false
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('batches')) return { body: { items: [], pages: 1 } }
        return { body: [] }
      }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST') {
        if (url.includes('/temp/bulk')) {
          tempBulkCalled = true
          return { ok: true, body: {} }
        }
        return { body: { id: 'new-id' } }
      }
      return { body: {} }
    })
    const report = await processBrewGraphRestore(backup, deps)
    expect(tempBulkCalled).toBe(true)
    expect(report.readings.restored).toBe(1)
  })

  it('chunks a reading array above 1,000 items into multiple bulk POSTs', async () => {
    const backup = makeMinimalBackup()
    backup.batches[0].gravityReadings = Array.from({ length: 1500 }, (_, i) => ({
      deviceChipId: null,
      gravity: 1.05,
      createdAt: `2026-01-01T00:00:${String(i % 60).padStart(2, '0')}Z`
    }))
    backup.devices = []
    let gravityBulkCalls = 0
    let lastChunkSize = 0
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('batches')) return { body: { items: [], pages: 1 } }
        return { body: [] }
      }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST') {
        if (url.includes('/gravity/bulk')) {
          gravityBulkCalls++
          lastChunkSize = JSON.parse(opts.body).length
          return { ok: true, body: {} }
        }
        return { body: { id: 'new-id' } }
      }
      return { body: {} }
    })
    const report = await processBrewGraphRestore(backup, deps)
    expect(gravityBulkCalls).toBe(2)
    expect(lastChunkSize).toBe(500)
    expect(report.readings.restored).toBe(1500)
  })

  it('counts a rejected bulk chunk as failed rather than dropping it silently', async () => {
    const backup = makeMinimalBackup()
    backup.batches[0].pressureReadings = [
      { deviceChipId: null, pressure: 10, createdAt: '2026-01-01' }
    ]
    backup.devices = []
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('batches')) return { body: { items: [], pages: 1 } }
        return { body: [] }
      }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST') {
        if (url.includes('/pressure/bulk')) return { ok: false, status: 422, body: {} }
        return { body: { id: 'new-id' } }
      }
      return { body: {} }
    })
    const report = await processBrewGraphRestore(backup, deps)
    expect(report.readings.failed).toBe(1)
    expect(report.readings.restored).toBe(0)
  })

  it('aborts before purging when a delete fails, per the recoverable-restore invariant', async () => {
    const backup = makeMinimalBackup()
    backup.devices = []
    backup.batches = []
    let purgeCalled = false
    let createCalled = false
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('devices')) return { body: [{ id: 'd-1' }] }
        return { body: [] }
      }
      if (method === 'DELETE') {
        if (url.includes('/devices/d-1')) return { ok: false, status: 500, body: null }
        return { ok: true, status: 204, body: null }
      }
      if (method === 'POST') {
        if (url.includes('system/purge-deleted')) purgeCalled = true
        if (url.includes('api/devices')) createCalled = true
        return { body: { id: 'new-id' } }
      }
      return { body: {} }
    })
    await expect(processBrewGraphRestore(backup, deps)).rejects.toThrow(/Could not delete existing data/)
    expect(purgeCalled).toBe(false)
    expect(createCalled).toBe(false)
  })

  it('restores vessel temperature and pressure history, relinked by device chip', async () => {
    const backup = makeBackupWithVessels()
    backup.vessels[0].temperatureReadings = [
      { deviceChipId: null, temperature: 19, tempType: 'chamber', createdAt: '2026-01-01' }
    ]
    backup.vessels[0].pressureReadings = [
      { deviceChipId: null, pressure: 8, createdAt: '2026-01-01' }
    ]
    deps.refreshTaps = vi.fn().mockResolvedValue(undefined)
    deps.refreshVessels = vi.fn().mockResolvedValue(undefined)
    let vesselTempBulkCalled = false
    let vesselPressureBulkCalled = false
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') return { body: [] }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST') {
        if (url.includes('vessels') && url.includes('/temp/bulk')) {
          vesselTempBulkCalled = true
          return { ok: true, body: {} }
        }
        if (url.includes('vessels') && url.includes('/pressure/bulk')) {
          vesselPressureBulkCalled = true
          return { ok: true, body: {} }
        }
        if (url.includes('vessels') && !url.includes('/pours')) return { body: { id: 'nv' } }
        if (url.includes('taps')) return { body: { id: 'nt' } }
        if (url.includes('/pours/bulk')) return { ok: true, body: {} }
        return { body: { id: 'new-id' } }
      }
      return { body: {} }
    })
    const report = await processBrewGraphRestore(backup, deps)
    expect(vesselTempBulkCalled).toBe(true)
    expect(vesselPressureBulkCalled).toBe(true)
    expect(report.readings.restored).toBe(2)
  })

  it('handles vessel POST failure gracefully', async () => {
    const backup = makeBackupWithVessels()
    deps.refreshTaps = vi.fn().mockResolvedValue(undefined)
    deps.refreshVessels = vi.fn().mockResolvedValue(undefined)
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') return { body: [] }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST') {
        if (url.includes('vessels') && !url.includes('/pours') && !url.includes('/token')) {
          return { ok: false, status: 422, body: {} }
        }
        if (url.includes('taps')) return { body: { id: 'new-tap' } }
        return { body: { id: 'new-id' } }
      }
      return { body: {} }
    })
    const report = await processBrewGraphRestore(backup, deps)
    expect(report.vessels.failed).toBe(1)
    // The vessel's pour history is lost with it and must show in the report.
    expect(report.pours).toEqual({ restored: 0, failed: 1 })
    expect(report.problems).toEqual([
      `vessel "${backup.vessels[0].name}": the server rejected its data as invalid`
    ])
  })

  it('reports a rejected tap and continues the restore', async () => {
    const backup = makeMinimalBackup()
    backup.devices = []
    backup.batches = []
    backup.taps = [{ id: 't-1', name: 'Tap 1', tapNumber: 1, location: '', notes: '' }]
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') return { body: [] }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST' && url.endsWith('/taps')) return { ok: false, status: 422 }
      return { body: { id: 'new-id' } }
    })

    const report = await processBrewGraphRestore(backup, deps)

    expect(report.taps).toEqual({ restored: 0, failed: 1 })
    expect(report.problems).toContain('tap "Tap 1": the server rejected its data as invalid')
    expect(deps.onProgress).toHaveBeenCalled()
  })

  it('names rejected readings once per collection, not once per chunk', async () => {
    const backup = makeMinimalBackup()
    backup.batches[0].gravityReadings = Array.from({ length: 1500 }, (_, i) => ({
      id: 'g' + i,
      batchId: 'b1',
      gravity: 1.05,
      createdAt: '2026-01-01'
    }))
    backup.devices = []
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') return { body: { items: [], pages: 1 } }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (url.includes('/gravity/bulk')) return { ok: false, status: 500 }
      return { body: { id: 'new-id' } }
    })
    const report = await processBrewGraphRestore(backup, deps)
    expect(report.readings.failed).toBe(1500)
    expect(report.problems).toEqual([
      `1500 of 1500 gravity readings of batch "${backup.batches[0].name}": server error`
    ])
  })

  it('restores an archived batch with its readings, archiving it last', async () => {
    // The API refuses reading writes to an archived batch (404 "Batch not found"),
    // so creating it archived loses every reading.
    const backup = makeMinimalBackup()
    backup.devices = []
    backup.batches[0].status = 'archived'
    backup.batches[0].gravityReadings = [
      { id: 'g1', batchId: 'b1', gravity: 1.05, createdAt: '2026-01-01' }
    ]
    let serverStatus = null
    const order = []
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') return { body: { items: [], pages: 1 } }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST' && url.endsWith('api/batches')) {
        serverStatus = JSON.parse(opts.body).status
        return { body: { id: 'nb' } }
      }
      if (url.includes('/gravity/bulk')) {
        order.push('readings')
        return serverStatus === 'archived' ? { ok: false, status: 404 } : { body: {} }
      }
      if (method === 'PATCH' && url.endsWith('batches/nb')) {
        order.push('archive')
        serverStatus = JSON.parse(opts.body).status
        return { body: {} }
      }
      return { body: { id: 'x' } }
    })

    const report = await processBrewGraphRestore(backup, deps)

    expect(report.readings).toEqual({ restored: 1, failed: 0 })
    expect(report.problems).toEqual([])
    expect(order).toEqual(['readings', 'archive'])
    expect(serverStatus).toBe('archived')
  })

  it('reports a batch that could not be re-archived', async () => {
    const backup = makeMinimalBackup()
    backup.devices = []
    backup.batches[0].status = 'archived'
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') return { body: { items: [], pages: 1 } }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'PATCH') return { ok: false, status: 400 }
      return { body: { id: 'nb' } }
    })

    const report = await processBrewGraphRestore(backup, deps)
    expect(report.batches.restored).toBe(1)
    expect(report.problems).toEqual([
      `archiving batch "${backup.batches[0].name}" (it was restored as fermenting): ` +
        'the server rejected its data as invalid'
    ])
  })

  it('describes each rejection status in plain words', () => {
    expect(rejectionReason(422)).toBe('the server rejected its data as invalid')
    expect(rejectionReason(409)).toBe('it conflicts with data already on the server')
    expect(rejectionReason(403)).toBe('not authorized')
    expect(rejectionReason(503)).toBe('server error')
    expect(rejectionReason(418)).toBe('unexpected response 418')
  })

  it('never requests a vessel token on restore', async () => {
    // Vessels have no token; integration/QR flows use the tap token, which survives keg swaps.
    // See spec-data-model.md §5.11.
    const backup = makeBackupWithVessels()
    deps.refreshTaps = vi.fn().mockResolvedValue(undefined)
    deps.refreshVessels = vi.fn().mockResolvedValue(undefined)
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') return { body: [] }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST') {
        if (url.includes('vessels') && !url.includes('/pours')) return { body: { id: 'nv' } }
        if (url.includes('taps')) return { body: { id: 'nt' } }
        if (url.includes('/pours/bulk')) return { ok: true, body: {} }
        return { body: { id: 'new-id' } }
      }
      return { body: {} }
    })
    await processBrewGraphRestore(backup, deps)
    const calledUrls = global.fetch.mock.calls.map((c) => c[0])
    expect(calledUrls.some((u) => u.includes('/token'))).toBe(false)
  })

  it('handles missing devices/batches/taps/vessels fields in backup', async () => {
    const backup = { schemaVersion: '1', mode: 'backup', source: 'oss', settings: {} }
    deps.refreshTaps = vi.fn().mockResolvedValue(undefined)
    deps.refreshVessels = vi.fn().mockResolvedValue(undefined)
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') {
        if (url.includes('batches')) return { body: { items: [], pages: 1 } }
        return { body: [] }
      }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      return { body: { id: 'new-id' } }
    })
    await expect(processBrewGraphRestore(backup, deps)).resolves.toBeDefined()
  })

  it('handles vessel with tapId=null (no tap lookup)', async () => {
    const backup = makeBackupWithVessels({
      taps: [],
      vessels: [
        {
          id: 'v-1',
          batchId: '',
          tapId: null,
          vesselNumber: null,
          vesselType: 'keg',
          name: 'Keg',
          fillDate: '2026-01-01',
          totalVolume: 19,
          volumeRemaining: 15,
          bottleVolume: null,
          bottleCount: null,
          bottlesRemaining: null,
          status: 'serving',
          location: '',
          notes: '',
          pourEvents: []
        }
      ]
    })
    deps.refreshTaps = vi.fn().mockResolvedValue(undefined)
    deps.refreshVessels = vi.fn().mockResolvedValue(undefined)
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') return { body: [] }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST') {
        if (url.includes('vessels') && !url.includes('/pours') && !url.includes('/token')) {
          return { body: { id: 'nv', token: 'tok' } }
        }
        return { body: { id: 'new-id' } }
      }
      return { body: {} }
    })
    await expect(processBrewGraphRestore(backup, deps)).resolves.toBeDefined()
  })

  it('handles vessel with existing token (no token POST)', async () => {
    const backup = makeBackupWithVessels()
    deps.refreshTaps = vi.fn().mockResolvedValue(undefined)
    deps.refreshVessels = vi.fn().mockResolvedValue(undefined)

    let tokenPostCalled = false
    global.fetch = buildFetchMock((url, opts) => {
      const method = opts?.method
      if (method === 'GET') return { body: [] }
      if (method === 'DELETE') return { ok: true, status: 204, body: null }
      if (method === 'POST') {
        if (url.includes('/token')) {
          tokenPostCalled = true
          return { ok: true, body: {} }
        }
        if (url.includes('vessels')) return { body: { id: 'nv', token: 'existing-token' } }
        if (url.includes('taps')) return { body: { id: 'nt' } }
        if (url.includes('/pours/bulk')) return { ok: true, body: {} }
        return { body: { id: 'new-id' } }
      }
      return { body: {} }
    })

    await processBrewGraphRestore(backup, deps)
    expect(tokenPostCalled).toBe(false)
  })
})
