/*
 * Read-only browser comparison between the preserved legacy and active Quasar frontends.
 * Both clients must point to the same local API data. This test does not submit forms,
 * confirm deletes, save settings, or otherwise mutate server data.
 */
import { expect, test } from '@playwright/test'
import process from 'node:process'

const staticRoutes = [
  '/',
  '/device',
  '/batch',
  '/batch/compare',
  '/settings',
  '/other/backup',
  '/other/support',
  '/other/system',
  '/other/ingestion',
  '/other/integrations',
  '/other/about',
  '/cellar/taps',
  '/cellar/vessels'
]

const legacyBaseURL = process.env.LEGACY_WEB_URL ?? 'http://127.0.0.1:81'
const quasarBaseURL = process.env.WEB_PARITY_URL ?? 'http://127.0.0.1:5174'

function routeName(route) {
  return route.replace(/[^a-z0-9]+/gi, '_').replace(/_[0-9a-f]{8}[0-9a-f_]*/g, '_') || 'root'
}

test('renders every route without Quasar console errors or mobile overflow', async ({ browser }, testInfo) => {
  const discoveryContext = await browser.newContext({ viewport: { width: 1400, height: 1000 } })
  const discoveryPage = await discoveryContext.newPage()
  const findLink = async (listRoute, pattern) => {
    await discoveryPage.goto(`${quasarBaseURL}${listRoute}`, { waitUntil: 'domcontentloaded' })
    await discoveryPage.waitForTimeout(1_000)
    const links = await discoveryPage.locator('a[href]').evaluateAll((elements) =>
      elements.map((element) => element.getAttribute('href')).filter(Boolean)
    )
    return links.find((href) => pattern.test(href))
  }
  const deviceRoute = await findLink('/device', /^\/device\/[\da-f-]{36}$/i)
  const deviceLogRoute = await findLink('/device', /^\/device\/log\/(?!\*)([^/]+)$/)
  const batchRoute = await findLink('/batch', /^\/batch\/[\da-f-]{36}$/i)
  const tapRoute = await findLink('/cellar/taps', /^\/cellar\/taps\/[\da-f-]{36}$/i)
  const vesselRoute = await findLink('/cellar/vessels', /^\/cellar\/vessels\/[\da-f-]{36}$/i)
  await discoveryContext.close()

  const batchId = batchRoute?.split('/')[2]
  const routes = [
    ...staticRoutes.slice(0, 2),
    ...(deviceRoute ? [deviceRoute] : []),
    ...(deviceLogRoute ? [deviceLogRoute] : []),
    ...staticRoutes.slice(2, 3),
    ...(batchId
      ? [
          batchRoute,
          `/batch/${batchId}/gravity/graph`,
          `/batch/${batchId}/fermentation-control`,
          `/batch/${batchId}/gravity`,
          `/batch/${batchId}/pressure/graph`,
          `/batch/${batchId}/pressure`,
          `/batch/${batchId}/temp/chart`,
          `/batch/${batchId}/gravity/test`
        ]
      : []),
    ...staticRoutes.slice(3, 11),
    ...(tapRoute ? [tapRoute] : []),
    ...staticRoutes.slice(11),
    ...(vesselRoute ? [vesselRoute, `${vesselRoute}/pours`] : [])
  ]

  const problems = []

  for (const [tag, baseURL] of [['legacy', legacyBaseURL], ['quasar', quasarBaseURL]]) {
    const context = await browser.newContext({ viewport: { width: 1400, height: 1000 } })
    const page = await context.newPage()
    const consoleErrors = []
    page.on('console', (message) => {
      if (message.type() === 'error' && !/status of 424/.test(message.text())) consoleErrors.push({ text: message.text().slice(0, 180), location: message.location().url })
    })
    page.on('pageerror', (error) => consoleErrors.push(error.message.slice(0, 180)))
    page.on('response', (response) => {
      // An instance without Brewfather credentials answers 424 by design; that is not a defect.
      if (tag === 'quasar' && response.status() >= 400 && !response.url().includes('/api/brewfather/')) {
        consoleErrors.push({ text: `HTTP ${response.status()}`, location: response.url() })
      }
    })
    for (const [index, route] of routes.entries()) {
      const response = await page.goto(`${baseURL}${route}`, { waitUntil: 'domcontentloaded' })
      await page.waitForTimeout(2_000)
      if (!response || response.status() >= 400) {
        problems.push({ tag, route, status: response?.status() ?? 'no response' })
      }
      const pageText = await page.locator('body').innerText()
      if (pageText.trim().length < 100) {
        problems.push({ tag, route, issue: 'page content did not render' })
      }
      if (tag === 'legacy' || tag === 'quasar') {
        const screenshotPath = testInfo.outputPath(`${String(index + 1).padStart(2, '0')}-${routeName(route)}-${tag}.png`)
        await page.screenshot({ path: screenshotPath, fullPage: true })
      }

      if (tag === 'quasar') {
        await page.setViewportSize({ width: 390, height: 844 })
        await page.goto(`${baseURL}${route}`, { waitUntil: 'domcontentloaded' })
        await page.waitForTimeout(400)
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
        if (overflow) problems.push({ tag, route, issue: 'horizontal overflow at 390px' })
        await page.setViewportSize({ width: 1400, height: 1000 })
      }
    }

    if (tag === 'quasar' && consoleErrors.length) {
      problems.push({ tag, issue: 'console errors', errors: [...new Set(consoleErrors)].slice(0, 20) })
    }
    await context.close()
  }

  console.log(JSON.stringify({ routes: routes.length, problems }, null, 2))
  expect(problems).toEqual([])
})
