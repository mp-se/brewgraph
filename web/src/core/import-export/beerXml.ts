/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 *
 * Parses a BeerXML 1.0 file and returns fields mapped to BrewGraph's batch model.
 * Runs entirely client-side — no server round-trip.
 */

export interface BeerXmlImport {
  name: string
  style: string
  brewer: string
  og: number | null
  fg: number | null
  ibu: number | null
  ebc: number | null
  volume: number | null
  carbonation: number | null
  notes: string
  yeast: string
  fermentationSteps: BeerXmlFermentationStep[]
  dryHops: BeerXmlDryHop[]
}

export interface BeerXmlDryHop {
  name: string
  amount: number
  triggerHoursBefore: number
}

export interface BeerXmlFermentationStep {
  order: number
  name: string
  type: string
  temp: number
  days: number
  date: string
  control: string
}

function getText(parent: Element, tag: string): string {
  return parent.querySelector(tag)?.textContent?.trim() ?? ''
}

function getFloat(parent: Element, tag: string): number | null {
  const v = getText(parent, tag)
  const n = parseFloat(v)
  return isNaN(n) ? null : n
}

/** Convert SRM to EBC (SRM × 1.97) */
function srmToEbc(srm: number): number {
  return Math.round(srm * 1.97)
}

export function parseBeerXml(xml: string): BeerXmlImport | null {
  let doc: Document
  try {
    doc = new DOMParser().parseFromString(xml, 'text/xml')
  } catch {
    return null
  }

  const recipe = doc.querySelector('RECIPE')
  if (!recipe) return null

  const name    = getText(recipe, 'NAME')
  const brewer  = getText(recipe, 'BREWER')
  const og      = getFloat(recipe, 'OG')
  const fg      = getFloat(recipe, 'FG')
  const ibu     = getFloat(recipe, 'IBU')
  const volume  = getFloat(recipe, 'BATCH_SIZE')        // litres
  const carbonation = getFloat(recipe, 'CARBONATION')   // volumes
  const notes   = getText(recipe, 'NOTES')

  // Colour — prefer EBC, fall back to SRM
  let ebc: number | null = getFloat(recipe, 'EST_COLOR')
  const colorUnit = getText(recipe, 'COLOR_UNITS') || getText(recipe, 'COLOR_METHOD') || 'EBC'
  if (ebc !== null && colorUnit.toUpperCase().includes('SRM')) {
    ebc = srmToEbc(ebc)
  }
  if (ebc === null) {
    const srm = getFloat(recipe, 'COLOR')
    if (srm !== null) ebc = srmToEbc(srm)
  }

  // Style
  const styleEl = recipe.querySelector('STYLE')
  const style = styleEl ? getText(styleEl, 'NAME') : ''

  // Yeast — first YEAST entry name
  const yeastEl = recipe.querySelector('YEAST')
  const yeast = yeastEl ? getText(yeastEl, 'NAME') : ''

  // Fermentation steps from MASH > MASH_STEPS for mash, and FERMENTATION_STAGES
  const fermentationSteps: BeerXmlFermentationStep[] = []

  // BeerXML 1.0 stores primary/secondary/tertiary as top-level recipe fields
  const primaryDays  = getFloat(recipe, 'PRIMARY_AGE')
  const primaryTemp  = getFloat(recipe, 'PRIMARY_TEMP')
  const secondaryDays = getFloat(recipe, 'SECONDARY_AGE')
  const secondaryTemp = getFloat(recipe, 'SECONDARY_TEMP')
  const tertiaryDays  = getFloat(recipe, 'TERTIARY_AGE')
  const tertiaryTemp  = getFloat(recipe, 'TERTIARY_TEMP')

  if (primaryDays !== null) {
    fermentationSteps.push({
      order: 0,
      name: 'Primary',
      type: 'Hold',
      temp: primaryTemp ?? 20,
      days: primaryDays,
      date: '',
      control: 'fridge'
    })
  }
  if (secondaryDays !== null && secondaryDays > 0) {
    fermentationSteps.push({
      order: 1,
      name: 'Secondary',
      type: 'Hold',
      temp: secondaryTemp ?? 20,
      days: secondaryDays,
      date: '',
      control: 'fridge'
    })
  }
  if (tertiaryDays !== null && tertiaryDays > 0) {
    fermentationSteps.push({
      order: 2,
      name: 'Conditioning',
      type: 'Hold',
      temp: tertiaryTemp ?? 20,
      days: tertiaryDays,
      date: '',
      control: 'fridge'
    })
  }

  // Dry hops - BeerXML 1.0 stores <TIME> in minutes for every HOP regardless of
  // <USE> (Boil/Aroma/Dry Hop all use minutes); <AMOUNT> is always in kilograms.
  const dryHops: BeerXmlDryHop[] = []
  const hopEls = recipe.querySelectorAll('HOPS > HOP')
  hopEls.forEach((hopEl) => {
    const use = getText(hopEl, 'USE')
    if (!use.toLowerCase().includes('dry hop')) return
    const name = getText(hopEl, 'NAME')
    const amountKg = getFloat(hopEl, 'AMOUNT') ?? 0
    const timeMinutes = getFloat(hopEl, 'TIME') ?? 0
    dryHops.push({
      name,
      amount: amountKg * 1000,
      triggerHoursBefore: timeMinutes / 60
    })
  })

  return { name, style, brewer, og, fg, ibu, ebc, volume, carbonation, notes, yeast, fermentationSteps, dryHops }
}
