/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import { expect, test } from '@playwright/test'

const emptyPage = { items: [], pages: 1 }
const emptyCursor = { items: [], hasMore: false, nextCursor: null }

function sampleDevice(overrides = {}) {
  return {
    id: 'device-1',
    name: 'GravityMon',
    chipId: 'a1b2c3',
    chipFamily: 'esp32',
    deviceType: 'gravitymon',
    deviceColor: 'Blue',
    token: 'smoke-token',
    mdns: 'gravitymon.local',
    url: '',
    config: null,
    description: '',
    collectLogs: false,
    batchId: 'batch-1',
    batchRole: 'gravity',
    vesselId: null,
    failedIngestCounter: 0,
    lastSeen: null,
    ...overrides
  }
}

function sampleBatch(overrides = {}) {
  return {
    id: 'batch-1',
    name: 'Smoke IPA',
    description: '',
    brewer: 'Smoke test',
    brewDate: '2026-10-01',
    status: 'fermenting',
    acceptIngest: true,
    gravityDeviceId: 'device-1',
    pressureDeviceId: null,
    chamberDeviceId: null,
    og: 1.05,
    fg: null,
    abv: null,
    ebc: null,
    ibu: null,
    gravityCount: 1,
    pressureCount: 0,
    temperatureCount: 0,
    fermentationSteps: '',
    ...overrides
  }
}

function sampleGravityReading() {
  return {
    id: 'reading-1',
    deviceId: 'device-1',
    gravity: 1.05,
    temperature: 18.5,
    angle: 25.3,
    velocity: 0.4,
    battery: 4.13,
    rssi: -71,
    runTime: 5,
    excluded: false,
    isAggregate: false,
    createdAt: '2026-10-01T10:00:00Z'
  }
}

async function installMockApi(page, seed = {}) {
  const state = {
    devices: structuredClone(seed.devices ?? []),
    batches: structuredClone(seed.batches ?? []),
    taps: structuredClone(seed.taps ?? []),
    vessels: structuredClone(seed.vessels ?? []),
    requests: []
  }

  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/events') {
      await route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
      return
    }
    if (!url.pathname.startsWith('/api/')) {
      await route.continue()
      return
    }

    const method = request.method()
    const path = url.pathname.slice('/api/'.length).replace(/\/$/, '')
    const body = request.postDataJSON?.() ?? null
    state.requests.push({ method, path, body })
    const json = (payload, status = 200) =>
      route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify(payload)
      })
    const collection = path.split('/')[0]

    if (method === 'GET' && path === 'tenant/settings') {
      await json({ id: 'smoke-instance', temperatureFormat: 'c', pressureFormat: 'kpa', gravityFormat: 'sg', volumeFormat: 'metric' })
      return
    }
    if (method === 'GET' && path === 'yeast-strains') {
      await json([])
      return
    }
    if (method === 'GET' && ['devices', 'batches', 'taps', 'vessels'].includes(path)) {
      await json({ items: state[path], pages: 1, total: state[path].length })
      return
    }
    if (method === 'GET' && path === 'system/logs') {
      await json(emptyCursor)
      return
    }

    const collectionItem = path.match(/^(devices|batches|taps|vessels)\/([^/]+)$/)
    if (collectionItem) {
      const [, key, id] = collectionItem
      const rows = state[key]
      const index = rows.findIndex((row) => String(row.id) === id)
      if (method === 'GET') {
        await json(index < 0 ? { message: 'Not found' } : rows[index], index < 0 ? 404 : 200)
        return
      }
      if (method === 'PATCH') {
        if (index >= 0) rows[index] = { ...rows[index], ...(body ?? {}) }
        await json(rows[index] ?? { id, ...(body ?? {}) })
        return
      }
      if (method === 'DELETE') {
        state[key] = rows.filter((row) => String(row.id) !== id)
        await route.fulfill({ status: 204, body: '' })
        return
      }
    }

    if (method === 'POST' && ['devices', 'batches', 'taps', 'vessels'].includes(path)) {
      const singular = { devices: 'device', batches: 'batch', taps: 'tap', vessels: 'vessel' }[path]
      const id = `${singular}-smoke-${state[path].length + 1}`
      const saved = { ...(body ?? {}), id }
      state[path].push(saved)
      await json(saved, 201)
      return
    }

    const batchSubresource = path.match(/^batches\/([^/]+)\/(.+)$/)
    if (batchSubresource && method === 'GET') {
      const [, batchId, resource] = batchSubresource
      if (resource === 'fermentation-steps' || resource === 'dry-hops') {
        await json([])
        return
      }
      if (resource === 'gravity') {
        const rows = state.batches.some((row) => String(row.id) === batchId) && seed.includeGravity
          ? [sampleGravityReading()]
          : []
        await json({ ...emptyCursor, items: rows })
        return
      }
      await json(emptyCursor)
      return
    }

    if (method === 'GET' && /^(devices|batches|taps|vessels)$/.test(path)) {
      await json({ items: state[collection] ?? [], pages: 1 })
      return
    }

    if (method === 'POST' && path === 'system/purge-deleted') {
      await json({ purged: 0 })
      return
    }
    if (method === 'DELETE' && /\/fermentation-steps$/.test(path)) {
      await route.fulfill({ status: 204, body: '' })
      return
    }
    if (method === 'POST' && /\/fermentation-steps$/.test(path)) {
      await json([], 201)
      return
    }
    if (method === 'POST' && /\/(gravity|pressure|temp|pours)\/bulk$/.test(path)) {
      await json({ inserted: Array.isArray(body) ? body.length : 0 })
      return
    }
    if (method === 'POST') {
      await json({ id: `${collection}-smoke-${state[collection]?.length ?? 1}` }, 201)
      return
    }
    if (method === 'PATCH') {
      await json({})
      return
    }

    await json(emptyPage)
  })

  return state
}

async function openApp(page, path, seed) {
  const state = await installMockApi(page, seed)
  await page.goto(path)
  await expect(page.getByText('Initializing BrewGraph interface')).toHaveCount(0)
  await expect(page.locator('#app')).toBeVisible()
  return state
}

test('creates and edits a batch in the browser', async ({ page }) => {
  const state = await openApp(page, '/batch/new')

  await page.getByLabel('Name', { exact: true }).fill('Smoke created batch')
  await page.getByRole('button', { name: /Save/ }).click()
  await expect(page).toHaveURL(/\/batch\/batch-smoke-1$/)

  await page.getByLabel('Name', { exact: true }).fill('Smoke edited batch')
  await page.getByRole('button', { name: /Save/ }).click()
  await expect(page.getByText('Saved batch')).toBeVisible()
  expect(state.requests.some((request) => request.method === 'POST' && request.path === 'batches')).toBe(true)
  expect(state.requests.some((request) => request.method === 'PATCH' && request.path === 'batches/batch-smoke-1')).toBe(true)
})

test('creates and edits a device in the browser', async ({ page }) => {
  const state = await openApp(page, '/device/new')

  await page.getByLabel('Name', { exact: true }).fill('Smoke created device')
  await page.getByRole('button', { name: /Save/ }).click()
  await expect(page).toHaveURL(/\/device\/device-smoke-1$/)

  await page.getByLabel('Name', { exact: true }).fill('Smoke edited device')
  await page.getByRole('button', { name: /Save/ }).click()
  await expect(page.getByText('Saved device')).toBeVisible()
  expect(state.requests.some((request) => request.method === 'POST' && request.path === 'devices')).toBe(true)
  expect(state.requests.some((request) => request.method === 'PATCH' && request.path === 'devices/device-smoke-1')).toBe(true)
})

test('the device editor shows Collect logs once, as the header above the toggle', async ({ page }) => {
  await openApp(page, '/device/device-1', { devices: [sampleDevice()] })
  await expect(page.getByRole('button', { name: /Save/ })).toBeVisible()
  await expect(page.getByText('Collect logs', { exact: true })).toHaveCount(1)
  await expect(page.getByRole('switch', { name: 'Collect logs' })).toBeVisible()
})

test('opens the gravity formula editor and saves a calibration point', async ({ page }) => {
  const state = await openApp(page, '/device/device-1', { devices: [sampleDevice()] })
  await expect(page.getByTestId('gravity-formula-editor')).toHaveCount(0)
  await page.getByRole('button', { name: 'Formula editor' }).click()
  await expect(page).toHaveURL(/\/device\/device-1\/gravity-formula$/)
  const editor = page.getByTestId('gravity-formula-editor')
  await expect(editor).toBeVisible()
  await expect(editor.getByText('does not change the formula on the device', { exact: false })).toBeVisible()
  await editor.getByRole('tab', { name: 'Table', exact: true }).click()
  await editor.getByRole('button', { name: 'Add point' }).click()
  await editor.getByLabel('Angle (°)').fill('30')
  await editor.getByLabel('Gravity (SG)').fill('1.03')
  await editor.getByLabel('Gravity (SG)').blur()
  await editor.getByRole('tab', { name: 'Formula', exact: true }).click()
  await editor.getByRole('textbox', { name: 'Formula' }).fill('1+tilt/1000')
  await editor.getByRole('tab', { name: 'Graph', exact: true }).click()
  await expect(editor.getByRole('img', { name: /Gravity calibration chart/ })).toBeVisible()
  await page.getByRole('button', { name: /Save/ }).click()
  await expect.poll(() => state.requests.findLast(request => request.method === 'PATCH' &&
    request.path === 'devices/device-1')?.body?.gravityCalibrationData).toEqual([{ angle: 30, gravity: 1.03 }])
  expect(state.requests.findLast(request => request.method === 'PATCH' &&
    request.path === 'devices/device-1')?.body?.gravityFormula).toBe('1+tilt/1000')
})

test('opens the batch action menu and exports readings', async ({ page }) => {
  const state = await openApp(page, '/batch', {
    devices: [sampleDevice()],
    batches: [sampleBatch()],
    includeGravity: true
  })

  await page.getByRole('button', { name: 'More batch actions' }).click()
  await expect(page.getByTestId('batch-data-menu-content')).toBeVisible()
  const downloadPromise = page.waitForEvent('download')
  await page.getByText('Export gravity CSV', { exact: true }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/gravity.*\.csv$/i)
  expect(state.requests.some((request) => request.path === 'batches/batch-1/gravity')).toBe(true)
})

test('creates a backup and restores it into a clean browser instance', async ({ browser }, testInfo) => {
  const sourceContext = await browser.newContext({ acceptDownloads: true })
  const sourcePage = await sourceContext.newPage()
  await openApp(sourcePage, '/other/backup', {
    devices: [sampleDevice()],
    batches: [sampleBatch()],
    includeGravity: true
  })

  const downloadPromise = sourcePage.waitForEvent('download')
  await sourcePage.getByRole('button', { name: 'Create backup' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('brewgraph_backup.txt')
  const backupPath = testInfo.outputPath(download.suggestedFilename())
  await download.saveAs(backupPath)

  const restoreContext = await browser.newContext()
  try {
    const restorePage = await restoreContext.newPage()
    const cleanState = await openApp(restorePage, '/other/backup')
    await restorePage.locator('#restore-file').setInputFiles(backupPath)
    await restorePage.getByRole('button', { name: 'Restore selected backup' }).click()
    await restorePage.getByRole('button', { name: 'Confirm' }).click()

    await expect(restorePage.getByText('Restore successful')).toBeVisible({ timeout: 15_000 })
    expect(cleanState.devices).toHaveLength(1)
    expect(cleanState.batches).toHaveLength(1)
    expect(cleanState.requests.some((request) => request.method === 'POST' && request.path === 'devices')).toBe(true)
    expect(cleanState.requests.some((request) => request.method === 'POST' && request.path === 'batches')).toBe(true)
    expect(cleanState.requests.some((request) => request.method === 'POST' && /\/gravity\/bulk$/.test(request.path) && request.body?.length === 1)).toBe(true)
  } finally {
    await restoreContext.close()
    await sourceContext.close()
  }
})

test.describe('list view action row layout', () => {
  const manyDevices = Array.from({ length: 12 }, (_, i) =>
    sampleDevice({ id: `device-${i + 1}`, name: `Device ${i + 1}`, chipId: `chip${i + 1}`, batchId: null, batchRole: null })
  )

  async function boxes(page) {
    // "Add Device" lives in the page header; the secondary actions share the row with the pagination.
    const add = await page.getByRole('button', { name: 'Search for Devices' }).boundingBox()
    // The visible page buttons, not the nav wrapper: a margin on the list would move the wrapper and not the buttons.
    const nav = await page.getByRole('navigation', { name: 'Device list pagination' }).locator('ul').boundingBox()
    expect(add).not.toBeNull()
    expect(nav).not.toBeNull()
    return { add, nav }
  }

  for (const width of [1440, 1024]) test(`pagination sits on the action button row, to its right, at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await openApp(page, '/device', { devices: manyDevices })
    const { add, nav } = await boxes(page)

    const overlap = Math.min(add.y + add.height, nav.y + nav.height) - Math.max(add.y, nav.y)
    expect(overlap, 'pagination and the action buttons share a row').toBeGreaterThan(0)
    const offset = Math.abs(add.y + add.height / 2 - (nav.y + nav.height / 2))
    expect(offset, `pagination is vertically centred on the buttons (off by ${offset.toFixed(1)}px)`).toBeLessThanOrEqual(3)
    expect(nav.x, 'pagination is right of the buttons').toBeGreaterThan(add.x + add.width)
    const row = await page.locator('.app-list-actions').boundingBox()
    expect(row.x + row.width - (nav.x + nav.width), 'pagination is right-aligned').toBeLessThanOrEqual(2)
  })

  for (const width of [390, 800]) {
    test(`action row does not overflow horizontally at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      await openApp(page, '/device', { devices: manyDevices })
      await boxes(page)
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
      expect(overflow).toBeLessThanOrEqual(0)
    })
  }
})

test.describe('list screen conventions', () => {
  const devices = [
    sampleDevice({ id: 'device-1', name: 'Coloured', deviceColor: 'blue', chipFamily: '', url: 'http://10.0.0.5' }),
    sampleDevice({ id: 'device-2', name: 'Plain', chipId: 'b2c3d4', deviceColor: '', chipFamily: '', batchId: null, batchRole: null })
  ]

  test('the create action is one primary button in the page header, visible without scrolling at 1440px', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await openApp(page, '/device', { devices })

    const add = page.locator('.app-page-header__action').getByText('Add Device')
    await expect(add).toBeVisible()
    const box = await add.boundingBox()
    expect(box.y + box.height, 'inside the first screen').toBeLessThanOrEqual(900)
    const title = await page.locator('.app-page-header .text-h6').boundingBox()
    expect(box.x, 'right of the title').toBeGreaterThan(title.x + title.width)
    const page_ = await page.locator('.app-page-header').boundingBox()
    expect(page_.x + page_.width - (box.x + box.width), 'right-aligned in the page').toBeLessThanOrEqual(20)
    await expect(page.locator('.app-list-actions').getByText('Add Device')).toHaveCount(0)
    await expect(page.locator('.app-list-actions').getByText('Search for Devices')).toBeVisible()
  })

  for (const [path, label] of [['/batch', 'Add Batch'], ['/cellar/vessels', 'Add Vessel'], ['/cellar/taps', 'Add Tap']]) {
    test(`${label} is in the page header at 1440px`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 })
      await openApp(page, path, { devices, batches: [sampleBatch()] })
      const add = page.locator('.app-page-header__action').getByText(label)
      await expect(add).toBeVisible()
      const box = await add.boundingBox()
      expect(box.y + box.height).toBeLessThanOrEqual(900)
    })
  }

  test('row actions are filled icon buttons, coloured by meaning, with a label', async ({ page }) => {
    // The batches link shows for a device whose id equals its chip id and that has a batch.
    const withBatch = [sampleDevice({ id: 'a1b2c3', chipId: 'a1b2c3', url: 'http://10.0.0.5' })]
    await openApp(page, '/device', { devices: withBatch, batches: [sampleBatch({ gravityDeviceId: 'a1b2c3' })] })
    const row = page.locator('tbody tr').first()

    for (const [name, kind] of [['Edit device', 'primary'], ['Delete device', 'negative'], ['Show batches for this device', 'positive'], ['Open device UI', 'secondary']]) {
      const action = row.getByLabel(name)
      await expect(action).toBeVisible()
      await expect(action).toHaveClass(new RegExp(`app-button--${kind}`))
      await expect(action).toHaveClass(/app-button--dense/)
      await expect(action).not.toHaveClass(/q-btn--flat/)
      await expect(action).not.toHaveClass(/q-btn--round/)
      const style = await action.evaluate((el) => {
        const css = getComputedStyle(el)
        return { radius: parseFloat(css.borderRadius), background: css.backgroundColor }
      })
      expect(style.radius, `${name} is a rounded rectangle`).toBeLessThan(12)
      expect(style.background, `${name} is filled`).not.toBe('rgba(0, 0, 0, 0)')
    }
  })

  test('the delete action is a solid red button with a white icon', async ({ page }) => {
    await openApp(page, '/device', { devices })
    const del = page.locator('tbody tr').first().getByLabel('Delete device')
    const style = await del.evaluate((el) => {
      const css = getComputedStyle(el)
      return { background: css.backgroundColor, colour: css.color }
    })
    const [r, g, b] = style.background.match(/\d+/g).map(Number)
    expect(r, 'red dominates').toBeGreaterThan(g + 60)
    expect(r).toBeGreaterThan(b + 60)
    expect(style.colour).toBe('rgb(255, 255, 255)')
  })

  test('collect logs is a toggle that saves at once', async ({ page }) => {
    const state = await openApp(page, '/device', { devices })
    const toggle = page.getByTestId('collect-logs-toggle').first()

    await expect(toggle).toBeVisible()
    await expect(toggle).toHaveAttribute('aria-checked', 'false')
    expect(await page.locator('tbody input[type="checkbox"]:visible').count()).toBe(0)
    await toggle.click()
    await expect(toggle).toHaveAttribute('aria-checked', 'true')
    await expect.poll(() => state.requests.some((r) => r.method === 'PATCH' && r.path === 'devices/device-1' && r.body?.collectLogs === true)).toBe(true)
  })

  test('a failed collect-logs save puts the toggle back and says why', async ({ page }) => {
    await openApp(page, '/device', { devices })
    await page.route('**/api/devices/device-1', (route) =>
      route.request().method() === 'PATCH' ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"message":"boom"}' }) : route.fallback()
    )
    const toggle = page.getByTestId('collect-logs-toggle').first()

    await toggle.click()
    await expect(page.getByText(/Collect logs/).filter({ hasText: 'put back' })).toBeVisible()
    await expect(toggle).toHaveAttribute('aria-checked', 'false')
  })

  test('the colour swatch is a round dot and is not drawn without a colour', async ({ page }) => {
    await openApp(page, '/device', { devices })
    const swatches = page.locator('tbody .device-color-swatch')

    await expect(swatches).toHaveCount(1)
    const radius = await swatches.first().evaluate((el) => getComputedStyle(el).borderRadius)
    expect(radius).toBe('50%')
    const border = await swatches.first().evaluate((el) => getComputedStyle(el).borderTopWidth)
    expect(border).toBe('0px')
  })

  test('the chip family column appears only while a listed device has one', async ({ page }) => {
    await openApp(page, '/device', { devices })
    await expect(page.getByRole('columnheader', { name: /Chip Family/ })).toHaveCount(0)

    await openApp(page, '/device', { devices: [{ ...devices[0], chipFamily: 'esp32' }, devices[1]] })
    await expect(page.getByRole('columnheader', { name: /Chip Family/ })).toHaveCount(1)
  })

  test('column headers are aligned with their data', async ({ page }) => {
    await openApp(page, '/device', { devices })
    const aligns = await page.locator('thead th').evaluateAll((ths) => ths.map((th) => getComputedStyle(th).textAlign))
    expect(new Set(aligns)).toEqual(new Set(['left']))
  })
})

test.describe('batch editor', () => {
  const devices = [
    sampleDevice(),
    sampleDevice({ id: 'device-2', name: 'Pressure', chipId: 'b2c3d4', deviceType: 'pressuremon', batchRole: 'pressure', token: 'pressure-token' }),
    sampleDevice({ id: 'device-3', name: 'Chamber', chipId: 'c3d4e5', deviceType: 'chamber_controller', batchRole: 'chamber', token: 'chamber-token' })
  ]
  const batch = sampleBatch({
    pressureDeviceId: 'device-2',
    chamberDeviceId: 'device-3',
    gravityCount: 20,
    pressureCount: 20,
    temperatureCount: 20,
    fermentationSteps: JSON.stringify([{ order: 0, name: 'Primary', type: 'Hold', temp: 18, days: 7, date: '' }])
  })

  async function openBatch(page, width = 1440) {
    await page.setViewportSize({ width, height: 900 })
    await installMockApi(page, { devices, batches: [batch], includeGravity: true })
    await page.route('**/api/batches/batch-1/fermentation-steps', (route) =>
      route.request().method() === 'GET'
        ? route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ order: 0, name: 'Primary', type: 'Hold', temp: 18, days: 7, date: '' }]) })
        : route.fallback()
    )
    await page.goto('/batch/batch-1')
    await expect(page.getByRole('button', { name: /Save/ })).toBeVisible()
  }

  test('the Accepting toggle shows its label once, as the header', async ({ page }) => {
    await openBatch(page)
    await expect(page.getByText('Accepting', { exact: true })).toHaveCount(1)
    await expect(page.getByRole('switch', { name: 'Accepting' })).toBeVisible()
  })

  test('a gravity device shows its server URL and token, like the pressure device', async ({ page }) => {
    await openBatch(page)
    await expect(page.getByText('No setup instructions available')).toHaveCount(0)
    await expect(page.getByText('http://127.0.0.1:5175/ingest/gravitymon')).toBeVisible()
    await expect(page.getByText('smoke-token', { exact: true })).toBeVisible()
    await expect(page.getByText('http://127.0.0.1:5175/ingest/pressuremon')).toBeVisible()
    await expect(page.getByText('pressure-token', { exact: true })).toBeVisible()
    await expect(page.getByText('Server URL', { exact: true })).toHaveCount(3)
  })

  for (const width of [1440, 390]) {
    test(`kegs and bottles do not overlap and no keg row action is clipped at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      const keg = {
        id: 'vessel-1', name: 'Keg 1', batchId: 'batch-1', tapId: null, vesselNumber: 1, vesselType: 'keg',
        fillDate: '2026-10-01', conditioningDays: null, totalVolume: 19, volumeRemaining: 19,
        bottleVolume: null, bottleCount: null, bottlesRemaining: null, status: 'filled', location: '', notes: ''
      }
      await installMockApi(page, { devices, batches: [batch], vessels: [keg], includeGravity: true })
      await page.goto('/batch/batch-1')
      const kegs = page.getByTestId('batch-kegs')
      const bottles = page.getByTestId('batch-bottles')
      await expect(kegs.getByRole('button', { name: 'Empty keg' })).toBeVisible()
      await expect(bottles.getByText('No bottle batches for this batch.')).toBeVisible()

      const k = await kegs.boundingBox()
      const b = await bottles.boundingBox()
      // Stacked, each section on the full content width: Bottles starts below Kegs.
      expect(b.y, 'Bottles sits below Kegs').toBeGreaterThanOrEqual(k.y + k.height - 1)
      expect(Math.abs(k.width - b.width), 'sections share the content width').toBeLessThanOrEqual(2)

      // Every row action sits inside the table's scroll container, or the container scrolls to it.
      const container = kegs.locator('.q-table__container')
      const clipped = await container.evaluate((el) => {
        const box = el.getBoundingClientRect()
        const scrolls = el.scrollWidth > el.clientWidth + 1
        return [...el.querySelectorAll('tbody button')].map((btn) => {
          const r = btn.getBoundingClientRect()
          return { label: btn.getAttribute('aria-label'), inside: r.left >= box.left - 1 && r.right <= box.right + 1, scrolls }
        })
      })
      expect(clipped.length).toBeGreaterThanOrEqual(2)
      // Wide screens need no sideways scrolling at all; narrow ones may scroll inside the table.
      for (const c of clipped) expect(c.inside || (width < 600 && c.scrolls), `${c.label} is not clipped`).toBe(true)
      // Section header buttons keep clear of the title.
      const title = await kegs.getByText('Kegs', { exact: true }).boundingBox()
      const assign = await kegs.getByRole('button', { name: /Assign/ }).boundingBox()
      expect(assign.x >= title.x + title.width || assign.y >= title.y + title.height).toBe(true)
    })
  }

  for (const width of [1440, 390]) {
    test(`primary actions share one row above a separate, labelled group of secondary actions at ${width}px`, async ({ page }) => {
      await openBatch(page, width)
      const primary = page.getByTestId('batch-primary-actions')
      const secondary = page.getByTestId('batch-secondary-actions')
      await expect(secondary.getByText('Import, export and status')).toBeVisible()
      await expect(primary.getByRole('button', { name: /Save/ })).toBeVisible()
      await expect(primary.getByRole('button', { name: /Cancel/ })).toBeVisible()
      for (const name of ['BeerXML', 'Brewfather', 'Export', 'Archive', 'Fermentation Control']) {
        await expect(secondary.getByRole('button', { name })).toBeVisible()
        await expect(secondary.getByRole('button', { name })).toHaveClass(/app-button--outline-secondary/)
      }

      const save = await primary.getByRole('button', { name: /Save/ }).boundingBox()
      const cancel = await primary.getByRole('button', { name: /Cancel/ }).boundingBox()
      expect(Math.abs(save.y - cancel.y), 'Save and Cancel are on one row').toBeLessThanOrEqual(2)
      const group = await secondary.boundingBox()
      expect(group.y, 'the secondary group starts below the primary row').toBeGreaterThanOrEqual(save.y + save.height)
      for (const button of await secondary.getByRole('button').all()) {
        const box = await button.boundingBox()
        expect(box.y, 'no secondary action shares the primary row').toBeGreaterThan(save.y + save.height)
      }
    })
  }
})

test.describe('vessel editor', () => {
  const vessel = {
    id: 'vessel-1', name: 'Keg 1', batchId: 'batch-1', tapId: null, vesselNumber: 1, vesselType: 'keg',
    fillDate: '2026-10-01', conditioningDays: null, totalVolume: 19, volumeRemaining: 19,
    bottleVolume: null, bottleCount: null, bottlesRemaining: null, status: 'filled', location: '', notes: ''
  }
  const devices = [
    sampleDevice({ id: 'device-2', name: 'Pressure', chipId: 'b2c3d4', deviceType: 'pressuremon', batchId: null, batchRole: null, vesselId: 'vessel-1', token: 'pressure-token' }),
    sampleDevice({ id: 'device-3', name: 'Chamber', chipId: 'c3d4e5', deviceType: 'chamber_controller', batchId: null, batchRole: null, vesselId: 'vessel-1', url: 'http://chamber.local', token: 'chamber-token' })
  ]

  async function openVessel(page, width = 1440) {
    await page.setViewportSize({ width, height: 900 })
    await installMockApi(page, { devices, batches: [sampleBatch()], vessels: [vessel] })
    await page.goto('/cellar/vessels/vessel-1')
    await expect(page.getByRole('button', { name: /Save/ })).toBeVisible()
  }

  async function clearPicker(page, label) {
    await page.getByRole('combobox', { name: new RegExp(label) }).click()
    await page.getByRole('option', { name: '-- Disabled --' }).click()
    await expect(page.getByRole('option')).toHaveCount(0)
  }

  test('the paired pressure and chamber devices show their server URL and token, until the picker is cleared', async ({ page }) => {
    await openVessel(page)
    await expect(page.getByText('Server URL', { exact: true })).toHaveCount(2)
    await expect(page.getByText('Token', { exact: true })).toHaveCount(2)
    await expect(page.getByText('http://127.0.0.1:5175/ingest/pressuremon')).toBeVisible()
    await expect(page.getByText('pressure-token', { exact: true })).toBeVisible()
    await expect(page.getByText('http://127.0.0.1:5175/ingest/chamber')).toBeVisible()
    await expect(page.getByText('chamber-token', { exact: true })).toBeVisible()

    await clearPicker(page, 'Pressure Device')
    await expect(page.getByText('Server URL', { exact: true })).toHaveCount(1)
    await expect(page.getByText('pressure-token', { exact: true })).toHaveCount(0)
    await clearPicker(page, 'Chamber Device')
    await expect(page.getByText('Server URL', { exact: true })).toHaveCount(0)
    await expect(page.getByText('Token', { exact: true })).toHaveCount(0)
  })

  test('leaving without saving asks once and does not keep asking on the next screens', async ({ page }) => {
    const prompts = []
    page.on('dialog', async (dialog) => {
      prompts.push(dialog.message())
      await dialog.accept()
    })
    await openVessel(page)
    await clearPicker(page, 'Pressure Device')

    await page.getByRole('link', { name: 'Home' }).first().click()
    await expect(page).toHaveURL(/\/$/)
    expect(prompts).toHaveLength(1)
    expect(prompts[0]).toContain('unsaved changes')

    await page.getByRole('link', { name: 'Batch' }).first().click()
    await expect(page).toHaveURL(/\/batch$/)
    await page.getByRole('link', { name: 'Device' }).first().click()
    await expect(page).toHaveURL(/\/device$/)
    expect(prompts).toHaveLength(1)
  })
})

test.describe('integration forwarding form', () => {
  async function pickOption(page, label, option) {
    await page.getByRole('combobox', { name: new RegExp(label) }).click()
    await page.getByRole('option', { name: option, exact: true }).click()
  }

  test('a custom target starts from a complete JSON example for its measurement', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await openApp(page, '/other/integrations', { devices: [] })
    await pickOption(page, 'Type', 'Custom')

    const template = page.locator('textarea').first()
    const gravity = JSON.parse((await template.inputValue()).replace(/\$\{[a-zA-Z]+\}/g, '1'))
    expect(Object.keys(gravity)).toEqual(expect.arrayContaining(['name', 'gravity', 'temperature', 'angle', 'battery', 'rssi', 'timestamp']))
    expect(await template.inputValue()).not.toContain('api_key=')

    await pickOption(page, 'Measurement', 'Pressure')
    expect(await template.inputValue()).toContain('${pressure}')
    expect(await template.inputValue()).not.toContain('${gravity}')
  })

  test('a template the user has edited is not replaced when the measurement changes', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await openApp(page, '/other/integrations', { devices: [] })
    await pickOption(page, 'Type', 'Custom')
    const template = page.locator('textarea').first()
    await template.fill('{"mine": ${gravity}}')
    await pickOption(page, 'Measurement', 'Pressure')
    expect(await template.inputValue()).toBe('{"mine": ${gravity}}')
  })

  test('a pressure target can choose Brewfather custom stream and previews its payload', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await openApp(page, '/other/integrations', { devices: [] })
    await pickOption(page, 'Measurement', 'Pressure')
    await page.getByRole('combobox', { name: /Type/ }).click()
    await expect(page.getByRole('option', { name: 'iSpindel forward', exact: true })).toHaveCount(0)
    await page.getByRole('option', { name: 'Brewfather custom stream', exact: true }).click()
    await page.getByRole('button', { name: /Preview payload/ }).click()

    const body = page.locator('pre').last()
    await expect(body).toContainText('"pressure_unit": "KPA"')
    expect(JSON.parse(await body.innerText())).toEqual({
      name: 'Fermenter 1',
      pressure: 12.5,
      pressure_unit: 'KPA',
      temp: 4,
      temp_unit: 'C',
      battery: 3.98,
      rssi: -62
    })
  })

  test('a configured target can be edited, with measurement and type locked', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    const target = {
      id: 'integration-1', name: 'Old name', measurement: 'gravity', type: 'ispindel_forward',
      enabled: true, config: { url: 'https://old.example.com/in', method: 'POST', headers: {}, template: null }
    }
    const patches = []
    const state = await openApp(page, '/other/integrations', { devices: [] })
    await page.route('**/api/integrations**', async (route) => {
      const request = route.request()
      if (request.method() === 'PATCH') {
        patches.push(request.postDataJSON())
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...target, ...request.postDataJSON() }) })
        return
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([target]) })
    })
    await page.reload()

    await page.getByRole('button', { name: 'Edit target' }).click()
    await expect(page.getByRole('button', { name: /Save target/ })).toBeVisible()
    await expect(page.getByRole('combobox', { name: /Measurement/ })).toBeDisabled()
    await expect(page.getByRole('combobox', { name: /Type/ })).toBeDisabled()

    await page.getByLabel('Name', { exact: true }).fill('New name')
    await page.getByLabel('URL').fill('https://new.example.com/in')
    await page.getByRole('button', { name: /Save target/ }).click()

    await expect(page.getByRole('button', { name: /Add target/ })).toBeVisible()
    expect(patches).toEqual([{ name: 'New name', config: { url: 'https://new.example.com/in' } }])
    expect(state.requests.some((r) => r.method === 'POST' && r.path === 'integrations')).toBe(false)
  })
})
