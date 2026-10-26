/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import { describe, expect, it } from 'vitest'
import vectors from './vectors.json'
import {
  evaluateFormula, fitPolynomial, FormulaError, FormulaProfileError, GRAVITY_FORMULA_MAX_LENGTH,
  GRAVITY_FORMULA_MAX_TOKENS, normalizeFormula, parseProfile, serializeProfile,
  temperatureCorrectGravity, validateFormula
} from './index'

describe('shared gravity formula vectors', () => {
  it('shares parser limits with Python', () => {
    expect(GRAVITY_FORMULA_MAX_LENGTH).toBe(vectors.limits.maxLength)
    expect(GRAVITY_FORMULA_MAX_TOKENS).toBe(vectors.limits.maxTokens)
  })
  it.each(vectors.valid)('evaluates $formula at $tilt°', vector => {
    expect(evaluateFormula(vector.formula, vector.tilt, vector.temp, vector.unit as 'sg' | 'plato'))
      .toBeCloseTo(vector.gravitySg, 9)
  })
  it.each(vectors.invalidFormula)('rejects invalid formula %s', formula => {
    expect(() => validateFormula(formula)).toThrow(FormulaError)
  })
  it.each(vectors.invalidReading)('rejects unusable reading $formula', vector => {
    expect(() => evaluateFormula(vector.formula, vector.tilt, vector.temp, vector.unit as 'sg' | 'plato'))
      .toThrow(FormulaError)
  })
  it.each(vectors.temperatureCorrection)('corrects SG at $tempC °C', vector => {
    expect(temperatureCorrectGravity(vector.gravitySg, vector.tempC, vector.calibrationTempC))
      .toBeCloseTo(vector.correctedSg, 9)
  })
})

describe('sign before a power', () => {
  it('names the parenthesised forms that are valid', () => {
    expect(() => validateFormula('-tilt^2')).toThrow('ambiguous; add parentheses: (-tilt)^2 or -(tilt^2)')
  })
  it('keeps unambiguous signs valid', () => {
    expect(evaluateFormula('1.1+(-(tilt^2))/10000', 30, 20, 'sg')).toBeCloseTo(1.01, 9)
    expect(evaluateFormula('-8.1e-7*tilt^3+1.1', 30, 20, 'sg')).toBeCloseTo(1.07813, 9)
  })
})

describe('shared exponent normalization vectors', () => {
  const { normalization } = vectors
  it.each(normalization.valid)('rewrites $input', vector => {
    expect(normalizeFormula(vector.input)).toBe(vector.output)
    expect(normalizeFormula(vector.output)).toBe(vector.output)
  })
  it.each(normalization.notAnExponent)('leaves %s unchanged', formula => {
    expect(normalizeFormula(formula)).toBe(formula)
  })
  it.each(normalization.invalidExponent)('rejects the out-of-range exponent in %s', formula => {
    expect(() => normalizeFormula(formula)).toThrow(FormulaError)
  })
  it.each(normalization.invalidFormula)('rejects invalid formula %s', formula => {
    expect(() => validateFormula(formula)).toThrow(FormulaError)
  })
  it('is idempotent over the vectors and a random sample, and exact for random literals', () => {
    let seed = 20261011
    const next = () => { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296 }
    const pick = (chars: string) => chars[Math.floor(next() * chars.length)]
    const samples = [...normalization.valid.map(v => v.input), ...normalization.notAnExponent]
    const literals: string[] = []
    for (let i = 0; i < 500; i++) {
      const whole = String(Math.floor(next() * 100000))
      const fraction = next() < 0.5 ? '.' + Array.from({ length: Math.floor(next() * 7) }, () => pick('0123456789')).join('') : ''
      literals.push(`${whole}${fraction}${pick('eE')}${['', '+', '-'][Math.floor(next() * 3)]}${Math.floor(next() * 31)}`)
    }
    for (let i = 0; i < 2000; i++) {
      samples.push(Array.from({ length: 1 + Math.floor(next() * 14) }, () => pick('0123456789.eE+-*tilt_')).join(''))
    }
    for (const sample of [...samples, ...literals]) {
      let once: string
      try { once = normalizeFormula(sample) } catch { continue }
      expect(normalizeFormula(once)).toBe(once)
    }
    for (const literal of literals) expect(Number(normalizeFormula(literal))).toBe(Number(literal))
  })
  it.each(normalization.strayMarker)('leaves the stray exponent marker in %s unchanged and rejects it', formula => {
    expect(normalizeFormula(formula)).toBe(formula)
    expect(() => validateFormula(formula)).toThrow(FormulaError)
  })
  it('is idempotent for junk input and agrees with Python on 30000 token strings', () => {
    const tokens = ['0', '1', '2', '3', '5', '9', '.', 'e', 'E', '+', '-', '*', '^', '(', ')', 'tilt', 'temp', ' ']
    const count = 30000
    let seed = 20261011
    const draw = () => { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296 }
    const corpus = [...normalization.valid.map(v => v.input), ...normalization.notAnExponent,
      ...normalization.strayMarker, ...normalization.invalidExponent]
    for (let i = 0; i < count; i++) {
      const length = 1 + Math.floor(draw() * 16)
      corpus.push(Array.from({ length }, () => tokens[Math.floor(draw() * tokens.length)]).join(''))
    }
    const outcomes: string[] = []
    for (const sample of corpus) {
      let once: string
      try { once = normalizeFormula(sample) } catch { outcomes.push('!'); continue }
      expect(normalizeFormula(once)).toBe(once)
      outcomes.push(once)
    }
    let hash = 2166136261
    for (const char of outcomes.slice(-count).join('\n')) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619) >>> 0
    expect(hash.toString(16).padStart(8, '0')).toBe(normalization.junkDigest)
  })
  it('stays fast on pathological 200-character inputs', () => {
    const started = performance.now()
    for (const unit of ['1e', '1.e', '.1e+', '1e+1e', '0'.repeat(9) + 'e', '1.', 'e1', '1.1.1e1', '.e']) {
      try { normalizeFormula(unit.repeat(200).slice(0, GRAVITY_FORMULA_MAX_LENGTH)) } catch { /* rejected is fine */ }
    }
    expect(performance.now() - started).toBeLessThan(1000)
  })
  it('evaluates an exponent formula exactly like its plain decimal', () => {
    const source = '-8.1595791e-7*tilt^3+0.00010120890*tilt^2-0.0022066128*tilt+0.99997836'
    expect(evaluateFormula(source, 45, undefined)).toBe(evaluateFormula(normalizeFormula(source), 45, undefined))
  })
  it('stores the rewritten formula in a profile', () => {
    const document = serializeProfile('1e-3*tilt+1', 'sg', [])
    expect(JSON.parse(document).gravityFormula).toBe('0.001*tilt+1')
    expect(parseProfile(document.replace('0.001', '1e-3'), 'gravitymon').gravityFormula).toBe('0.001*tilt+1')
  })
})

describe('calibration tools', () => {
  const points = [
    { angle: 20, gravity: 1.02 }, { angle: 30, gravity: 1.03 },
    { angle: 40, gravity: 1.04 }, { angle: 50, gravity: 1.05 }
  ]

  it('fits an evaluable polynomial without changing points', () => {
    const before = JSON.stringify(points)
    const candidate = fitPolynomial(points, 2, 'sg')
    expect(candidate.maxDeviation).toBeLessThan(0.00001)
    expect(evaluateFormula(candidate.formula, 35, undefined)).toBeCloseTo(1.035, 4)
    expect(JSON.stringify(points)).toBe(before)
  })

  it('rejects singular fits', () => {
    expect(() => fitPolynomial(points.slice(0, 2), 3, 'sg')).toThrow(FormulaError)
  })

  it('round-trips a versioned profile in either unit and rejects a device outside the scope', () => {
    const document = serializeProfile('1+tilt/1000', 'sg', points)
    expect(parseProfile(document, 'gravitymon').gravityCalibrationData).toEqual(points)
    expect(parseProfile(document.replace('"sg"', '"plato"'), 'gravitymon').gravityFormulaUnit).toBe('plato')
    expect(() => parseProfile(document, 'kegmon')).toThrow(FormulaError)
  })

  it('reports every profile problem before changing editor state', () => {
    const bad = JSON.stringify({ format: 'wrong', version: 2, gravityFormula: 'bad(tilt)',
      gravityFormulaUnit: 'plato', gravityCalibrationData: [
        { angle: 20, gravity: 1.02 }, { angle: 20, gravity: 2 }
      ] })
    try { parseProfile(bad, 'gravitymon'); throw new Error('expected validation failure') }
    catch (error) {
      expect(error).toBeInstanceOf(FormulaProfileError)
      expect((error as FormulaProfileError).issues).toEqual(expect.arrayContaining([
        'Unsupported profile format', 'Unsupported profile version',
        'Duplicate angle 20'
      ]))
    }
  })
})
