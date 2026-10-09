import { describe, expect, it } from 'vitest'
import vectors from './vectors.json'
import {
  evaluateFormula, fitPolynomial, FormulaError, FormulaProfileError, GRAVITY_FORMULA_MAX_LENGTH,
  GRAVITY_FORMULA_MAX_TOKENS, parseProfile, serializeProfile,
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
