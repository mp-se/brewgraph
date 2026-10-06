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

import { config } from '@/modules/pinia'
import { abv, gravityToPlato, tempToF } from '@/modules/utils'
import {
  alcoholPoints,
  applyMovingAverage,
  gravityPoints,
  gravityVelocityPoints,
  MovingAverageFilter as LowPassFilter,
  temperaturePoints
} from '@brewgraph/core'
import type { GravitySeriesReading } from '@brewgraph/core'

export interface ChartPoint {
  x: string | Date
  y: number | string
}

/** Simple moving-average filter over a sliding window. */
export { LowPassFilter }

/** Gravity points in the configured unit (SG or Plato). */
export function mapGravityData(gList: GravitySeriesReading[]): ChartPoint[] {
  return gravityPoints(gList, config.isGravitySG, gravityToPlato)
}

/** Battery voltage points. */
export function mapBatteryData(gList: GravitySeriesReading[]): ChartPoint[] {
  const result: ChartPoint[] = []

  gList.forEach((g: GravitySeriesReading) => {
    result.push({
      x: g.created,
      y: parseFloat(new Number(g.battery).toFixed(2))
    })
  })

  return result
}

/** Temperature points in the configured unit, skipping null readings. */
export function mapTemperatureData(gList: GravitySeriesReading[]): ChartPoint[] {
  return temperaturePoints(gList, config.isTempC, tempToF)
}

/** Estimated ABV points derived from the highest gravity in the list. */
export function mapAlcoholData(gList: GravitySeriesReading[]): ChartPoint[] {
  return alcoholPoints(gList, abv)
}

/** Chamber temperature points in the configured unit, skipping null readings. */
export function mapChamberData(gList: GravitySeriesReading[]): ChartPoint[] {
  const result: ChartPoint[] = []

  gList
    .filter((g: GravitySeriesReading) => g.chamberTemperature != null)
    .forEach((g: GravitySeriesReading) => {
      const chamberTemperature = g.chamberTemperature
      if (chamberTemperature == null) return
      result.push({
        x: g.created,
        y: new Number(
          config.isTempC ? chamberTemperature : tempToF(chamberTemperature)
        ).toFixed(2)
      })
    })

  return result
}

/**
 * Gravity velocity (points/24h) from hourly-averaged slots, plus the raw
 * device-reported velocity series ("development").
 */
export function mapGravityVelocityData(gList: GravitySeriesReading[]): {
  velocity: ChartPoint[]
  development: ChartPoint[]
} {
  return gravityVelocityPoints(gList)
}

/** Run a point series through a moving-average filter of the given window. */
export function applyLowPass(input: ChartPoint[], windowSize: number): ChartPoint[] {
  return applyMovingAverage(input.map((point) => ({ x: point.x, y: Number(point.y) })), windowSize)
}
