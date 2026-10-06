/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

/**
 * Backup → restore must reproduce the dataset, dependencies included.
 *
 * This is the safety net for retiring the 2.0 container without a compatibility
 * branch. `backupCreate` and `brewgraphRestore` each had tests; nothing checked
 * that what one writes the other can read, which is exactly the gap that let the
 * two drift.
 *
 * A backup is a snapshot of the database, so the assertions here are about
 * *dependencies* surviving — devices relinked to their batches and vessels,
 * readings relinked to their devices — not just field-for-field equality.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createBrewGraphBackup } from '../backupCreate'
import { processBrewGraphRestore } from '../brewgraphRestore'

const DEVICE = {
  id: 'dev-old',
  chipId: 'a1b2c3',
  name: 'GravityMon 7',
  chipFamily: 'esp32',
  deviceType: 'gravitymon',
  mdns: 'gravmon.local',
  url: 'http://gravmon.local',
  config: '{"sleep":300}',
  token: 'tok_abc',
  deviceColor: '#ff0000',
  collectLogs: true,
  description: 'Fermenter 1',
  batchId: 'batch-old',
  batchRole: 'gravity',
  vesselId: null
}

const BATCH = {
  id: 'batch-old',
  name: '80. Helles',
  brewDate: '2026-01-02',
  og: 1.048,
  fg: 1.005,
  style: 'German Helles',
  brewer: 'Magnus',
  ebc: 4.6,
  ibu: 28,
  fermentationSteps: '',
  gravity: [
    {
      deviceId: 'dev-old',
      gravity: 1.048,
      temperature: 18.5,
      angle: 25.3,
      velocity: 0.4,
      battery: 4.13,
      rssi: -71,
      runTime: 5,
      excluded: false,
      createdAt: '2026-01-02T10:00:00Z'
    }
  ],
  pressure: []
}

const NOTES = [
  {
    content: 'Dry hopped — 50g Citra',
    createdAt: '2026-01-05T12:00:00Z',
    noteType: 'general',
    testResult: null
  },
  {
    content: 'Diacetyl test clean',
    createdAt: '2026-01-09T09:00:00Z',
    noteType: 'diacetyl_test',
    testResult: 'pass'
  }
]

/** Capture every write the restore makes, keyed by endpoint. */
function makeRestoreRecorder() {
  const posted = {
    devices: [],
    batches: [],
    taps: [],
    vessels: [],
    gravity: [],
    patches: [],
    notes: []
  }
  let nextId = 0

  global.fetch = vi.fn(async (url, opts = {}) => {
    const method = opts.method ?? 'GET'
    const body = opts.body ? JSON.parse(opts.body) : null

    if (method === 'GET') return { ok: true, json: async () => ({ items: [], pages: 1 }) }
    if (method === 'DELETE') return { ok: true, status: 204 }

    if (method === 'PATCH' && url.includes('/devices/')) {
      posted.patches.push({ url, body })
      return { ok: true, json: async () => ({}) }
    }
    if (url.endsWith('/gravity/bulk')) {
      posted.gravity.push(...body)
      return { ok: true, json: async () => ({}) }
    }
    if (url.endsWith('/notes')) {
      posted.notes.push({ url, body })
      return { ok: true, json: async () => ({ id: `note-${++nextId}` }) }
    }
    if (url.endsWith('api/devices')) {
      const id = `dev-new-${++nextId}`
      posted.devices.push(body)
      return { ok: true, json: async () => ({ id }) }
    }
    if (url.endsWith('api/batches')) {
      const id = `batch-new-${++nextId}`
      posted.batches.push(body)
      return { ok: true, json: async () => ({ id }) }
    }
    return { ok: true, status: 200, json: async () => ({ id: `x-${++nextId}` }) }
  })

  return posted
}

const restoreDeps = () => ({
  baseURL: 'http://x/',
  token: 'Bearer t',
  onProgress: vi.fn(),
  refreshDevices: vi.fn().mockResolvedValue(true),
  refreshBatches: vi.fn().mockResolvedValue(true)
})

describe('backup → restore round trip', () => {
  let backup

  beforeEach(async () => {
    global.fetch = vi.fn(async (url) => {
      if (url.includes('tenant/settings')) {
        return { ok: true, json: async () => ({ backupSourceId: 'source-1' }) }
      }
      // Sub-resource endpoints, mocked with the real `CursorPage`/plain-array
      // shapes those endpoints return — BatchResponse/BatchListResponse carry
      // no reading arrays or fermentation-steps field at all, so the backup
      // collector fetches these separately.
      if (url.includes('batches/batch-old/gravity')) {
        return { ok: true, json: async () => ({ items: BATCH.gravity, nextCursor: null, hasMore: false }) }
      }
      if (url.includes('batches/batch-old/pressure')) {
        return { ok: true, json: async () => ({ items: BATCH.pressure, nextCursor: null, hasMore: false }) }
      }
      if (url.includes('batches/batch-old/temp')) {
        return { ok: true, json: async () => ({ items: [], nextCursor: null, hasMore: false }) }
      }
      if (url.includes('batches/batch-old/fermentation-steps')) {
        return { ok: true, json: async () => [] }
      }
      // `GET /batches/{id}/notes` is a `CursorPage[...]`, like the readings above.
      if (url.includes('/notes')) {
        return { ok: true, json: async () => ({ items: NOTES, nextCursor: null, hasMore: false }) }
      }
      // Devices/batches/taps/vessels are `Page[...]` envelopes on the real
      // API, not plain arrays — the collector must handle that envelope shape.
      if (url.includes('devices')) {
        return { ok: true, json: async () => ({ items: [DEVICE], total: 1, page: 1, pageSize: 200, pages: 1 }) }
      }
      if (url.includes('batches?')) {
        return { ok: true, json: async () => ({ items: [BATCH], total: 1, page: 1, pageSize: 200, pages: 1 }) }
      }
      if (url.includes('taps')) return { ok: true, json: async () => ({ items: [], pages: 1 }) }
      if (url.includes('vessels')) return { ok: true, json: async () => ({ items: [], pages: 1 }) }
      return { ok: true, json: async () => null }
    })
    backup = await createBrewGraphBackup({
      baseURL: 'http://x/',
      token: 'Bearer t',
      getBatch: vi.fn().mockResolvedValue(BATCH),
      onProgress: vi.fn()
    })
  })

  it('produces a restorable document', () => {
    expect(backup.schemaVersion).toBe('1')
    expect(backup.mode).toBe('backup')
    expect(backup.batches).toHaveLength(1)
    expect(backup.devices).toHaveLength(1)
  })

  it('carries the device configuration a restore needs', () => {
    const dev = backup.devices[0]
    expect(dev).toMatchObject({
      chipId: 'a1b2c3',
      deviceType: 'gravitymon',
      config: '{"sleep":300}',
      token: 'tok_abc',
      batchId: 'batch-old'
    })
  })

  it('restores devices with their configuration intact', async () => {
    const posted = makeRestoreRecorder()
    await processBrewGraphRestore(backup, restoreDeps())
    expect(posted.devices).toHaveLength(1)
    expect(posted.devices[0]).toMatchObject({
      chipId: 'a1b2c3',
      deviceType: 'gravitymon',
      config: '{"sleep":300}'
    })
  })

  it('relinks devices to their batch after both are recreated', async () => {
    // The whole reason backup mode carries ids. A restore recreates rows with
    // new ids, so the links have to be rebuilt from the old ones.
    const posted = makeRestoreRecorder()
    await processBrewGraphRestore(backup, restoreDeps())
    expect(posted.patches).toHaveLength(1)
    expect(posted.patches[0].body.batchId).toBe('batch-new-2')
    expect(posted.patches[0].body.batchRole).toBe('gravity')
  })

  it('relinks readings to the recreated device by chipId', async () => {
    // Readings reference devices by chipId, which survives the restore. The old
    // deviceId would point at a row that no longer exists.
    const posted = makeRestoreRecorder()
    await processBrewGraphRestore(backup, restoreDeps())
    expect(posted.gravity).toHaveLength(1)
    expect(posted.gravity[0].deviceId).toBe('dev-new-1')
    expect(posted.gravity[0].deviceChipId).toBeUndefined()
  })

  it('carries every reading field through the round trip', async () => {
    const posted = makeRestoreRecorder()
    await processBrewGraphRestore(backup, restoreDeps())
    expect(posted.gravity[0]).toMatchObject({
      gravity: 1.048,
      temperature: 18.5,
      angle: 25.3,
      velocity: 0.4,
      battery: 4.13,
      rssi: -71,
      runTime: 5
    })
  })

  it('carries batch notes through the round trip', async () => {
    /*
     * The round trip is the only place this can be checked properly: the
     * collector must fetch notes so the document carries them, or a restore
     * silently drops every one. Notes are the part of a batch the system
     * cannot reconstruct from measurements — losing a reading loses a
     * sample, losing a note loses what the brewer knew.
     */
    expect(backup.batches[0].batchNotes).toHaveLength(2)

    const posted = makeRestoreRecorder()
    await processBrewGraphRestore(backup, restoreDeps())

    expect(posted.notes).toHaveLength(2)
    // Posted against the *new* batch id — the old one no longer exists.
    expect(posted.notes[0].url).toContain('batches/batch-new-2/notes')
    expect(posted.notes.map((n) => n.body)).toEqual([
      {
        content: 'Dry hopped — 50g Citra',
        createdAt: '2026-01-05T12:00:00Z',
        noteType: 'general'
      },
      {
        content: 'Diacetyl test clean',
        createdAt: '2026-01-09T09:00:00Z',
        noteType: 'diacetyl_test',
        testResult: 'pass'
      }
    ])
  })

  it('restores each note under its original timestamp, not the restore time', async () => {
    // Without an explicit createdAt every restored note would carry the moment of
    // the restore, collapsing a brew log into a single instant and destroying the
    // ordering that makes it readable.
    const posted = makeRestoreRecorder()
    await processBrewGraphRestore(backup, restoreDeps())
    expect(posted.notes.map((n) => n.body.createdAt)).toEqual([
      '2026-01-05T12:00:00Z',
      '2026-01-09T09:00:00Z'
    ])
  })

  it('refuses an ml export, rather than half-restoring from it', async () => {
    // An ml/archive document records what was measured, not what was stored.
    // Restoring from one yields a brewery with every device unconfigured and
    // unlinked, so refusing is the kinder failure.
    makeRestoreRecorder()
    const shallow = { ...backup, mode: 'ml' }
    await expect(processBrewGraphRestore(shallow, restoreDeps())).rejects.toThrow(/backup file/)
  })

  it('refuses a file that is not an export document at all', async () => {
    makeRestoreRecorder()
    await expect(
      processBrewGraphRestore({ meta: { version: '2.0' } }, restoreDeps())
    ).rejects.toThrow(/schemaVersion/)
  })

  it('deletes nothing when the document is malformed past the header', async () => {
    /*
     * The whole reason validation runs where it does.
     *
     * `processBrewGraphRestore` empties every device, vessel, tap and batch before
     * it writes anything, so it must validate the whole body first, not just the
     * header — a file with a valid header and a corrupt body must not be allowed
     * to wipe the database and then fail. A restore that refuses is
     * recoverable; a restore that empties the database and then fails is not.
     *
     * Asserting on the DELETEs specifically, not just the rejection: the throw
     * could move below the deletes and every other test here would still pass.
     */
    const deletes = []
    global.fetch = vi.fn(async (url, opts = {}) => {
      if ((opts.method ?? 'GET') === 'DELETE') deletes.push(url)
      if ((opts.method ?? 'GET') === 'GET') return { ok: true, json: async () => ({ items: [] }) }
      return { ok: true, json: async () => ({ id: 'x' }) }
    })

    const corrupt = structuredClone(backup)
    corrupt.batches[0].gravityReadings[0].gravity = 'not a number'

    await expect(processBrewGraphRestore(corrupt, restoreDeps())).rejects.toThrow(
      /does not match the BrewGraph export format/
    )
    expect(deletes).toEqual([])
  })
})
