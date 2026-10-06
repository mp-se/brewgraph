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
import {
  logDebug,
  isValidJson,
  isValidFormData,
  isValidMqttData,
  validateCurrentForm,
  formatTime
} from '@/ui'
import {
  abv,
  gravityToPlato,
  platoToGravity,
  pressureFromBAR,
  pressureFromKPA,
  pressureToBAR,
  pressureToKPA,
  roundValue,
  tempToC,
  tempToF,
  volumeCLtoUKOZ,
  volumeCLtoUSOZ,
  volumeLtoCL,
  volumeLtoUKGallon,
  volumeLtoUKPint,
  volumeLtoUSFlOz,
  volumeLtoUSGallon,
  volumeCLtoL,
  volumeUKGallonToL,
  volumeUKPintToL,
  volumeUSFlOzToL,
  volumeUSGallonToL,
  formatDurationShort,
  readingStats,
  relativeTime,
  truncateString as truncateCoreString
} from '@brewgraph/core'

export {
  abv,
  gravityToPlato,
  platoToGravity,
  pressureFromBAR,
  pressureFromKPA,
  pressureToBAR,
  pressureToKPA,
  tempToF,
  tempToC,
  volumeCLtoUSOZ,
  volumeCLtoUKOZ,
  volumeLtoCL,
  volumeLtoUKGallon,
  volumeLtoUKPint,
  volumeLtoUSFlOz,
  volumeLtoUSGallon,
  volumeCLtoL,
  volumeUKGallonToL,
  volumeUKPintToL,
  volumeUSFlOzToL,
  volumeUSGallonToL,
  roundValue,
  isValidJson,
  isValidFormData,
  isValidMqttData,
  validateCurrentForm,
  formatTime
}

export function getFormattedTemperature(temp: number | null | undefined): string {
  if (temp === null || temp === undefined || temp < -270) {
    return '--'
  }
  if (config.isTempF) {
    return Number(tempToF(temp)).toFixed(1) + ' °F'
  }
  return Number(temp).toFixed(1) + ' °C'
}

export function getFormattedPressure(pressure: number): string {
  if (config.isPressurePSI) {
    return Number(pressure).toFixed(1) + ' PSI'
  }
  if (config.isPressureKPA) {
    return Number(pressureToKPA(pressure)).toFixed(0) + ' kPa'
  }
  return Number(pressureToBAR(pressure)).toFixed(2) + ' Bar'
}

export function getFormattedVolume(volumeLiters: number): string {
  if (config.isVolumeUs) {
    return Number(volumeLtoUSGallon(volumeLiters)).toFixed(2) + ' gal'
  }
  if (config.isVolumeUk) {
    return Number(volumeLtoUKGallon(volumeLiters)).toFixed(2) + ' gal'
  }
  return Number(volumeLiters).toFixed(2) + ' L'
}

export function getFormattedPourVolume(volumeCentiliters: number): string {
  if (config.isVolumeUs) {
    return Number(volumeCLtoUSOZ(volumeCentiliters)).toFixed(1) + ' oz'
  }
  if (config.isVolumeUk) {
    return Number(volumeCLtoUKOZ(volumeCentiliters)).toFixed(1) + ' oz'
  }
  return Number(volumeCentiliters).toFixed(0) + ' cl'
}

export function truncateString(str: string, maxLength: number): string {
  return truncateCoreString(str, maxLength)
}

export function getTimeSincePosted(created: string): string {
  return relativeTime(created)
}

export function download(content: string | ArrayBuffer, mimeType: string, filename: string): void {
  const a = document.createElement('a')
  let objectUrl: string | null = null

  if (mimeType.startsWith('text/')) {
    const dataUrl = `data:${mimeType};charset=utf-8,${encodeURIComponent(content as string)}`
    a.setAttribute('href', dataUrl)
  } else {
    const blob = new Blob([content], { type: mimeType })
    objectUrl = URL.createObjectURL(blob)
    a.setAttribute('href', objectUrl)
  }

  a.setAttribute('download', filename)
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  a.remove()
  if (objectUrl) setTimeout(() => URL.revokeObjectURL(objectUrl), 0)
}

// navigator.clipboard only exists in secure contexts (HTTPS or localhost); self-hosted
// installs are typically served over plain HTTP on the LAN, so fall back to execCommand.
// Inside a dialog, pass the dialog as `container`: its focus trap would otherwise pull
// focus off a textarea appended to <body> and the copy would silently fail.
export async function copyToClipboard(
  text: string,
  container: HTMLElement = document.body
): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // fall through to the legacy path
    }
  }

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  container.appendChild(textarea)
  textarea.select()
  try {
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    container.removeChild(textarea)
  }
}

interface PressureStats {
  pressure: { min: number; max: number; minString: string; maxString: string }
  temperature: { min: number; max: number; minString: string; maxString: string }
  date: {
    first: string
    last: string
    firstDate: string
    lastDate: string
    firstTime: string
    lastTime: string
  }
  readings: number
  averageInterval: number | string
  averageIntervalString: string
}

interface PressureReading {
  excluded: boolean
  pressure: number
  temperature: number | null
  createdAt: string
}

export function getPressureDataAnalytics(pressureList: PressureReading[]): PressureStats {
  logDebug('utils.getPressureDataAnalytics()')
  const raw = readingStats(pressureList, {
    getValue: (reading) => reading.pressure,
    getCreated: (reading) => reading.createdAt,
    isValidTemperature: (temperature) => temperature >= -270
  })
  const stats: PressureStats = { ...raw, pressure: { ...raw.value, minString: '', maxString: '' }, temperature: { ...raw.temperature, minString: '', maxString: '' } }

  stats.pressure.min = config.isPressurePSI
    ? stats.pressure.min
    : config.isPressureBAR
      ? pressureToBAR(stats.pressure.min)
      : pressureToKPA(stats.pressure.min)
  stats.pressure.max = config.isPressurePSI
    ? stats.pressure.max
    : config.isPressureBAR
      ? pressureToBAR(stats.pressure.max)
      : pressureToKPA(stats.pressure.max)
  stats.temperature.min = config.isTempC ? stats.temperature.min : tempToF(stats.temperature.min)
  stats.temperature.max = config.isTempC ? stats.temperature.max : tempToF(stats.temperature.max)

  stats.pressure.minString =
    new Number(stats.pressure.min).toFixed(3) +
    (config.isPressurePSI ? ' Psi' : config.isPressureBAR ? ' Bar' : ' kPa')
  stats.pressure.maxString =
    new Number(stats.pressure.max).toFixed(3) +
    (config.isPressurePSI ? ' Psi' : config.isPressureBAR ? ' Bar' : ' kPa')
  stats.temperature.minString =
    new Number(stats.temperature.min).toFixed(2) + (config.isTempC ? ' C' : ' F')
  stats.temperature.maxString =
    new Number(stats.temperature.max).toFixed(2) + (config.isTempC ? ' C' : ' F')

  logDebug('utils.getPressureDataAnalytics()', stats)
  return stats
}

interface GravityStats {
  gravity: { min: number; max: number; minString: string; maxString: string }
  temperature: { min: number; max: number; minString: string; maxString: string }
  abv: number
  abvString: string
  date: {
    first: string
    last: string
    firstDate: string
    lastDate: string
    firstTime: string
    lastTime: string
  }
  readings: number
  averageInterval: number | string
  averageIntervalString: string
}

interface GravityReading {
  excluded: boolean
  gravity: number
  temperature: number | null
  created: string
}

export function getGravityDataAnalytics(gravityList: GravityReading[]): GravityStats {
  logDebug('utils.getGravityDataAnalytics()')
  const raw = readingStats(gravityList, {
    getValue: (reading) => reading.gravity,
    getCreated: (reading) => reading.created
  })
  const stats: GravityStats = { ...raw, gravity: { ...raw.value, minString: '', maxString: '' }, temperature: { ...raw.temperature, minString: '', maxString: '' }, abv: 0, abvString: '' }

  stats.abv = abv(stats.gravity.max, stats.gravity.min)
  stats.gravity.min = config.isGravitySG ? stats.gravity.min : gravityToPlato(stats.gravity.min)
  stats.gravity.max = config.isGravitySG ? stats.gravity.max : gravityToPlato(stats.gravity.max)
  stats.temperature.min = config.isTempC ? stats.temperature.min : tempToF(stats.temperature.min)
  stats.temperature.max = config.isTempC ? stats.temperature.max : tempToF(stats.temperature.max)

  stats.abvString = new Number(stats.abv).toFixed(2) + ' %'
  stats.gravity.minString =
    new Number(stats.gravity.min).toFixed(3) + (config.isGravitySG ? ' SG' : ' P')
  stats.gravity.maxString =
    new Number(stats.gravity.max).toFixed(3) + (config.isGravitySG ? ' SG' : ' P')
  stats.temperature.minString =
    new Number(stats.temperature.min).toFixed(2) + (config.isTempC ? ' C' : ' F')
  stats.temperature.maxString =
    new Number(stats.temperature.max).toFixed(2) + (config.isTempC ? ' C' : ' F')

  logDebug('utils.getGravityDataAnalytics()', stats)
  return stats
}

export function formatTimeShort(t: number): string {
  const seconds = Math.floor(t % 60)
  const minutes = Math.floor((t % (60 * 60)) / 60)
  const hours = Math.floor((t % (24 * 60 * 60)) / (60 * 60))
  const days = Math.floor((t % (7 * 24 * 60 * 60)) / (24 * 60 * 60))
  const weeks = Math.floor((t % (365 * 24 * 60 * 60)) / (7 * 24 * 60 * 60))

  logDebug('utils.formatTimeShort()', t, weeks, days, hours, minutes, seconds)

  return formatDurationShort(t)
}
