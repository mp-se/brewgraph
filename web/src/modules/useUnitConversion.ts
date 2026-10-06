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

import { computed, type Ref } from 'vue'
import { config } from '@/modules/pinia'
import { decimalPrecision, decimalStep } from '@brewgraph/core'
import {
  gravityToPlato,
  platoToGravity,
  tempToF,
  tempToC,
  pressureToKPA,
  pressureToBAR,
  pressureFromBAR,
  pressureFromKPA,
  volumeLtoUSGallon,
  volumeLtoUKGallon,
  volumeLtoCL,
  volumeLtoUSFlOz,
  volumeLtoUKPint,
  volumeCLtoL,
  volumeUKGallonToL,
  volumeUKPintToL,
  volumeUSFlOzToL,
  volumeUSGallonToL,
  roundValue
} from '@/modules/utils'

// Fallback decimal counts used only until `config.precision` has loaded from
// GET /tenant/settings (api/oss/precision.py DECIMALS) -- once loaded, these
// quantities are governed by that response, never re-duplicated here.
const FALLBACK_DECIMALS: Record<string, number> = {
  gravity: 4,
  temperature: 2,
  pressure: 2,
  volume: 3
}

export function decimalsFor(quantity: string): number {
  return decimalPrecision(quantity, config.precision, FALLBACK_DECIMALS) ?? 0
}

export function stepFor(quantity: string): number {
  // Not `Math.pow(10, -decimals)`: Math.pow is spec-"implementation-approximated"
  // (ECMA-262 does not require correct rounding), so a dynamic, non-constant-folded
  // exponent can resolve one ULP off (e.g. 0.00009999999999999999 instead of 0.0001)
  // depending on JIT state, which made this flaky. Numeric-literal parsing is
  // spec-guaranteed correctly rounded, so route through it instead.
  return decimalStep(decimalsFor(quantity))
}

export function useGravityConversion(batch: Ref<Record<string, number | null> | null>, field: string) {
  const displayValue = computed({
    get() {
      if (!batch.value || batch.value[field] == null) return null
      const sgValue = batch.value[field] as number
      const val = config.isGravitySG ? sgValue : gravityToPlato(sgValue)
      return roundValue(val, decimalsFor('gravity'))
    },
    set(displayedValue: number | null) {
      if (batch.value) {
        batch.value[field] = displayedValue == null
          ? null
          : config.isGravitySG ? displayedValue : platoToGravity(displayedValue)
      }
    }
  })

  const unit = computed(() => (config.isGravitySG ? 'SG' : 'P'))
  const step = computed(() => stepFor('gravity'))

  return { displayValue, unit, step }
}

export function useTemperatureConversion(
  batch: Ref<Record<string, number | null> | null>,
  field: string
) {
  const displayValue = computed({
    get() {
      if (!batch.value || batch.value[field] === null || batch.value[field] === undefined) return 0
      const celsiusValue = batch.value[field] as number
      const val = config.isTempC ? celsiusValue : tempToF(celsiusValue)
      return roundValue(val, decimalsFor('temperature'))
    },
    set(displayedValue: number) {
      if (batch.value) {
        batch.value[field] = config.isTempC ? displayedValue : tempToC(displayedValue)
      }
    }
  })

  const unit = computed(() => (config.isTempC ? '°C' : '°F'))
  const step = computed(() => stepFor('temperature'))

  return { displayValue, unit, step }
}

export function usePressureConversion(batch: Ref<Record<string, number> | null>, field: string) {
  const displayValue = computed({
    get() {
      if (!batch.value || !batch.value[field]) return 0
      const psiValue = batch.value[field]
      let val: number
      let decimals: number

      if (config.isPressurePSI) {
        val = psiValue
        decimals = decimalsFor('pressure')
      } else if (config.isPressureBAR) {
        val = pressureToBAR(psiValue)
        decimals = decimalsFor('pressure')
      } else {
        val = pressureToKPA(psiValue)
        decimals = decimalsFor('pressure')
      }
      return roundValue(val, decimals)
    },
    set(displayedValue: number) {
      if (batch.value) {
        if (config.isPressurePSI) {
          batch.value[field] = displayedValue
        } else if (config.isPressureBAR) {
          batch.value[field] = pressureFromBAR(displayedValue)
        } else {
          batch.value[field] = pressureFromKPA(displayedValue)
        }
      }
    }
  })

  const unit = computed(() => {
    if (config.isPressurePSI) return 'PSI'
    if (config.isPressureBAR) return 'Bar'
    return 'kPa'
  })

  return { displayValue, unit }
}

export function useVolumeConversion(
  entity: Ref<Record<string, number | null> | null>,
  field: string
) {
  const displayValue = computed<number | null>({
    get() {
      const liters = entity.value ? entity.value[field] : null
      if (liters === null || liters === undefined) return null
      if (config.isVolumeUs) return roundValue(volumeLtoUSGallon(liters), 2)
      if (config.isVolumeUk) return roundValue(volumeLtoUKGallon(liters), 2)
      return roundValue(liters, 3)
    },
    set(displayedValue: number | null) {
      if (!entity.value) return
      if (displayedValue === null || displayedValue === undefined) {
        entity.value[field] = null
        return
      }
      if (config.isVolumeUs) entity.value[field] = roundValue(volumeUSGallonToL(displayedValue), 3)
      else if (config.isVolumeUk)
        entity.value[field] = roundValue(volumeUKGallonToL(displayedValue), 3)
      else entity.value[field] = roundValue(displayedValue, 3)
    }
  })

  const unit = computed(() => (config.isVolumeMetric ? 'L' : 'gal'))
  const step = computed(() => (config.isVolumeMetric ? stepFor('volume') : 0.01))

  return { displayValue, unit, step }
}

export function usePourVolumeConversion(pourLiters: Ref<number>) {
  const displayValue = computed({
    get() {
      if (config.isVolumeUs) return roundValue(volumeLtoUSFlOz(pourLiters.value), 1)
      if (config.isVolumeUk) return roundValue(volumeLtoUKPint(pourLiters.value), 2)
      return roundValue(volumeLtoCL(pourLiters.value), 1)
    },
    set(v: number) {
      if (config.isVolumeUs) pourLiters.value = roundValue(volumeUSFlOzToL(v), 4)
      else if (config.isVolumeUk) pourLiters.value = roundValue(volumeUKPintToL(v), 4)
      else pourLiters.value = roundValue(volumeCLtoL(v), 4)
    }
  })

  const unit = computed(() => {
    if (config.isVolumeUs) return 'fl oz'
    if (config.isVolumeUk) return 'pint'
    return 'cl'
  })

  const step = computed(() => (config.isVolumeMetric ? 1 : 0.5))

  const max = computed(() => {
    if (config.isVolumeUs) return roundValue(volumeLtoUSFlOz(50), 0)
    if (config.isVolumeUk) return roundValue(volumeLtoUKPint(50), 0)
    return roundValue(volumeLtoCL(50), 0)
  })

  return { displayValue, unit, step, max }
}

export function volumeMaxL(baseMaxL: number): number {
  if (config.isVolumeUs) return roundValue(volumeLtoUSGallon(baseMaxL), 0)
  if (config.isVolumeUk) return roundValue(volumeLtoUKGallon(baseMaxL), 0)
  return baseMaxL
}

// Fixed L <-> ml conversion, unlike useVolumeConversion this does not follow
// config.isVolumeUs/Uk — brewers think in millilitres for a single glass
// regardless of the unit preference used for batch/vessel volumes, and the
// stored value must stay null (not 0) when the field is left unset, since a
// glass size of zero is not a thing.
export function useGlassSizeConversion(
  entity: Ref<Record<string, number | null> | null>,
  field: string
) {
  const displayValue = computed<number | null>({
    get() {
      const liters = entity.value ? entity.value[field] : null
      if (liters === null || liters === undefined) return null
      return Math.round(liters * 1000)
    },
    set(ml: number | null) {
      if (!entity.value) return
      entity.value[field] = ml === null || ml === undefined ? null : ml / 1000
    }
  })
  return { displayValue }
}

export { roundValue } from '@/modules/utils'
