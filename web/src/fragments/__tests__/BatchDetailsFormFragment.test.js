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

// deps ../BatchDetailsFormFragment.vue

import { describe, it, expect } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import BatchDetailsFormFragment from '../BatchDetailsFormFragment.vue'

const abvHelpFor = (batch) => {
  const html = shallowMount(BatchDetailsFormFragment, { props: { batch } }).html()
  const alcohol = html.slice(html.indexOf('label="Alcohol"'))
  return /help="([^"]*)"/.exec(alcohol)?.[1]
}

describe('BatchDetailsFormFragment ABV', () => {
  it('shows the measured ABV and a dash when there is none', () => {
    expect(abvHelpFor({ og: null, fg: null, abv: 5, abvMeasured: 5.5 })).toBe('Measured: 5.5%')
    expect(abvHelpFor({ og: null, fg: null, abv: 5, abvMeasured: null })).toBe('Measured: —')
  })

  it('says the planned ABV is calculated while it matches OG and FG', () => {
    expect(abvHelpFor({ og: 1.06, fg: 1.01, abv: 6.6, abvMeasured: null })).toBe(
      'Calculated from OG and FG. Measured: —'
    )
    expect(abvHelpFor({ og: 1.06, fg: 1.01, abv: 5.0, abvMeasured: null })).toBe('Measured: —')
  })
})
