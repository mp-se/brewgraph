/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

/** Label for the "Detected format" line shown after a restore file is picked. */
export function describeBackupFormat(data: unknown): string {
  const doc = (data ?? {}) as {
    meta?: { software?: string; version?: string | number }
    source?: string
    schemaVersion?: string | number
  }
  if (doc.meta?.software) return `${doc.meta.software} v${doc.meta.version ?? '?'}`
  if (doc.source && doc.schemaVersion !== undefined) return `BrewGraph v${doc.schemaVersion}`
  return 'Unknown format'
}
