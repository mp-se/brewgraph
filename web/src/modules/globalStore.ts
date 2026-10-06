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
import { logDebug, logInfo } from '@/ui'
import { version as packageVersion } from '../../package.json'

export const useGlobalStore = defineStore('global', {
  state: () => {
    return {
      initialized: false,
      busyOperations: 0,
      // Restore emits an event per deleted/restored entity. The event stream
      // deliberately ignores those echo events and the final list refreshes
      // retain the busy lock without repeatedly releasing it.
      restoreInProgress: false,

      configChanged: false,
      batchChanged: false,
      deviceChanged: false,
      tapChanged: false,
      vesselChanged: false,

      messageError: '',
      messageWarning: '',
      messageSuccess: '',
      messageInfo: '',

      fetchTimout: 30000,
      url: undefined as string | undefined,

      updatedDeviceData: 0,
      updatedBatchData: 0,
      updatedGravityData: 0,
      updatedPressureData: 0,
      updatedPourData: 0,
      updatedTapData: 0,
      updatedVesselData: 0
    }
  },
  getters: {
    disabled(): boolean {
      return this.busyOperations > 0
    },
    hasUnsavedChanges(): boolean {
      return (
        this.batchChanged ||
        this.deviceChanged ||
        this.tapChanged ||
        this.vesselChanged ||
        this.configChanged
      )
    },
    isError(): boolean {
      return this.messageError != ''
    },
    isWarning(): boolean {
      return this.messageWarning != ''
    },
    isSuccess(): boolean {
      return this.messageSuccess != ''
    },
    isInfo(): boolean {
      return this.messageInfo != ''
    },
    baseURL(): string {
      if (this.url !== undefined) return this.url

      if (import.meta.env.VITE_APP_HOST === undefined) {
        logInfo('configStore:baseURL()', 'Using base URL from env', window.location.origin + '/')
        this.url = window.location.origin + '/'
      } else {
        logInfo('configStore:baseURL()', 'Using base URL from env', import.meta.env.VITE_APP_HOST)
        this.url = import.meta.env.VITE_APP_HOST
      }

      return this.url as string
    },
    token(): string {
      logDebug(
        'globalStore.token()',
        'env:',
        import.meta.env.VITE_APP_TOKEN,
        'js:',
        (window as unknown as Record<string, unknown>).VITE_APP_TOKEN
      )

      const windowToken = (window as unknown as Record<string, unknown>).VITE_APP_TOKEN
      if (windowToken === undefined || windowToken === '__TOKEN__')
        return 'Bearer ' + import.meta.env.VITE_APP_TOKEN

      return 'Bearer ' + windowToken
    },
    uiVersion(): string {
      return import.meta.env.VITE_APP_VERSION ?? packageVersion.replace(/-migration$/, '')
    },
    uiBuild(): string {
      return import.meta.env.VITE_APP_BUILD
    },
    apiURL(): string {
      return this.baseURL + 'api/'
    }
  },
  actions: {
    acquireBusy(): () => void {
      this.busyOperations += 1
      let released = false

      return () => {
        if (released) return
        released = true
        this.busyOperations = Math.max(0, this.busyOperations - 1)
      }
    },
    clearMessages(): void {
      this.messageError = ''
      this.messageWarning = ''
      this.messageSuccess = ''
      this.messageInfo = ''
    }
  }
})
