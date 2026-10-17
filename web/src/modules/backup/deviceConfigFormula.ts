/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 */

import {
  GRAVITY_CALIBRATION_MAX_POINTS,
  normalizeFormula,
  validateCalibrationPoints,
  validateFormula,
  type CalibrationPoint,
  type FormulaUnit
} from '@/core/gravityFormula'

/*
 * A backup made before the formula fields existed keeps a gravity device's formula only inside
 * the captured firmware configuration of the device row: `config` is either the capture envelope
 * ({ v, kind, capturedAt, source, data: { raw } }) around the firmware answer, or the firmware
 * answer itself, as BrewLogger stored it. The answer holds
 * ({ config: { gravity_formula, gravity_unit | gravity_format, formula_calculation_data } }).
 * Only those three keys are read; nothing else in the capture is copied, logged or returned.
 */

const GRAVITY_DEVICE_TYPES = new Set(['gravitymon', 'ispindel', 'rapt_pill'])

export interface DeviceFormulaRecord {
  deviceType?: string | null
  config?: unknown
  gravityFormula?: string | null
  gravityFormulaUnit?: FormulaUnit | null
  gravityCalibrationData?: CalibrationPoint[] | null
}

export interface DeviceFormulaFill {
  /** The formula fields to set on the device; a field is present only when the capture supplied it. */
  fields: {
    gravityFormula?: string
    gravityFormulaUnit?: FormulaUnit
    gravityCalibrationData?: CalibrationPoint[]
  }
  /** What the capture held but could not be used, in words for the person restoring. */
  problems: string[]
}

type Json = Record<string, unknown>

/** A JSON object given as an object or as a JSON string; anything else (or malformed) is null. */
function asObject(value: unknown): Json | null {
  let parsed = value
  if (typeof parsed === 'string') {
    if (!parsed.trim()) return null
    try { parsed = JSON.parse(parsed) } catch { return null }
  }
  return parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed) ? (parsed as Json) : null
}

/** The firmware answer is either wrapped in the capture envelope or stored as it came. */
function capturedFirmwareConfig(config: unknown): Json | null {
  const outer = asObject(config)
  const data = asObject(outer?.data)
  return asObject(asObject(data?.raw)?.config) ?? asObject(outer?.config)
}

function capturedUnit(firmware: Json): FormulaUnit | null {
  for (const key of ['gravity_unit', 'gravity_format']) {
    const value = firmware[key]
    if (value === 'G') return 'sg'
    if (value === 'P') return 'plato'
  }
  return null
}

function capturedPoints(firmware: Json, problems: string[]): CalibrationPoint[] {
  const entries = firmware.formula_calculation_data
  if (!Array.isArray(entries)) return []
  const points: CalibrationPoint[] = []
  const angles = new Set<number>()
  let rejected = 0
  for (const entry of entries) {
    const slot = asObject(entry)
    // An entry with angle 0 is an unused slot, whatever its gravity.
    if (!slot || typeof slot.a !== 'number' || slot.a === 0) continue
    if (points.length >= GRAVITY_CALIBRATION_MAX_POINTS) break
    const point = { angle: slot.a, gravity: slot.g as number }
    try { validateCalibrationPoints([point]) } catch { rejected++; continue }
    if (angles.has(point.angle)) { rejected++; continue }
    angles.add(point.angle)
    points.push(point)
  }
  if (rejected) problems.push(`${rejected} calibration point${rejected === 1 ? '' : 's'} left out (outside the valid range or repeated)`)
  return points
}

export const FORMULA_NOT_APPLIED =
  'The formula was not applied (the device already has a formula or calibration points)'

/**
 * Fill a device's formula fields from its captured firmware configuration.
 *
 * Does nothing unless the device can carry a formula and holds neither a formula nor calibration
 * points, so a formula or point that is already set is never overwritten. The unit is not part of
 * that test (every gravity device has an effective one) and is replaced by the configuration's.
 * When the device already has a formula or points and the configuration carries one, nothing is
 * filled and the problems say so. The formula is rewritten from exponent notation and validated
 * like any other; one the language rejects is left out and reported, and the unit and points are
 * still filled. "Apply formula" is never touched.
 */
export function fillFormulaFromConfig(device: DeviceFormulaRecord): DeviceFormulaFill {
  const fill: DeviceFormulaFill = { fields: {}, problems: [] }
  // Only an explicit gravity type is filled; a missing type is not assumed to be one.
  if (!device.deviceType || !GRAVITY_DEVICE_TYPES.has(device.deviceType)) return fill
  const firmware = capturedFirmwareConfig(device.config)
  if (!firmware) return fill

  const source = firmware.gravity_formula
  if (typeof source === 'string' && source.trim()) {
    try {
      const formula = normalizeFormula(source.trim())
      validateFormula(formula)
      fill.fields.gravityFormula = formula
    } catch (error) {
      fill.problems.push(`gravity formula left out (${(error as Error).message})`)
    }
  }
  const unit = capturedUnit(firmware)
  if (unit) fill.fields.gravityFormulaUnit = unit
  const points = capturedPoints(firmware, fill.problems)
  if (points.length) fill.fields.gravityCalibrationData = points

  const hasFormula = !!device.gravityFormula?.trim() || !!device.gravityCalibrationData?.length
  if (!hasFormula) return fill
  return { fields: {}, problems: differsFromDevice(device, fill) ? [FORMULA_NOT_APPLIED] : [] }
}

/** The formula as stored: exponent notation rewritten; text the language cannot read is kept as is. */
function storedFormula(text: string): string {
  try { return normalizeFormula(text.trim()) } catch { return text.trim() }
}

const sortedPoints = (points: CalibrationPoint[]) =>
  JSON.stringify([...points].map(p => [p.angle, p.gravity]).sort((a, b) => a[0] - b[0]))

/** Whether the configuration carries a formula or points the device does not already hold. */
function differsFromDevice(device: DeviceFormulaRecord, fill: DeviceFormulaFill): boolean {
  if (fill.problems.length) return true
  const { gravityFormula, gravityCalibrationData } = fill.fields
  if (gravityFormula && gravityFormula !== storedFormula(device.gravityFormula ?? '')) return true
  return !!gravityCalibrationData &&
    sortedPoints(gravityCalibrationData) !== sortedPoints(device.gravityCalibrationData ?? [])
}

/** What a fill put into the formula fields, in words; empty when it filled nothing. */
export function describeFormulaFill(fill: DeviceFormulaFill): string {
  const parts: string[] = []
  if (fill.fields.gravityFormula) parts.push('formula')
  if (fill.fields.gravityFormulaUnit) parts.push(`unit (${fill.fields.gravityFormulaUnit})`)
  const count = fill.fields.gravityCalibrationData?.length
  if (count) parts.push(`${count} calibration point${count === 1 ? '' : 's'}`)
  return parts.length ? `Filled ${parts.join(', ')} from the device configuration` : ''
}
