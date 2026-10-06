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

import { ref } from 'vue'
import { logDebug } from '@/ui'
import { deviceStore } from '@/modules/pinia'
import { assignmentCandidates, deviceEndpoint } from '@brewgraph/core'

export interface DeviceOption {
  value: string | null
  label: string
}

function withDeviceColor(label: string, deviceColor: string): string {
  return `${label} — ${deviceColor}`
}

/**
 * Select-options for assigning gravity/pressure/chamber devices to a batch,
 * built from the device store's current device list.
 */
export function useDeviceOptions() {
  const gravityDeviceOptions = ref<DeviceOption[]>([])
  const pressureDeviceOptions = ref<DeviceOption[]>([])
  const tempControlDeviceOptions = ref<DeviceOption[]>([])

  function updateDeviceOptions() {
    logDebug('useDeviceOptions.updateDeviceOptions()')

    gravityDeviceOptions.value = [{ value: null, label: '-- Disabled --' }]
    pressureDeviceOptions.value = [{ value: null, label: '-- Disabled --' }]
    tempControlDeviceOptions.value = [{ value: null, label: '-- Disabled --' }]

    assignmentCandidates(deviceStore.devices, 'gravity').forEach((device) => {
      gravityDeviceOptions.value.push({
        value: device.id,
        label: withDeviceColor(device.chipId + ' (' + deviceEndpoint(device) + ')', device.deviceColor)
      })
    })
    assignmentCandidates(deviceStore.devices, 'pressure').forEach((device) => {
      pressureDeviceOptions.value.push({
        value: device.id,
        label: withDeviceColor(device.chipId + ' (' + deviceEndpoint(device) + ')', device.deviceColor)
      })
    })
    assignmentCandidates(deviceStore.devices, 'temperature-control').forEach((device) => {
      tempControlDeviceOptions.value.push({
        value: device.id,
        label: withDeviceColor(device.deviceType + '(' + deviceEndpoint(device) + ')', device.deviceColor)
      })
    })

    logDebug('useDeviceOptions.updateDeviceOptions()', 'Gravity', gravityDeviceOptions.value)
    logDebug('useDeviceOptions.updateDeviceOptions()', 'Pressure', pressureDeviceOptions.value)
    logDebug('useDeviceOptions.updateDeviceOptions()', 'Chamber', tempControlDeviceOptions.value)
  }

  return {
    gravityDeviceOptions,
    pressureDeviceOptions,
    tempControlDeviceOptions,
    updateDeviceOptions
  }
}
