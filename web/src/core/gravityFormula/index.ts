/** Framework-neutral, bounded gravity-formula language and calibration tools. */
import { gravityToPlato, platoToGravity } from '../calculations/units'

export const GRAVITY_FORMULA_MAX_LENGTH = 200
export const GRAVITY_FORMULA_MAX_TOKENS = 128
export const GRAVITY_CALIBRATION_MAX_POINTS = 20
export const MIN_VALID_ANGLE_DEG = 15
export const MAX_VALID_ANGLE_DEG = 90
export const MIN_VALID_GRAVITY_SG = 0.98
export const MAX_VALID_GRAVITY_SG = 1.25
const MAX_LITERAL = 1_000_000
const MAX_INTERMEDIATE = 1_000_000_000_000

export type FormulaUnit = 'sg' | 'plato'
export type CalibrationPoint = { angle: number; gravity: number }
type Node = { op: 'num'; value: number } | { op: 'var'; name: 'tilt' | 'temp' } |
  { op: 'u+'; child: Node } | { op: 'u-'; child: Node } | { op: '^'; left: Node; exponent: number } |
  { op: '+' | '-' | '*' | '/'; left: Node; right: Node }

export class FormulaError extends Error { name = 'FormulaError' }
export class FormulaProfileError extends FormulaError {
  name = 'FormulaProfileError'
  constructor(public readonly issues: string[]) { super(issues.join('; ')) }
}

function tokenize(formula: string): string[] {
  if (!formula || formula.length > GRAVITY_FORMULA_MAX_LENGTH) throw new FormulaError('Formula is empty or too long')
  const tokens: string[] = []
  const pattern = /(?:\d+(?:\.\d*)?|\.\d+)|[A-Za-z_]\w*|[-()+*/^]/y
  let pos = 0
  while (pos < formula.length) {
    if (/[ \t\r\n\f\v]/.test(formula[pos])) { pos++; continue }
    pattern.lastIndex = pos
    const match = pattern.exec(formula)
    if (!match) throw new FormulaError(`Invalid formula character at position ${pos + 1}`)
    tokens.push(match[0])
    if (tokens.length > GRAVITY_FORMULA_MAX_TOKENS) throw new FormulaError('Formula exceeds token limit')
    pos = pattern.lastIndex
  }
  return tokens
}

class Parser {
  private index = 0
  constructor(private readonly tokens: string[]) {}
  peek(): string | undefined { return this.tokens[this.index] }
  take(): string {
    const token = this.tokens[this.index++]
    if (token === undefined) throw new FormulaError('Unexpected end of formula')
    return token
  }
  expression(): Node {
    let node = this.term()
    while (this.peek() === '+' || this.peek() === '-') {
      const op = this.take() as '+' | '-'
      node = { op, left: node, right: this.term() }
    }
    return node
  }
  term(): Node {
    let node = this.unary()
    while (this.peek() === '*' || this.peek() === '/') {
      const op = this.take() as '*' | '/'
      node = { op, left: node, right: this.unary() }
    }
    return node
  }
  unary(): Node {
    if (this.peek() === '+' || this.peek() === '-') return { op: `u${this.take()}` as 'u+' | 'u-', child: this.unary() }
    return this.power()
  }
  power(): Node {
    let node = this.primary()
    if (this.peek() === '^') {
      this.take()
      const exponent = this.take()
      if (!/^[1-6]$/.test(exponent)) throw new FormulaError('Power must be an integer literal from 1 to 6')
      node = { op: '^', left: node, exponent: Number(exponent) }
    }
    return node
  }
  primary(): Node {
    const token = this.take()
    if (token === '(') {
      const node = this.expression()
      if (this.take() !== ')') throw new FormulaError('Missing closing parenthesis')
      return node
    }
    if (token === 'tilt' || token === 'temp') return { op: 'var', name: token }
    if (/^(?:\d|\.)/.test(token)) {
      const value = Number(token)
      if (!Number.isFinite(value) || value > MAX_LITERAL) throw new FormulaError('Numeric literal is too large')
      return { op: 'num', value }
    }
    throw new FormulaError(`Unknown identifier or unexpected token: ${token}`)
  }
}

export function parseFormula(formula: string): Node {
  const parser = new Parser(tokenize(formula))
  const node = parser.expression()
  if (parser.peek() !== undefined) throw new FormulaError(`Unexpected token: ${parser.peek()}`)
  return node
}

export function validateFormula(formula: string): void { parseFormula(formula) }

function value(node: Node, tilt: number, temp?: number): number {
  if (node.op === 'num') return node.value
  if (node.op === 'var') {
    if (node.name === 'tilt') return tilt
    if (temp === undefined || !Number.isFinite(temp)) throw new FormulaError('Temperature is required by this formula')
    return temp
  }
  if (node.op === 'u+' || node.op === 'u-') {
    const result = value(node.child, tilt, temp)
    return node.op === 'u+' ? result : -result
  }
  const left = value(node.left, tilt, temp)
  let result: number
  if (node.op === '^') result = left ** node.exponent
  else {
    const right = value(node.right, tilt, temp)
    if (node.op === '+') result = left + right
    else if (node.op === '-') result = left - right
    else if (node.op === '*') result = left * right
    else {
      if (right === 0) throw new FormulaError('Division by zero')
      result = left / right
    }
  }
  if (!Number.isFinite(result) || Math.abs(result) > MAX_INTERMEDIATE) throw new FormulaError('Formula result exceeds intermediate limit')
  return result
}

export function temperatureCorrectGravity(gravitySg: number, tempC: number, calibrationTempC = 20): number {
  const factor = (celsius: number) => {
    const fahrenheit = celsius * 1.8 + 32
    return 1.00130346 - 0.000134722124 * fahrenheit +
      0.00000204052596 * fahrenheit ** 2 - 0.00000000232820948 * fahrenheit ** 3
  }
  return gravitySg * factor(tempC) / factor(calibrationTempC)
}

export function evaluateFormula(formula: string, tilt: number, temp: number | undefined,
  unit: FormulaUnit = 'sg', correctTemperature = false, calibrationTempC = 20): number {
  if (!Number.isFinite(tilt) || tilt < MIN_VALID_ANGLE_DEG || tilt > MAX_VALID_ANGLE_DEG) throw new FormulaError('Angle is outside valid range')
  if (unit !== 'sg' && unit !== 'plato') throw new FormulaError('Unknown formula unit')
  const raw = value(parseFormula(formula), tilt, temp)
  let gravity = unit === 'sg' ? raw : platoToGravity(raw)
  if (correctTemperature) {
    if (temp === undefined || !Number.isFinite(temp)) throw new FormulaError('Temperature is required for correction')
    gravity = temperatureCorrectGravity(gravity, temp, calibrationTempC)
  }
  if (!Number.isFinite(gravity) || gravity < MIN_VALID_GRAVITY_SG || gravity > MAX_VALID_GRAVITY_SG) throw new FormulaError('Gravity is outside valid range')
  return gravity
}

export function validateCalibrationPoints(points: CalibrationPoint[]): void {
  if (!Array.isArray(points) || points.length > GRAVITY_CALIBRATION_MAX_POINTS) throw new FormulaError('Too many calibration points')
  const angles = new Set<number>()
  for (const point of points) {
    if (!point || !Number.isFinite(point.angle) || point.angle < MIN_VALID_ANGLE_DEG || point.angle > MAX_VALID_ANGLE_DEG ||
        !Number.isFinite(point.gravity) || point.gravity < MIN_VALID_GRAVITY_SG || point.gravity > MAX_VALID_GRAVITY_SG) {
      throw new FormulaError('Calibration point is outside valid range')
    }
    if (angles.has(point.angle)) throw new FormulaError('Calibration angles must be distinct')
    angles.add(point.angle)
  }
}

export type FitCandidate = { degree: number; formula: string; deviations: number[]; maxDeviation: number }

/** Fit on normalized angles, then serialize a directly evaluable polynomial. */
export function fitPolynomial(points: CalibrationPoint[], degree: number, unit: FormulaUnit): FitCandidate {
  validateCalibrationPoints(points)
  if (!Number.isInteger(degree) || degree < 1 || degree > 4 || points.length < degree + 1) {
    throw new FormulaError('A degree 1–4 fit needs at least degree + 1 distinct points')
  }
  const mean = points.reduce((sum, point) => sum + point.angle, 0) / points.length
  const scale = Math.max(...points.map(point => Math.abs(point.angle - mean)))
  if (scale === 0) throw new FormulaError('Calibration angles must be distinct')
  const n = degree + 1
  const matrix = Array.from({ length: n }, () => Array<number>(n + 1).fill(0))
  for (const point of points) {
    const x = (point.angle - mean) / scale
    const powers = Array.from({ length: 2 * degree + 1 }, (_, k) => x ** k)
    const y = unit === 'plato' ? gravityToPlato(point.gravity) : point.gravity
    for (let row = 0; row < n; row++) {
      for (let col = 0; col < n; col++) matrix[row][col] += powers[row + col]
      matrix[row][n] += y * powers[row]
    }
  }
  for (let col = 0; col < n; col++) {
    let pivot = col
    for (let row = col + 1; row < n; row++) if (Math.abs(matrix[row][col]) > Math.abs(matrix[pivot][col])) pivot = row
    if (Math.abs(matrix[pivot][col]) < 1e-10) throw new FormulaError('Fit is singular or ill-conditioned; spread the angles farther apart')
    ;[matrix[col], matrix[pivot]] = [matrix[pivot], matrix[col]]
    const divisor = matrix[col][col]
    for (let k = col; k <= n; k++) matrix[col][k] /= divisor
    for (let row = 0; row < n; row++) {
      if (row === col) continue
      const multiple = matrix[row][col]
      for (let k = col; k <= n; k++) matrix[row][k] -= multiple * matrix[col][k]
    }
  }
  const coeff = matrix.map(row => row[n])
  const term = `(tilt-${Number(mean.toPrecision(10))})/${Number(scale.toPrecision(10))}`
  const formula = coeff.map((c, power) => {
    // Exponent notation is deliberately absent from the formula grammar.
    const number = c.toFixed(15).replace(/\.?0+$/, '') || '0'
    return power === 0 ? number : `${number}*(${term})${power > 1 ? `^${power}` : ''}`
  }).join('+')
  validateFormula(formula)
  const deviations = points.map(point => {
    const result = evaluateFormula(formula, point.angle, undefined, unit)
    return (unit === 'plato' ? gravityToPlato(result) - gravityToPlato(point.gravity) : result - point.gravity)
  })
  return { degree, formula, deviations, maxDeviation: Math.max(...deviations.map(Math.abs)) }
}

export type FormulaProfile = { format: 'brewgraph-gravity-formula'; version: 1; gravityFormula: string | null;
  gravityFormulaUnit: FormulaUnit | null; gravityCalibrationData: CalibrationPoint[] }

export function parseProfile(raw: string, deviceType: string): FormulaProfile {
  let data: unknown
  try { data = JSON.parse(raw) }
  catch { throw new FormulaProfileError(['Profile must be valid JSON']) }
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new FormulaProfileError(['Profile must be an object'])
  const profile = data as Record<string, unknown>
  const issues: string[] = []
  const allowed = new Set(['format', 'version', 'gravityFormula', 'gravityFormulaUnit', 'gravityCalibrationData'])
  for (const key of Object.keys(profile)) if (!allowed.has(key)) issues.push('Unexpected field ' + key)
  if (profile.format !== 'brewgraph-gravity-formula') issues.push('Unsupported profile format')
  if (profile.version !== 1) issues.push('Unsupported profile version')
  if (profile.gravityFormula !== null && typeof profile.gravityFormula !== 'string') issues.push('Invalid formula field')
  const formula = typeof profile.gravityFormula === 'string' ? profile.gravityFormula.trim() || null : null
  if (formula) {
    try { validateFormula(formula) }
    catch (error) { issues.push((error as Error).message) }
  }
  const unit = profile.gravityFormulaUnit ?? null
  if (unit !== null && unit !== 'sg' && unit !== 'plato') issues.push('Invalid formula unit')
  if (!['gravitymon', 'ispindel', 'rapt_pill', ''].includes(deviceType)) issues.push('Device cannot carry calibration')
  const points = profile.gravityCalibrationData
  if (!Array.isArray(points)) issues.push('Calibration points must be an array')
  else {
    if (points.length > GRAVITY_CALIBRATION_MAX_POINTS) issues.push('More than 20 points')
    const angles = new Set<number>()
    points.forEach((point: unknown, index: number) => {
      if (!point || typeof point !== 'object' || Array.isArray(point)) {
        issues.push('Point ' + (index + 1) + ' must be an object'); return
      }
      const p = point as Record<string, unknown>
      if (Object.keys(p).some(key => key !== 'angle' && key !== 'gravity')) issues.push('Point ' + (index + 1) + ' has unexpected fields')
      if (typeof p.angle !== 'number' || !Number.isFinite(p.angle) || p.angle < MIN_VALID_ANGLE_DEG || p.angle > MAX_VALID_ANGLE_DEG) {
        issues.push('Point ' + (index + 1) + ' angle must be between 15 and 90')
      } else if (angles.has(p.angle)) issues.push('Duplicate angle ' + p.angle)
      else angles.add(p.angle)
      if (typeof p.gravity !== 'number' || !Number.isFinite(p.gravity) || p.gravity < MIN_VALID_GRAVITY_SG || p.gravity > MAX_VALID_GRAVITY_SG) {
        issues.push('Point ' + (index + 1) + ' gravity must be between 0.980 and 1.250 SG')
      }
    })
  }
  if (issues.length) throw new FormulaProfileError(issues)
  return { format: 'brewgraph-gravity-formula', version: 1, gravityFormula: formula,
    gravityFormulaUnit: unit as FormulaUnit | null, gravityCalibrationData: points as CalibrationPoint[] }
}

export function serializeProfile(formula: string | null, unit: FormulaUnit | null,
  points: CalibrationPoint[]): string {
  if (formula) validateFormula(formula)
  validateCalibrationPoints(points)
  return JSON.stringify({ format: 'brewgraph-gravity-formula', version: 1, gravityFormula: formula,
    gravityFormulaUnit: unit, gravityCalibrationData: points } satisfies FormulaProfile, null, 2)
}
