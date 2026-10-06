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

export interface CursorPage<T> {
  items: T[]
  hasMore: boolean
  nextCursor: string | null
}

export interface NumberedPage<T> {
  items: T[]
  pages: number
}

export async function fetchAllCursorPages<T>(
  fetchPage: (cursor: string | null) => Promise<CursorPage<T> | null>
): Promise<T[] | null> {
  const all: T[] = []
  let cursor: string | null = null
  let hasMore = true
  while (hasMore) {
    const page = await fetchPage(cursor)
    if (!page) return null
    all.push(...page.items)
    cursor = page.nextCursor
    hasMore = page.hasMore
  }
  return all
}

export async function fetchAllNumberedPages<T>(
  fetchPage: (page: number) => Promise<NumberedPage<T> | null>
): Promise<T[] | null> {
  const all: T[] = []
  let page = 1
  let totalPages = 1
  do {
    const result = await fetchPage(page)
    if (!result) return null
    all.push(...result.items)
    totalPages = result.pages
    page++
  } while (page <= totalPages)
  return all
}
