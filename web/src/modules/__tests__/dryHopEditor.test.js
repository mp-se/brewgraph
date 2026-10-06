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

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { dryHopsPayload, persistDryHops } from '@/modules/dryHopEditor'

vi.mock('@/ui', () => ({
  logDebug: vi.fn()
}))

const mockApiOk = vi.fn()
vi.mock('@/modules/apiClient', () => ({
  apiOk: (...args) => mockApiOk(...args)
}))

describe('dryHopEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('dryHopsPayload', () => {
    it('should map staged hops to the BatchDryHopCreate payload shape', () => {
      const staged = [
        { name: 'Citra', amount: 50, triggerHoursBefore: 48 },
        { name: 'Mosaic', amount: 30, triggerHoursBefore: 24 }
      ]

      const result = dryHopsPayload(staged)

      expect(result).toHaveLength(2)
      expect(result[0]).toEqual({
        name: 'Citra',
        amount: 50,
        triggerMethod: 'hours_before_completion',
        triggerHoursBefore: 48,
        triggerGravity: null
      })
      expect(result[1]).toEqual({
        name: 'Mosaic',
        amount: 30,
        triggerMethod: 'hours_before_completion',
        triggerHoursBefore: 24,
        triggerGravity: null
      })
    })

    it('should clamp triggerHoursBefore to minimum 1 for fractional values', () => {
      const staged = [{ name: 'Galaxy', amount: 20, triggerHoursBefore: 0.4 }]

      const result = dryHopsPayload(staged)

      expect(result[0].triggerHoursBefore).toBe(1)
    })

    it('should round triggerHoursBefore to the nearest integer', () => {
      const staged = [{ name: 'Simcoe', amount: 25, triggerHoursBefore: 36.7 }]

      const result = dryHopsPayload(staged)

      expect(result[0].triggerHoursBefore).toBe(37)
    })

    it('should return an empty array when given no hops', () => {
      expect(dryHopsPayload([])).toEqual([])
    })

    it('should always set triggerMethod to hours_before_completion and triggerGravity to null', () => {
      const staged = [{ name: 'Amarillo', amount: 40, triggerHoursBefore: 72 }]

      const [item] = dryHopsPayload(staged)

      expect(item.triggerMethod).toBe('hours_before_completion')
      expect(item.triggerGravity).toBeNull()
    })
  })

  describe('persistDryHops', () => {
    it('should return true immediately when the staged list is empty (no-op)', async () => {
      const result = await persistDryHops('batch-123', [])

      expect(mockApiOk).not.toHaveBeenCalled()
      expect(result).toBe(true)
    })

    it('should POST the correct payload to batches/<id>/dry-hops', async () => {
      mockApiOk.mockResolvedValueOnce(true)
      const hops = [{ name: 'Citra', amount: 50, triggerHoursBefore: 48 }]

      const result = await persistDryHops('batch-abc', hops)

      expect(mockApiOk).toHaveBeenCalledExactlyOnceWith('POST', 'batches/batch-abc/dry-hops', [
        {
          name: 'Citra',
          amount: 50,
          triggerMethod: 'hours_before_completion',
          triggerHoursBefore: 48,
          triggerGravity: null
        }
      ])
      expect(result).toBe(true)
    })

    it('should return false when the API call fails', async () => {
      mockApiOk.mockResolvedValueOnce(false)
      const hops = [{ name: 'Mosaic', amount: 30, triggerHoursBefore: 24 }]

      const result = await persistDryHops('batch-xyz', hops)

      expect(result).toBe(false)
    })

    it('should POST all hops in a single request', async () => {
      mockApiOk.mockResolvedValueOnce(true)
      const hops = [
        { name: 'Citra', amount: 50, triggerHoursBefore: 48 },
        { name: 'Mosaic', amount: 30, triggerHoursBefore: 24 },
        { name: 'Galaxy', amount: 20, triggerHoursBefore: 12 }
      ]

      await persistDryHops('batch-multi', hops)

      expect(mockApiOk).toHaveBeenCalledOnce()
      const payload = mockApiOk.mock.calls[0][2]
      expect(payload).toHaveLength(3)
    })
  })
})
