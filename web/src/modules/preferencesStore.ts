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

import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

function readBoolean(key: string): boolean {
  try {
    return typeof localStorage !== 'undefined' && localStorage.getItem(key) === 'true'
  } catch {
    return false
  }
}

function readString(key: string, fallback: string): string {
  try {
    if (typeof localStorage === 'undefined') return fallback
    const value = localStorage.getItem(key)
    return value === null ? fallback : value
  } catch {
    return fallback
  }
}

function persist(key: string, value: string | boolean): void {
  try {
    if (typeof localStorage !== 'undefined') localStorage.setItem(key, String(value))
  } catch {
    // Preferences remain usable for this session when browser storage is unavailable.
  }
}

export const usePreferencesStore = defineStore('preferences', () => {
  const batchListFilterDevice = ref(readString('batchListFilterDevice', '*'))
  const batchListFilterActive = ref(readBoolean('batchListFilterActive'))
  const batchListFilterData = ref(readBoolean('batchListFilterData'))
  const deviceListFilterDeviceType = ref(readString('deviceListFilterDeviceType', '*'))
  const showChamberTemps = ref(readBoolean('showChamberTemps'))
  const showKegmonTaps = ref(readBoolean('showKegmonTaps'))
  const dark_mode = ref(readBoolean('dark_mode'))

  watch(batchListFilterDevice, value => persist('batchListFilterDevice', value))
  watch(batchListFilterActive, value => persist('batchListFilterActive', value))
  watch(batchListFilterData, value => persist('batchListFilterData', value))
  watch(deviceListFilterDeviceType, value => persist('deviceListFilterDeviceType', value))
  watch(showChamberTemps, value => persist('showChamberTemps', value))
  watch(showKegmonTaps, value => persist('showKegmonTaps', value))
  watch(dark_mode, value => persist('dark_mode', value))

  return {
    batchListFilterDevice,
    batchListFilterActive,
    batchListFilterData,
    deviceListFilterDeviceType,
    showChamberTemps,
    showKegmonTaps,
    dark_mode
  }
})
