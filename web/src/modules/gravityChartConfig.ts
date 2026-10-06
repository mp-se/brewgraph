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

import type { ChartPoint } from '@/modules/gravityChartData'

export interface GravityGraphOptions {
  gravity: boolean
  temperature: boolean
  battery: boolean
  alcohol: boolean
  chamber: boolean
  velocity: boolean
}

export interface GravityGraphData {
  gravity: ChartPoint[]
  temperature: ChartPoint[]
  chamber: ChartPoint[]
  battery: ChartPoint[]
  alcohol: ChartPoint[]
  velocity: ChartPoint[]
  development: ChartPoint[]
}

const LINE_DEFAULTS = {
  pointRadius: 0,
  cubicInterpolationMode: 'monotone' as const,
  tension: 0.4
}

interface GravityChartHandle {
  config: { options: { scales: Record<string, unknown> } }
  data: {
    datasets: Array<{
      label: string
      data: ChartPoint[]
      borderColor: string
      backgroundColor: string
      yAxisID: string
      pointRadius: number
      cubicInterpolationMode: 'monotone'
      tension: number
    }>
  }
}

interface GravityChartStats {
  date: { first: string | number; last: string | number }
}

function setScale(
  chart: GravityChartHandle,
  id: string,
  enabled: boolean,
  position: 'left' | 'right',
  text: string
) {
  if (enabled) {
    chart.config.options.scales[id] = {
      type: 'linear',
      position,
      title: { display: true, text }
    }
  } else if (chart.config.options.scales[id]) {
    delete chart.config.options.scales[id]
  }
}

/**
 * Rebuild the chart's datasets and Y-axes from the selected graph options,
 * and pin the time axis to the dataset's date range.
 */
export function configureGravityChart(
  chart: GravityChartHandle,
  options: GravityGraphOptions,
  data: GravityGraphData,
  stats: GravityChartStats
): void {
  chart.data.datasets = []

  if (options.gravity) {
    chart.data.datasets.push({
      label: 'Gravity',
      data: data.gravity,
      borderColor: 'green',
      backgroundColor: 'green',
      yAxisID: 'yGravity',
      ...LINE_DEFAULTS
    })
  }
  setScale(chart, 'yGravity', options.gravity, 'left', 'Gravity')

  if (options.temperature) {
    chart.data.datasets.push({
      label: 'Temperature',
      data: data.temperature,
      borderColor: 'blue',
      backgroundColor: 'blue',
      yAxisID: 'yTemp',
      ...LINE_DEFAULTS
    })
  }

  if (options.chamber) {
    chart.data.datasets.push({
      label: 'Chamber',
      data: data.chamber,
      borderColor: 'pink',
      backgroundColor: 'pink',
      yAxisID: 'yTemp',
      ...LINE_DEFAULTS
    })
  }
  setScale(chart, 'yTemp', options.temperature || options.chamber, 'right', 'Temperature')

  if (options.battery) {
    chart.data.datasets.push({
      label: 'Battery',
      data: data.battery,
      borderColor: 'orange',
      backgroundColor: 'orange',
      yAxisID: 'yVolt',
      ...LINE_DEFAULTS
    })
  }
  setScale(chart, 'yVolt', options.battery, 'right', 'Voltage')

  if (options.alcohol) {
    chart.data.datasets.push({
      label: 'Alcohol',
      data: data.alcohol,
      borderColor: 'red',
      backgroundColor: 'red',
      yAxisID: 'yAlcohol',
      ...LINE_DEFAULTS
    })
  }
  setScale(chart, 'yAlcohol', options.alcohol, 'left', 'Alcohol')

  if (options.velocity) {
    chart.data.datasets.push({
      label: 'Velocity',
      data: data.velocity,
      borderColor: 'silver',
      backgroundColor: 'silver',
      yAxisID: 'yVelocity',
      ...LINE_DEFAULTS
    })
    chart.data.datasets.push({
      label: 'Development',
      data: data.development,
      borderColor: 'red',
      backgroundColor: 'red',
      yAxisID: 'yVelocity',
      ...LINE_DEFAULTS
    })
  }
  setScale(chart, 'yVelocity', options.velocity, 'right', 'Gravity velocity')

  chart.config.options.scales.x = {
    type: 'time',
    time: {
      unit: 'hour',
      displayFormats: {
        hour: 'E HH:mm',
        day: 'HH:mm',
        week: 'E HH:mm',
        month: 'd HH:mm'
      }
    },
    min: stats.date.first,
    max: stats.date.last
  }
}
