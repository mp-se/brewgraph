/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 *
 * This file is part of BrewGraph. For open source use it is licensed under
 * the GNU General Public License v3.0. For commercial use without source
 * disclosure, a separate Commercial License is required.
 * See LICENSE for details.
 */

/**
 * Runtime validation of import files against the shared JSON Schemas.
 *
 * Both schemas run at runtime against a file arriving from disk, not just
 * against *our* own producers in tests — that asymmetry matters most in the
 * one place validation must not be skipped: `processBrewGraphRestore`
 * **deletes every device, vessel, tap and batch** before it writes anything,
 * checking only two header fields beforehand. A file that passed those two
 * and was malformed anywhere else would take the database with it.
 *
 * Validation therefore runs *before* the destructive step, not as a courtesy check
 * afterwards.
 *
 * **The schemas are read from `api/oss/`, not copied here.** A second copy is a
 * second source of truth, and it would drift silently — which is the failure this
 * whole format exists to prevent. They are compiled into validators at build time
 * by scripts/build-validators.mjs, which reads those same files.
 *
 * Cost: the precompiled validators are imported only by the restore path, which
 * lives in a lazily-loaded route chunk, so they are fetched when someone opens
 * Backup & Restore and never on first paint. The ajv *runtime* is no longer shipped
 * to the browser at all — only the generated code, which is smaller.
 */

import type { ErrorObject } from 'ajv'
import { validationErrorSummary } from '@brewgraph/core'
import validateExport from './generated/exportValidator.js'
import validateBrewlogger from './generated/brewloggerValidator.js'

/*
 * The validators are **precompiled at build time** by scripts/build-validators.mjs,
 * not compiled here from the schema JSON.
 *
 * ajv's `compile()` generates JavaScript source and evaluates it with `new Function`.
 * The app is served under a Content-Security-Policy with no `'unsafe-eval'`, so that
 * threw EvalError and killed the entire restore path before it read a single batch —
 * in the production build only, which is why the dev server never showed it.
 *
 * Moving compilation to build time keeps the CSP strict. The two transforms that used
 * to live here — the import relaxation for the export schema, and compiling the
 * BrewLogger schema exactly as authored — moved into that script unchanged; see its
 * comments for why each is the way it is.
 *
 * The schemas are still the single source of truth, still read straight from
 * `api/oss/`, and the generated output is gitignored and regenerated on every dev,
 * build, and test run, so it cannot drift.
 */

/**
 * Render ajv errors as something a brewer can act on.
 *
 * ajv's raw output names the failing keyword and a JSON pointer, which reads as
 * noise to anyone who has not seen the schema. The path is the useful half — it
 * says *which batch* and *which field* — so it is kept and the keyword is
 * translated. Capped, because a file with the wrong shape produces hundreds of
 * errors that all say the same thing.
 */
const MAX_REPORTED = 5

export function describeErrors(errors: ErrorObject[] | null | undefined): string {
  return validationErrorSummary(errors, MAX_REPORTED)
}

/**
 * Validate a `brewgraph-batch-export-v1` document.
 *
 * Returns `null` when the document is valid, or a human-readable summary of what
 * is wrong. A summary rather than a thrown error, so callers decide whether a
 * given problem is fatal — the restore path treats it as fatal, deliberately.
 */
export function validateExportDocument(doc: unknown): string | null {
  if (!validateExport(doc)) return describeErrors(validateExport.errors)
  return backupBatchIdentityProblem(doc)
}

/*
 * The schema lets a batch's id, name and status be null, because other export modes
 * carry no ids. A backup, though, is restored by recreating each batch under its name,
 * so a backup whose batches have none is one whose restore would delete everything and
 * recreate nothing. Catch it here, before anything is deleted.
 */
function backupBatchIdentityProblem(doc: unknown): string | null {
  const d = doc as { mode?: string; batches?: Array<{ id?: unknown; name?: unknown }> }
  if (d?.mode !== 'backup' || !Array.isArray(d.batches)) return null
  const bad = d.batches.reduce(
    (acc: number[], b, i) => (!b?.id || !b?.name ? [...acc, i] : acc),
    []
  )
  if (bad.length === 0) return null
  const shown = bad.slice(0, MAX_REPORTED).map((i) => `/batches/${i}`)
  return (
    `${bad.length} of ${d.batches.length} batches have no id or name (${shown.join(', ')}` +
    `${bad.length > shown.length ? ', …' : ''}); the file is damaged and cannot be restored`
  )
}

/**
 * Validate a BrewLogger backup or single-batch export.
 *
 * Deliberately permissive, mirroring the schema: this is someone else's format, so
 * a false rejection refuses a user's real data. It catches wrong *types* — a
 * gravity of `"1.010"` reads fine and computes wrong — and missing essentials, not
 * unfamiliar fields.
 */
export function validateBrewloggerDocument(doc: unknown): string | null {
  if (validateBrewlogger(doc)) return null
  return describeErrors(validateBrewlogger.errors)
}
