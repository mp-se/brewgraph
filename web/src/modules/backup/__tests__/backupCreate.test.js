/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createBrewGraphBackup } from '../backupCreate'

vi.mock('@/ui', () => ({
  logDebug: vi.fn(),
  logInfo: vi.fn(),
  logError: vi.fn()
}))

/** The real `Page[...]` envelope shape (`GET /api/devices`, `/batches`, `/taps`, `/vessels`). */
function pageOf(items, pages = 1) {
  return { body: { items, total: items.length, page: 1, pageSize: 200, pages } }
}

/** The real `CursorPage[...]` envelope shape (readings, pour events). */
function cursorPageOf(items, hasMore = false, nextCursor = null) {
  return { body: { items, nextCursor, hasMore } }
}

const makeDevice = (id = 'd1') => ({ id, chipId: 'chip1', name: 'Device 1' })
const makeBatch = (id = 'b1') => ({
  id,
  name: 'Test Batch',
  desc: 'A batch',
  gravityDeviceId: null,
  pressureDeviceId: null,
  chamberDeviceId: null,
  status: 'fermenting',
  brewDate: '2026-01-01',
  style: 'IPA',
  brewer: 'Magnus',
  abv: 5.5,
  ebc: 10,
  ibu: 30,
  fg: 1.01,
  og: 1.055,
  carbonationVolumes: 2.4,
  brewfatherBatchId: 'bf1',
  notes: 'some notes',
  fermentationChamber: null
})

const makeTap = (id = 't1') => ({
  id,
  name: 'Tap 1',
  tapNumber: 1,
  location: 'Kitchen',
  notes: 'note'
})
const makeVessel = (id = 'v1') => ({
  id,
  batchId: 'b1',
  tapId: 't1',
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
  location: 'Fridge',
  notes: ''
})

const makePour = (id = 'p1', vesselId = 'v1') => ({
  id,
  vesselId,
  pourAmount: 0.5,
  volumeRemaining: 14.5,
  isManual: false,
  excluded: false,
  createdAt: '2026-01-02T10:00:00'
})

/*
 * Route responses by URL, not by call order.
 *
 * Matching by URL rather than a positional list of responses keeps every test
 * independent of how many requests the collector makes and in what order — a
 * positional list would let an unrelated fetch added anywhere upstream silently
 * shift every later response by one, passing tests for the wrong reason instead
 * of failing loudly. Keys are matched as substrings of the URL, longest first,
 * so a specific override (e.g. `batches/b1/gravity`) wins over a generic default
 * (`gravity`). An unmatched URL is a hard error rather than a 404, because a
 * request no test anticipated is a change in behaviour worth seeing.
 */
function buildFetchMock(routes) {
  const keys = Object.keys(routes).sort((a, b) => b.length - a.length)
  return vi.fn().mockImplementation((url) => {
    const key = keys.find((k) => String(url).includes(k))
    if (key === undefined) throw new Error(`unmocked fetch: ${url}`)
    const r = routes[key]
    if (r instanceof Error) return Promise.reject(r)
    return Promise.resolve({
      ok: r.ok ?? true,
      status: r.status ?? 200,
      json: () => Promise.resolve(r.body)
    })
  })
}

/**
 * The collector calls every test needs, empty unless a test overrides one.
 *
 * `gravity`/`pressure`/`temp`/`fermentation-steps`/`pours` are generic defaults
 * matching both the batch and vessel sub-resource paths (a vessel has no gravity
 * sub-resource, so that key only ever matches a batch url) — every test whose
 * `getBatch` returns non-null, or that fetches a vessel, reaches these routes,
 * mocking the real `CursorPage`/plain-array shapes those endpoints return.
 */
const emptyRoutes = () => ({
  'tenant/settings': { body: { backupSourceId: 'source-1' } },
  'devices': pageOf([]),
  'batches?': pageOf([]),
  'taps?': pageOf([]),
  'vessels': pageOf([]),
  'gravity': cursorPageOf([]),
  'pressure': cursorPageOf([]),
  'temp': cursorPageOf([]),
  'fermentation-steps': { body: [] },
  'pours': cursorPageOf([]),
  'notes': cursorPageOf([])
})

describe('createBrewGraphBackup', () => {
  let deps

  beforeEach(() => {
    deps = {
      baseURL: 'http://test/',
      token: 'Bearer t',
      getBatch: vi.fn(),
      onProgress: vi.fn()
    }
  })

  it('returns null when devices fetch fails', async () => {
    global.fetch = buildFetchMock({ 'devices': { ok: false, status: 500, body: null } })
    const result = await createBrewGraphBackup(deps)
    expect(result).toBeNull()
  })

  it('returns null when batches fetch fails', async () => {
    global.fetch = buildFetchMock({
      ...emptyRoutes(),
      'devices': pageOf([makeDevice()]),
      'batches?': { ok: false, status: 500, body: null }
    })
    const result = await createBrewGraphBackup(deps)
    expect(result).toBeNull()
  })

  it('builds minimal backup with no batches/taps/vessels', async () => {
    global.fetch = buildFetchMock(emptyRoutes())
    deps.getBatch = vi.fn()
    const result = await createBrewGraphBackup(deps)
    expect(result).not.toBeNull()
    // The bespoke `meta: {version: '2.0'}` container is gone. A backup is now a
    // brewgraph-batch-export-v1 document in `backup` mode — the same format the
    // per-batch export produces, differing only in depth.
    expect(result.schemaVersion).toBe('1')
    expect(result.source).toBe('oss')
    expect(result.mode).toBe('backup')
    expect(result.devices).toEqual([])
    expect(result.batches).toEqual([])
    expect(result.taps).toEqual([])
    expect(result.vessels).toEqual([])
  })

  it('builds backup with devices and batches', async () => {
    const device = makeDevice()
    const batch = makeBatch()
    deps.getBatch = vi.fn().mockResolvedValue(batch)

    global.fetch = buildFetchMock({
      ...emptyRoutes(),
      'devices': pageOf([device]),
      'batches?': pageOf([{ id: 'b1' }])
    })

    const result = await createBrewGraphBackup(deps)
    expect(result).not.toBeNull()
    expect(result.devices).toHaveLength(1)
    expect(result.batches).toHaveLength(1)
    expect(result.batches[0].name).toBe('Test Batch')
    expect(deps.onProgress).toHaveBeenCalled()
  })

  it('preserves device config blob verbatim (Backup & Restore contract)', async () => {
    const configBlob = JSON.stringify({
      fetched_at: '2026-07-25T14:03:00Z',
      status: { id: 'aabbcc' },
      config: { interval: 900 },
      feature: { platform: 'esp32' },
      format: { template: 'x' }
    })
    const device = { ...makeDevice(), config: configBlob }
    deps.getBatch = vi.fn()

    global.fetch = buildFetchMock({ ...emptyRoutes(), 'devices': pageOf([device]) })

    const result = await createBrewGraphBackup(deps)
    expect(result.devices).toHaveLength(1)
    expect(result.devices[0].config).toBe(configBlob)
  })

  it('includes taps in backup when taps fetch succeeds', async () => {
    deps.getBatch = vi.fn()
    global.fetch = buildFetchMock({ ...emptyRoutes(), 'taps?': pageOf([makeTap()]) })

    const result = await createBrewGraphBackup(deps)
    expect(result.taps).toHaveLength(1)
    expect(result.taps[0].name).toBe('Tap 1')
    expect(result.taps[0].tapNumber).toBe(1)
    expect(result.taps[0].location).toBe('Kitchen')
  })

  it('includes vessels with pour events', async () => {
    deps.getBatch = vi.fn()
    const vessel = makeVessel()
    const pour = makePour()

    global.fetch = buildFetchMock({
      ...emptyRoutes(),
      'vessels': pageOf([vessel]),
      'vessels/v1/pours': cursorPageOf([pour])
    })

    const result = await createBrewGraphBackup(deps)
    expect(result.vessels).toHaveLength(1)
    expect(result.vessels[0].name).toBe('Keg 1')
    expect(result.vessels[0].pourEvents).toHaveLength(1)
    expect(result.vessels[0].pourEvents[0].pourAmount).toBe(0.5)
  })

  it('aborts when the pour events of a vessel cannot be read', async () => {
    deps.getBatch = vi.fn()
    const vessel = makeVessel()

    global.fetch = buildFetchMock({
      ...emptyRoutes(),
      'vessels': pageOf([vessel]),
      'vessels/v1/pours': { body: null }
    })

    await expect(createBrewGraphBackup(deps)).rejects.toThrow('Could not read vessels/v1/pours')
  })

  it('aborts when a batch cannot be read', async () => {
    deps.getBatch = vi.fn().mockResolvedValue(null)

    global.fetch = buildFetchMock({
      ...emptyRoutes(),
      'batches?': pageOf([{ id: 'b1' }])
    })

    await expect(createBrewGraphBackup(deps)).rejects.toThrow('Could not read batch b1')
  })

  it('returns null when fetch throws an exception', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network error'))
    const result = await createBrewGraphBackup(deps)
    expect(result).toBeNull()
  })

  it('uses defaults for missing vessel and pour fields', async () => {
    const vessel = { id: 'v1', batchId: 'b1' }
    const pour = {
      id: 'p1',
      pourAmount: 0.5,
      volumeRemaining: 14.5,
      createdAt: '2026-01-02T10:00:00'
    }
    deps.getBatch = vi.fn()
    global.fetch = buildFetchMock({
      ...emptyRoutes(),
      'vessels': pageOf([vessel]),
      'vessels/v1/pours': cursorPageOf([pour])
    })
    const result = await createBrewGraphBackup(deps)
    expect(result.vessels[0].status).toBe('filled')
    expect(result.vessels[0].location).toBe('')
    expect(result.vessels[0].notes).toBe('')
    expect(result.vessels[0].pourEvents[0].isManual).toBe(false)
    expect(result.vessels[0].pourEvents[0].excluded).toBe(false)
  })

  /*
   * `BatchListResponse`/`BatchResponse` carry only reading *counts* — the
   * gravity/pressure/temperature arrays must come from their own sub-resource
   * endpoints, or a backup carries no fermentation history at all.
   */
  it('includes batch gravity, pressure and temperature data from their own endpoints', async () => {
    deps.getBatch = vi.fn().mockResolvedValue(makeBatch())

    global.fetch = buildFetchMock({
      ...emptyRoutes(),
      'batches?': pageOf([{ id: 'b1' }]),
      'batches/b1/gravity': cursorPageOf([{ id: 'g1', batchId: 'b1', gravity: 1.05 }]),
      'batches/b1/pressure': cursorPageOf([{ id: 'pr1', batchId: 'b1', pressure: 12 }]),
      'batches/b1/temp': cursorPageOf([{ id: 't1', batchId: 'b1', temperature: 18.2 }])
    })

    const result = await createBrewGraphBackup(deps)
    // Readings are named by the format now (`gravityReadings`/`pressureReadings`/
    // `temperatureReadings`) rather than passed through under the API's own key.
    expect(result.batches[0].gravityReadings).toHaveLength(1)
    expect(result.batches[0].pressureReadings).toHaveLength(1)
    expect(result.batches[0].temperatureReadings).toHaveLength(1)
    expect(result.batches[0].temperatureReadings[0].temperature).toBe(18.2)
  })

  it('follows every cursor page of a batch reading endpoint, not just the first', async () => {
    deps.getBatch = vi.fn().mockResolvedValue(makeBatch())
    let gravityCalls = 0

    // buildFetchMock only supports one static response per route, so a
    // multi-page sequence needs a custom implementation instead.
    const base = buildFetchMock({
      ...emptyRoutes(),
      'batches?': pageOf([{ id: 'b1' }])
    })
    global.fetch = vi.fn().mockImplementation((url) => {
      if (String(url).includes('batches/b1/gravity')) {
        gravityCalls++
        if (gravityCalls === 1) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () =>
              Promise.resolve({
                items: [{ id: 'g1', gravity: 1.01, createdAt: '2026-01-01T00:00:00Z' }],
                nextCursor: '2026-01-01T00:00:00Z',
                hasMore: true
              })
          })
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              items: [{ id: 'g2', gravity: 1.02, createdAt: '2026-01-02T00:00:00Z' }],
              nextCursor: null,
              hasMore: false
            })
        })
      }
      return base(url)
    })

    const result = await createBrewGraphBackup(deps)
    expect(gravityCalls).toBe(2)
    expect(result.batches[0].gravityReadings).toHaveLength(2)
  })

  it('follows every offset page of the batch list endpoint, not just the first', async () => {
    deps.getBatch = vi.fn().mockImplementation((id) => Promise.resolve(makeBatch(id)))
    global.fetch = buildFetchMock({
      ...emptyRoutes(),
      'batches?page=1': { body: { items: [{ id: 'b1' }], pages: 2 } },
      'batches?page=2': { body: { items: [{ id: 'b2' }], pages: 2 } }
    })

    const result = await createBrewGraphBackup(deps)
    expect(result.batches.map((b) => b.id).sort()).toEqual(['b1', 'b2'])
  })

  it('fetches a batch fermentation schedule from its own endpoint', async () => {
    deps.getBatch = vi.fn().mockResolvedValue(makeBatch())
    global.fetch = buildFetchMock({
      ...emptyRoutes(),
      'batches?': pageOf([{ id: 'b1' }]),
      'batches/b1/fermentation-steps': {
        body: [{ name: 'Primary', type: 'ferment', temp: 18, days: 7, order: 1 }]
      }
    })

    const result = await createBrewGraphBackup(deps)
    expect(result.batches[0].fermentationSteps).toEqual([
      { name: 'Primary', type: 'ferment', temp: 18, days: 7, order: 1 }
    ])
  })

  it('includes vessel temperature and pressure history alongside pour events', async () => {
    deps.getBatch = vi.fn()
    const vessel = makeVessel()

    global.fetch = buildFetchMock({
      ...emptyRoutes(),
      'vessels': pageOf([vessel]),
      'vessels/v1/temp': cursorPageOf([
        { id: 'vt1', temperature: 19.5, tempType: 'chamber', createdAt: '2026-01-02T10:00:00' }
      ]),
      'vessels/v1/pressure': cursorPageOf([
        { id: 'vp1', pressure: 8, createdAt: '2026-01-02T10:00:00' }
      ])
    })

    const result = await createBrewGraphBackup(deps)
    expect(result.vessels[0].temperatureReadings).toHaveLength(1)
    expect(result.vessels[0].temperatureReadings[0].temperature).toBe(19.5)
    expect(result.vessels[0].pressureReadings).toHaveLength(1)
    expect(result.vessels[0].pressureReadings[0].pressure).toBe(8)
  })

  /*
   * Notes are a separate resource — `GET /batches/{id}/notes` — so a backup
   * that never fetches them cannot carry them however good the builder is:
   * every note would be silently lost on restore.
   */
  it('fetches each batch its notes and carries them into the document', async () => {
    deps.getBatch = vi.fn().mockResolvedValue(makeBatch())
    global.fetch = buildFetchMock({
      ...emptyRoutes(),
      'batches?': pageOf([{ id: 'b1' }]),
      // The real shape: `CursorPage[BatchNoteResponse]`, an object with `items`.
      'batches/b1/notes': cursorPageOf([
        {
          content: 'Dry hopped',
          createdAt: '2026-01-05T12:00:00Z',
          noteType: 'general',
          testResult: null
        }
      ])
    })

    const result = await createBrewGraphBackup(deps)
    expect(result.batches[0].batchNotes).toEqual([
      {
        content: 'Dry hopped',
        createdAt: '2026-01-05T12:00:00Z',
        noteType: 'general',
        testResult: null
      }
    ])
  })

  it('follows the notes cursor until every note is collected', async () => {
    deps.getBatch = vi.fn().mockResolvedValue(makeBatch())
    const note = (n) => ({ content: `note ${n}`, createdAt: `2026-01-0${n}T00:00:00Z`, noteType: null, testResult: null })
    const pages = [
      { items: [note(1), note(2)], nextCursor: 'c1', hasMore: true },
      { items: [note(3)], nextCursor: null, hasMore: false }
    ]
    const base = buildFetchMock({
      ...emptyRoutes(),
      'batches?': pageOf([{ id: 'b1' }])
    })
    global.fetch = vi.fn().mockImplementation((url) =>
      String(url).includes('batches/b1/notes')
        ? Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve(String(url).includes('cursor=c1') ? pages[1] : pages[0])
          })
        : base(url)
    )

    const result = await createBrewGraphBackup(deps)
    expect(result.batches[0].batchNotes.map((n) => n.content)).toEqual(['note 1', 'note 2', 'note 3'])
    const noteCalls = global.fetch.mock.calls.map((c) => String(c[0])).filter((u) => u.includes('/notes'))
    expect(noteCalls).toHaveLength(2)
    expect(noteCalls[0]).not.toContain('includeExcluded')
  })

  it.each(['notes', 'gravity', 'pressure', 'temp'])(
    'aborts rather than write a backup missing a batch\'s %s',
    async (resource) => {
      // A file with a silent gap would restore as if it were complete.
      deps.getBatch = vi.fn().mockResolvedValue(makeBatch())
      global.fetch = buildFetchMock({
        ...emptyRoutes(),
        'batches?': pageOf([{ id: 'b1' }]),
        [`batches/b1/${resource}`]: { ok: false, status: 404, body: null }
      })

      await expect(createBrewGraphBackup(deps)).rejects.toThrow(`Could not read batches/b1/${resource}`)
    }
  )

  it('reads each batch as plain API JSON, so its identity reaches the document', async () => {
    // The app's Batch class keeps its data in `_`-prefixed fields; spreading one into the export
    // left id, name and status undefined. The default reader must not go through that class.
    delete deps.getBatch
    global.fetch = buildFetchMock({
      ...emptyRoutes(),
      'batches?': pageOf([{ id: 'b1' }]),
      'batches/b1': { body: { id: 'b1', name: 'Pale Ale', status: 'active', og: 1.05 } }
    })

    const result = await createBrewGraphBackup(deps)
    expect(result.batches).toHaveLength(1)
    expect(result.batches[0]).toMatchObject({ id: 'b1', name: 'Pale Ale', status: 'active' })
  })
})
