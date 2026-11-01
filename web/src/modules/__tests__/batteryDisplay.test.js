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

import { describe, expect, it } from 'vitest'
import { formatBattery } from '@/modules/batteryDisplay'

describe('formatBattery', () => {
  it('formats voltage and percentage independently', () => {
    expect(formatBattery(3.9, 87)).toBe('3.9 V · 87%')
  })

  it('formats whichever value is present', () => {
    expect(formatBattery(null, 87.25)).toBe('87.25%')
    expect(formatBattery(3.75, null)).toBe('3.75 V')
  })

  it('returns an empty string when both values are absent', () => {
    expect(formatBattery(null, undefined)).toBe('')
  })
})
