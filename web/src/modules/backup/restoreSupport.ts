/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import { logError } from '@/ui'
import type { RestoreDeps, RestoreReport } from './restoreTypes'
import { apiDelete, apiPost, fetchAllIds } from './restoreApiAdapter'

export function emptyRestoreReport(): RestoreReport {
  return {
    devices: { restored: 0, failed: 0 },
    batches: { restored: 0, failed: 0 },
    taps: { restored: 0, failed: 0 },
    vessels: { restored: 0, failed: 0 },
    readings: { restored: 0, failed: 0 },
    pours: { restored: 0, failed: 0 },
    problems: []
  }
}

export function restoreFailureCount(r: RestoreReport): number {
  return (
    r.devices.failed +
    r.batches.failed +
    r.taps.failed +
    r.vessels.failed +
    r.readings.failed +
    r.pours.failed
  )
}

/*
 * A rejection in words a brewer can act on. The API returns only a generic message
 * for a validation failure (field detail stays in the API log), so status is what
 * distinguishes the cases.
 */
export function rejectionReason(status: number): string {
  if (status === 400 || status === 422) return 'the server rejected its data as invalid'
  if (status === 409) return 'it conflicts with data already on the server'
  if (status === 401 || status === 403) return 'not authorized'
  if (status === 413) return 'too large'
  if (status >= 500) return 'server error'
  return `unexpected response ${status}`
}

export function recordRejection(report: RestoreReport, what: string, status: number): void {
  report.problems.push(`${what}: ${rejectionReason(status)}`)
}

/**
 * Delete every row at a collection URL. The caller must check all failed URLs
 * before hard-purging soft-deleted rows.
 */
export async function deleteAll(url: string, deps: RestoreDeps): Promise<string[]> {
  const ids = await fetchAllIds(url, deps.token)
  const failed: string[] = []

  await Promise.all(
    ids.map(async (id) => {
      const itemUrl = `${url}/${id}`
      const del = await apiDelete(itemUrl, deps.token)
      if (del.status !== 204) {
        logError('brewgraphRestore.deleteAll()', 'DELETE failed', del.status, itemUrl)
        failed.push(itemUrl)
      }
    })
  )
  return failed
}

/** The rejection body (e.g. a 422's field errors) for the log; never throws. */
export async function errorDetail(res: Response): Promise<string> {
  try {
    return await res.text()
  } catch {
    return ''
  }
}

const BULK_CHUNK_SIZE = 1000

function chunk<T>(items: T[], size = BULK_CHUNK_SIZE): T[][] {
  const chunks: T[][] = []
  for (let i = 0; i < items.length; i += size) chunks.push(items.slice(i, i + size))
  return chunks
}

/**
 * POST a bulk-insert array in slices no larger than the API's 1,000-item cap.
 * Count all failed items and emit one readable problem per collection.
 */
export async function postChunked(
  url: string,
  token: string,
  items: unknown[],
  counts: { restored: number; failed: number },
  onProgress: () => void,
  report: RestoreReport,
  what: string
): Promise<void> {
  let failedStatus: number | null = null
  let failedItems = 0
  for (const part of chunk(items)) {
    const res = await apiPost(url, token, part)
    if (res.ok) {
      counts.restored += part.length
    } else {
      counts.failed += part.length
      failedItems += part.length
      failedStatus ??= res.status
      logError('brewgraphRestore.postChunked()', `bulk POST failed for ${url} status=${res.status}`)
    }
    onProgress()
  }
  if (failedStatus !== null) {
    recordRejection(report, `${failedItems} of ${items.length} ${what}`, failedStatus)
  }
}
