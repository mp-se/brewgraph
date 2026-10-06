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

import { describe, it, expect } from 'vitest'
import { BrewfatherBatch } from '@/modules/classes'

describe('BrewfatherBatch - Data Class', () => {
  describe('Constructor', () => {
    it('should create with default values', () => {
      const bb = new BrewfatherBatch()
      expect(bb.brewfatherId).toBe('')
      expect(bb.name).toBe('')
      expect(bb.brewDate).toBe('')
      expect(bb.style).toBe('')
      expect(bb.brewer).toBe('')
      expect(bb.abv).toBe(0)
      expect(bb.ebc).toBe(0)
      expect(bb.ibu).toBe(0)
      expect(bb.og).toBe(0)
      expect(bb.fg).toBe(0)
      expect(bb.carbonation).toBe(0)
      expect(bb.fermentationSteps).toEqual([])
      expect(bb.dryHops).toEqual([])
    })

    it('should use provided values', () => {
      const bb = new BrewfatherBatch({
        brewfatherId: 'bf1',
        name: 'Summer IPA',
        brewDate: '2024-06-01',
        style: 'IPA',
        brewer: 'Magnus',
        abv: 6.5,
        ebc: 20,
        ibu: 45,
        og: 1.062,
        fg: 1.01,
        carbonation: 2.6,
        fermentationSteps: [{ order: 0, date: '', temp: 20, days: 7, type: 'Primary' }],
        dryHops: [{ name: 'Galaxy', amount: 60, trigger_hours_before: 96 }]
      })
      expect(bb.brewfatherId).toBe('bf1')
      expect(bb.name).toBe('Summer IPA')
      expect(bb.brewDate).toBe('2024-06-01')
      expect(bb.style).toBe('IPA')
      expect(bb.brewer).toBe('Magnus')
      expect(bb.abv).toBe(6.5)
      expect(bb.ebc).toBe(20)
      expect(bb.ibu).toBe(45)
      expect(bb.og).toBe(1.062)
      expect(bb.fg).toBe(1.01)
      expect(bb.carbonation).toBe(2.6)
      expect(bb.fermentationSteps).toEqual([{ order: 0, date: '', temp: 20, days: 7, type: 'Primary' }])
      expect(bb.dryHops).toEqual([{ name: 'Galaxy', amount: 60, trigger_hours_before: 96 }])
    })
  })

  describe('fromJson', () => {
    it('should create a BrewfatherBatch from JSON', () => {
      const json = {
        brewfatherId: 'bf2',
        name: 'Stout',
        brewDate: '2024-01-15',
        style: 'Imperial Stout',
        brewer: 'Alice',
        abv: 9.0,
        ebc: 80,
        ibu: 60,
        og: 1.09,
        fg: 1.02,
        carbonation: 2.2,
        fermentationSteps: [],
        dryHops: [{ name: 'Citra', amount: 40, trigger_hours_before: 48 }]
      }
      const bb = BrewfatherBatch.fromJson(json)
      expect(bb.brewfatherId).toBe('bf2')
      expect(bb.name).toBe('Stout')
      expect(bb.brewDate).toBe('2024-01-15')
      expect(bb.style).toBe('Imperial Stout')
      expect(bb.brewer).toBe('Alice')
      expect(bb.abv).toBe(9.0)
      expect(bb.ebc).toBe(80)
      expect(bb.ibu).toBe(60)
      expect(bb.og).toBe(1.09)
      expect(bb.fg).toBe(1.02)
      expect(bb.carbonation).toBe(2.2)
      expect(bb.fermentationSteps).toEqual([])
      expect(bb.dryHops).toEqual([{ name: 'Citra', amount: 40, trigger_hours_before: 48 }])
    })

    it('should default dryHops to an empty array when missing from JSON', () => {
      const bb = BrewfatherBatch.fromJson({ name: 'No Hops' })
      expect(bb.dryHops).toEqual([])
    })
  })

  describe('setters', () => {
    it('should update all fields via setters', () => {
      const bb = new BrewfatherBatch()
      bb.brewfatherId = 'bf3'
      bb.name = 'Lager'
      bb.brewDate = '2024-09-01'
      bb.style = 'Pilsner'
      bb.brewer = 'Bob'
      bb.abv = 4.5
      bb.ebc = 5
      bb.ibu = 20
      bb.og = 1.048
      bb.fg = 1.008
      bb.carbonation = 2.1
      bb.fermentationSteps = [{ order: 0, date: '', temp: 18, days: 5, type: 'Primary' }]
      bb.dryHops = [{ name: 'Mosaic', amount: 30, trigger_hours_before: 72 }]
      expect(bb.brewfatherId).toBe('bf3')
      expect(bb.name).toBe('Lager')
      expect(bb.abv).toBe(4.5)
      expect(bb.og).toBe(1.048)
      expect(bb.carbonation).toBe(2.1)
      expect(bb.fermentationSteps).toEqual([{ order: 0, date: '', temp: 18, days: 5, type: 'Primary' }])
      expect(bb.dryHops).toEqual([{ name: 'Mosaic', amount: 30, trigger_hours_before: 72 }])
    })
  })
})

describe('BrewfatherBatch - undefined branch coverage', () => {
  it('constructor uses defaults when fields are undefined', () => {
    const bb = new BrewfatherBatch({
      name: undefined,
      brewDate: undefined,
      style: undefined,
      brewer: undefined,
      abv: undefined,
      ebc: undefined,
      ibu: undefined,
      og: undefined,
      fg: undefined,
      carbonation: undefined,
      brewfatherId: undefined,
      fermentationSteps: undefined,
      dryHops: undefined
    })
    expect(bb.name).toBe('')
    expect(bb.brewDate).toBe('')
    expect(bb.style).toBe('')
    expect(bb.brewer).toBe('')
    expect(bb.abv).toBe(0)
    expect(bb.ebc).toBe(0)
    expect(bb.ibu).toBe(0)
    expect(bb.og).toBe(0)
    expect(bb.fg).toBe(0)
    expect(bb.carbonation).toBe(0)
    expect(bb.brewfatherId).toBe('')
    expect(bb.fermentationSteps).toEqual([])
    expect(bb.dryHops).toEqual([])
  })
})
