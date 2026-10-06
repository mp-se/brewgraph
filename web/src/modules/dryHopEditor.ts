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

import { logDebug } from '@/ui'
import { apiOk } from '@/modules/apiClient'
import { dryHopsPayload, type StagedDryHop } from '@brewgraph/core'

export { dryHopsPayload, type StagedDryHop }

/** Create dry hops staged from an import (Brewfather/BeerXML) on a newly created batch. */
export async function persistDryHops(batchId: string, hops: StagedDryHop[]): Promise<boolean> {
  logDebug('dryHopEditor.persistDryHops()', batchId, 'hops:', hops.length)
  if (hops.length === 0) return true

  const payload = dryHopsPayload(hops)
  const ok = await apiOk('POST', `batches/${batchId}/dry-hops`, payload)
  logDebug('dryHopEditor.persistDryHops()', 'result:', ok)
  return ok
}
