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

import { describe, it, expect, vi } from 'vitest'
import { fetchAllCursorPages, fetchAllNumberedPages } from '@brewgraph/core'

describe('fetchAllCursorPages', () => {
  it('returns all items from a single page with hasMore=false', async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValue({ items: [1, 2, 3], hasMore: false, nextCursor: null })
    const result = await fetchAllCursorPages(fetchPage)
    expect(result).toEqual([1, 2, 3])
    expect(fetchPage).toHaveBeenCalledWith(null)
  })

  it('returns null when fetchPage returns null', async () => {
    const fetchPage = vi.fn().mockResolvedValue(null)
    const result = await fetchAllCursorPages(fetchPage)
    expect(result).toBeNull()
  })

  it('follows cursor across multiple pages', async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({ items: [1, 2], hasMore: true, nextCursor: 'cursor-2' })
      .mockResolvedValueOnce({ items: [3, 4], hasMore: false, nextCursor: null })
    const result = await fetchAllCursorPages(fetchPage)
    expect(result).toEqual([1, 2, 3, 4])
    expect(fetchPage).toHaveBeenNthCalledWith(1, null)
    expect(fetchPage).toHaveBeenNthCalledWith(2, 'cursor-2')
  })

  it('returns null when a subsequent page returns null', async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({ items: [1], hasMore: true, nextCursor: 'c2' })
      .mockResolvedValueOnce(null)
    const result = await fetchAllCursorPages(fetchPage)
    expect(result).toBeNull()
  })
})

describe('fetchAllNumberedPages', () => {
  it('returns all items from a single page', async () => {
    const fetchPage = vi.fn().mockResolvedValue({ items: ['a', 'b'], pages: 1 })
    const result = await fetchAllNumberedPages(fetchPage)
    expect(result).toEqual(['a', 'b'])
    expect(fetchPage).toHaveBeenCalledWith(1)
  })

  it('returns null when fetchPage returns null', async () => {
    const fetchPage = vi.fn().mockResolvedValue(null)
    const result = await fetchAllNumberedPages(fetchPage)
    expect(result).toBeNull()
  })

  it('fetches all numbered pages', async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({ items: ['a', 'b'], pages: 3 })
      .mockResolvedValueOnce({ items: ['c', 'd'], pages: 3 })
      .mockResolvedValueOnce({ items: ['e'], pages: 3 })
    const result = await fetchAllNumberedPages(fetchPage)
    expect(result).toEqual(['a', 'b', 'c', 'd', 'e'])
    expect(fetchPage).toHaveBeenCalledTimes(3)
  })

  it('returns null when a subsequent page returns null', async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({ items: ['a'], pages: 2 })
      .mockResolvedValueOnce(null)
    const result = await fetchAllNumberedPages(fetchPage)
    expect(result).toBeNull()
  })
})
