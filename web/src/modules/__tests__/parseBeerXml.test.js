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
import { parseBeerXml } from '@brewgraph/core'

describe('parseBeerXml', () => {
  it('should parse a valid BeerXML recipe', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Pale Ale</NAME>
        <BREWER>Test Brewer</BREWER>
        <OG>1.050</OG>
        <FG>1.010</FG>
        <IBU>40</IBU>
        <BATCH_SIZE>20</BATCH_SIZE>
        <CARBONATION>2.5</CARBONATION>
        <EST_COLOR>10</EST_COLOR>
        <NOTES>A great pale ale</NOTES>
        <STYLE>
          <NAME>Pale Ale</NAME>
        </STYLE>
        <YEAST>
          <NAME>California Ale</NAME>
        </YEAST>
        <PRIMARY_AGE>14</PRIMARY_AGE>
        <PRIMARY_TEMP>18</PRIMARY_TEMP>
        <SECONDARY_AGE>10</SECONDARY_AGE>
        <SECONDARY_TEMP>18</SECONDARY_TEMP>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result).not.toBeNull()
    expect(result?.name).toBe('Pale Ale')
    expect(result?.brewer).toBe('Test Brewer')
    expect(result?.og).toBe(1.05)
    expect(result?.fg).toBe(1.01)
    expect(result?.ibu).toBe(40)
    expect(result?.volume).toBe(20)
    expect(result?.carbonation).toBe(2.5)
    expect(result?.notes).toBe('A great pale ale')
    expect(result?.style).toBe('Pale Ale')
    expect(result?.yeast).toBe('California Ale')
  })

  it('should return null for invalid XML', () => {
    const xml = 'invalid xml <broken>'

    const result = parseBeerXml(xml)

    expect(result).toBeNull()
  })

  it('should return null when RECIPE element is missing', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <OTHER>Test</OTHER>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result).toBeNull()
  })

  it('should handle missing fields gracefully', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Simple Recipe</NAME>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result).not.toBeNull()
    expect(result?.name).toBe('Simple Recipe')
    expect(result?.brewer).toBe('')
    expect(result?.og).toBeNull()
    expect(result?.fg).toBeNull()
    expect(result?.ibu).toBeNull()
  })

  it('should convert SRM color to EBC', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
        <COLOR>10</COLOR>
        <COLOR_UNITS>SRM</COLOR_UNITS>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result?.ebc).toBe(Math.round(10 * 1.97))
  })

  it('should prefer EST_COLOR over COLOR', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
        <EST_COLOR>15</EST_COLOR>
        <COLOR>10</COLOR>
        <COLOR_UNITS>EBC</COLOR_UNITS>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result?.ebc).toBe(15)
  })

  it('should convert EST_COLOR from SRM to EBC when COLOR_UNITS is SRM', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
        <EST_COLOR>10</EST_COLOR>
        <COLOR_UNITS>SRM</COLOR_UNITS>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result?.ebc).toBe(Math.round(10 * 1.97))
  })

  it('should handle fermentation steps correctly', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
        <PRIMARY_AGE>14</PRIMARY_AGE>
        <PRIMARY_TEMP>18</PRIMARY_TEMP>
        <SECONDARY_AGE>10</SECONDARY_AGE>
        <SECONDARY_TEMP>16</SECONDARY_TEMP>
        <TERTIARY_AGE>30</TERTIARY_AGE>
        <TERTIARY_TEMP>12</TERTIARY_TEMP>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result?.fermentationSteps).toHaveLength(3)
    expect(result?.fermentationSteps[0]).toEqual({
      order: 0,
      name: 'Primary',
      type: 'Hold',
      temp: 18,
      days: 14,
      date: '',
      control: 'fridge'
    })
    expect(result?.fermentationSteps[1]).toEqual({
      order: 1,
      name: 'Secondary',
      type: 'Hold',
      temp: 16,
      days: 10,
      date: '',
      control: 'fridge'
    })
    expect(result?.fermentationSteps[2]).toEqual({
      order: 2,
      name: 'Conditioning',
      type: 'Hold',
      temp: 12,
      days: 30,
      date: '',
      control: 'fridge'
    })
  })

  it('should skip secondary fermentation if SECONDARY_AGE is 0', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
        <PRIMARY_AGE>14</PRIMARY_AGE>
        <PRIMARY_TEMP>18</PRIMARY_TEMP>
        <SECONDARY_AGE>0</SECONDARY_AGE>
        <SECONDARY_TEMP>16</SECONDARY_TEMP>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result?.fermentationSteps).toHaveLength(1)
    expect(result?.fermentationSteps[0].name).toBe('Primary')
  })

  it('should skip tertiary fermentation if missing', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
        <PRIMARY_AGE>14</PRIMARY_AGE>
        <PRIMARY_TEMP>18</PRIMARY_TEMP>
        <SECONDARY_AGE>10</SECONDARY_AGE>
        <SECONDARY_TEMP>16</SECONDARY_TEMP>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result?.fermentationSteps).toHaveLength(2)
  })

  it('should use default temperature when PRIMARY_TEMP is missing', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
        <PRIMARY_AGE>14</PRIMARY_AGE>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result?.fermentationSteps[0].temp).toBe(20)
  })

  it('should handle empty fermentation steps', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result?.fermentationSteps).toEqual([])
  })

  it('should handle numeric parsing errors gracefully', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
        <OG>not-a-number</OG>
        <FG>invalid</FG>
        <IBU>abc</IBU>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result).not.toBeNull()
    expect(result?.og).toBeNull()
    expect(result?.fg).toBeNull()
    expect(result?.ibu).toBeNull()
  })

  it('should handle COLOR_METHOD as alternative to COLOR_UNITS', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
        <EST_COLOR>10</EST_COLOR>
        <COLOR_METHOD>SRM</COLOR_METHOD>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result?.ebc).toBe(Math.round(10 * 1.97))
  })

  it('should parse multiple yeast correctly (use first one)', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
        <YEAST>
          <NAME>California Ale</NAME>
        </YEAST>
        <YEAST>
          <NAME>English Ale</NAME>
        </YEAST>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result?.yeast).toBe('California Ale')
  })

  it('should parse style correctly', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
        <STYLE>
          <NAME>American Pale Ale</NAME>
        </STYLE>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result?.style).toBe('American Pale Ale')
  })

  it('should parse dry hop entries and convert kg to g, minutes to hours', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
        <HOPS>
          <HOP>
            <NAME>Warrior</NAME>
            <AMOUNT>0.025</AMOUNT>
            <USE>Boil</USE>
            <TIME>30</TIME>
          </HOP>
          <HOP>
            <NAME>Galaxy</NAME>
            <AMOUNT>0.06</AMOUNT>
            <USE>Dry Hop</USE>
            <TIME>5760</TIME>
          </HOP>
        </HOPS>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result?.dryHops).toHaveLength(1)
    expect(result?.dryHops[0]).toEqual({
      name: 'Galaxy',
      amount: 60,
      triggerHoursBefore: 96
    })
  })

  it('should exclude non-dry-hop USE values', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
        <HOPS>
          <HOP>
            <NAME>Warrior</NAME>
            <AMOUNT>0.025</AMOUNT>
            <USE>Boil</USE>
            <TIME>30</TIME>
          </HOP>
          <HOP>
            <NAME>Nelson Sauvin</NAME>
            <AMOUNT>0.012</AMOUNT>
            <USE>Aroma</USE>
            <TIME>20</TIME>
          </HOP>
        </HOPS>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result?.dryHops).toEqual([])
  })

  it('should match use case-insensitively', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
        <HOPS>
          <HOP>
            <NAME>Citra</NAME>
            <AMOUNT>0.03</AMOUNT>
            <USE>dry hop</USE>
            <TIME>2880</TIME>
          </HOP>
        </HOPS>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result?.dryHops).toHaveLength(1)
    expect(result?.dryHops[0].amount).toBe(30)
    expect(result?.dryHops[0].triggerHoursBefore).toBe(48)
  })

  it('should return an empty dryHops array when there are no HOPS', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result?.dryHops).toEqual([])
  })

  it('should return empty string for missing style', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <RECIPES>
      <RECIPE>
        <NAME>Test</NAME>
      </RECIPE>
    </RECIPES>`

    const result = parseBeerXml(xml)

    expect(result?.style).toBe('')
  })
})
