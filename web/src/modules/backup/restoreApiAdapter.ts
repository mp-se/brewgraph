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
 * Thin HTTP layer for `brewgraphRestore.ts`.
 *
 * This module knows how to talk to the BrewGraph API — auth header, JSON
 * encoding, offset pagination — and nothing about what a device, batch, tap
 * or vessel is. Keeping that split out is what keeps the restore-plan
 * executor's ordering and reporting logic (deletion order, id remapping,
 * per-entity success/failure counts) readable on its own.
 */

import { apiFetch } from '@/modules/apiClient'

// The restore takes its URL and token as parameters, and a restore can run long: no request timeout.
function send(method: string, url: string, token: string, body?: unknown): Promise<Response> {
  return apiFetch(method, url, body, { baseURL: '', token, timeout: false })
}

export async function apiGet(url: string, token: string): Promise<Response> {
  return send('GET', url, token)
}

export async function apiPost(url: string, token: string, body: unknown): Promise<Response> {
  return send('POST', url, token, body)
}

export async function apiPatch(url: string, token: string, body: unknown): Promise<Response> {
  return send('PATCH', url, token, body)
}

export async function apiDelete(url: string, token: string): Promise<Response> {
  return send('DELETE', url, token)
}

/**
 * Collect every id from a resource collection endpoint, following offset
 * pagination. Handles both plain-array responses and `{ items, pages }`
 * responses — the two shapes BrewGraph's list endpoints return.
 */
export async function fetchAllIds(url: string, token: string): Promise<(string | number)[]> {
  const ids: (string | number)[] = []

  const res = await apiGet(`${url}?pageSize=200`, token)
  if (!res.ok) throw new Error(`GET ${url} failed: ${res.status}`)
  const data = await res.json()

  if (Array.isArray(data)) {
    ids.push(...data.map((item: { id: string | number }) => item.id))
  } else {
    const first = data as { items: { id: string | number }[]; pages: number }
    ids.push(...(first.items ?? []).map((i) => i.id))
    for (let page = 2; page <= (first.pages ?? 1); page++) {
      const pr = await apiGet(`${url}?page=${page}&pageSize=200`, token)
      if (!pr.ok) break
      const pd = await pr.json()
      ids.push(...(pd.items ?? []).map((i: { id: string | number }) => i.id))
    }
  }
  return ids
}
