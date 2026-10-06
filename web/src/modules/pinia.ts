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
import { createPinia } from 'pinia'
import { useGlobalStore } from '@/modules/globalStore'
import { usePreferencesStore } from '@/modules/preferencesStore'
import { useConfigStore } from '@/modules/configStore'
import { useDeviceStore } from '@/modules/deviceStore'
import { useBatchStore } from '@/modules/batchStore'
import { useGravityStore } from '@/modules/gravityStore'
import { usePressureStore } from '@/modules/pressureStore'
import { useTempReadingStore } from '@/modules/tempReadingStore'
import { usePourStore } from '@/modules/pourStore'
import { useBrewfatherStore } from '@/modules/brewfatherStore'
import { useTapStore } from '@/modules/tapStore'
import { useVesselStore } from '@/modules/vesselStore'
import { useDashboardStore } from '@/modules/dashboardStore'
import { useBatchNoteStore } from '@/modules/batchNoteStore'
import { useYeastStrainStore } from '@/modules/yeastStrainStore'
import { useIntegrationStore } from '@/modules/integrationStore'
import { logDebug, logError } from '@/ui'

const piniaInstance = createPinia()

export default piniaInstance

const config = useConfigStore(piniaInstance)
const global = useGlobalStore(piniaInstance)
const preferences = usePreferencesStore(piniaInstance)
const deviceStore = useDeviceStore(piniaInstance)
const batchStore = useBatchStore(piniaInstance)
const gravityStore = useGravityStore(piniaInstance)
const pressureStore = usePressureStore(piniaInstance)
const tempReadingStore = useTempReadingStore(piniaInstance)
const pourStore = usePourStore(piniaInstance)
const brewfatherStore = useBrewfatherStore(piniaInstance)
const tapStore = useTapStore(piniaInstance)
const vesselStore = useVesselStore(piniaInstance)
const dashboardStore = useDashboardStore(piniaInstance)
const batchNoteStore = useBatchNoteStore(piniaInstance)
const yeastStrainStore = useYeastStrainStore(piniaInstance)
const integrationStore = useIntegrationStore(piniaInstance)

export {
  global,
  preferences,
  config,
  deviceStore,
  batchStore,
  gravityStore,
  pressureStore,
  tempReadingStore,
  pourStore,
  brewfatherStore,
  tapStore,
  vesselStore,
  dashboardStore,
  batchNoteStore,
  yeastStrainStore,
  integrationStore
}

const configCompare = ref<Record<string, unknown> | null>(null)

export const createConfigSnapshot = (
  configObj: Record<string, unknown>
): Record<string, unknown> => {
  const snapshot: Record<string, unknown> = {}
  for (const key in configObj) {
    if (typeof configObj[key] !== 'function' && key !== '$id') {
      snapshot[key] = configObj[key]
    }
  }
  return snapshot
}

export const detectConfigChanges = (
  savedSnapshot: Record<string, unknown>,
  currentSnapshot: Record<string, unknown>
): Record<string, unknown> => {
  const changes: Record<string, unknown> = {}

  if (!savedSnapshot) {
    logError('pinia.detectConfigChanges()', 'Saved snapshot is null or undefined')
    return changes
  }

  for (const key in savedSnapshot) {
    if (savedSnapshot[key] != currentSnapshot[key]) {
      changes[key] = currentSnapshot[key]
    }
  }

  return changes
}

export const hasSignificantChanges = (changes: Record<string, unknown>): boolean => {
  return JSON.stringify(changes).length > 2
}

const saveConfigState = (): void => {
  logDebug('pinia.saveConfigState()')
  configCompare.value = createConfigSnapshot(config as unknown as Record<string, unknown>)
  logDebug('pinia.saveConfigState()', 'Saved state: ', configCompare.value)
  global.configChanged = false
}

const getConfigChanges = (): Record<string, unknown> => {
  logDebug('pinia.getConfigChanges()')

  if (configCompare.value === null) {
    logError('pinia.getConfigChanges()', 'configState not saved')
    return {}
  }

  const currentSnapshot = createConfigSnapshot(config as unknown as Record<string, unknown>)
  return detectConfigChanges(configCompare.value, currentSnapshot)
}

config.$subscribe(() => {
  logDebug('pinia.subscribe()')

  if (!global.initialized) return

  const changes = getConfigChanges()
  logDebug('pinia.subscribe()', 'State change on configStore', changes)

  if (hasSignificantChanges(changes)) {
    global.configChanged = true
    logDebug('pinia.subscribe()', 'Changed properties:', changes)
  } else {
    global.configChanged = false
  }
})

export { saveConfigState, getConfigChanges }
