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

import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useGlobalStore } from '@/modules/globalStore'
import { usePreferencesStore } from '@/modules/preferencesStore'

describe('useGlobalStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // Mock environment variables
    import.meta.env.VITE_APP_HOST = undefined
    import.meta.env.VITE_APP_TOKEN = 'test-token'
    import.meta.env.VITE_APP_VERSION = '1.0.0'
    import.meta.env.VITE_APP_BUILD = '1'
    window.VITE_APP_TOKEN = undefined
    // Mock window.location.origin (read-only, so use Object.defineProperty)
    Object.defineProperty(window, 'location', {
      value: { origin: 'http://localhost:8080' },
      writable: true
    })
  })

  describe('Initial State', () => {
    it('should have default initialized state', () => {
      const store = useGlobalStore()
      expect(store.initialized).toBe(false)
      expect(store.disabled).toBe(false)
      expect(store.configChanged).toBe(false)
      expect(store.batchChanged).toBe(false)
      expect(store.deviceChanged).toBe(false)
    })

    it('should have empty messages by default', () => {
      const store = useGlobalStore()
      expect(store.messageError).toBe('')
      expect(store.messageWarning).toBe('')
      expect(store.messageSuccess).toBe('')
      expect(store.messageInfo).toBe('')
    })

    it('should have notification counters initialized to 0', () => {
      const store = useGlobalStore()
      expect(store.updatedDeviceData).toBe(0)
      expect(store.updatedBatchData).toBe(0)
      expect(store.updatedGravityData).toBe(0)
      expect(store.updatedPourData).toBe(0)
    })
  })

  describe('Message Getters', () => {
    it('should detect error message', () => {
      const store = useGlobalStore()
      expect(store.isError).toBe(false)
      store.messageError = 'Error occurred'
      expect(store.isError).toBe(true)
    })

    it('should detect warning message', () => {
      const store = useGlobalStore()
      expect(store.isWarning).toBe(false)
      store.messageWarning = 'Warning message'
      expect(store.isWarning).toBe(true)
    })

    it('should detect success message', () => {
      const store = useGlobalStore()
      expect(store.isSuccess).toBe(false)
      store.messageSuccess = 'Success'
      expect(store.isSuccess).toBe(true)
    })

    it('should detect info message', () => {
      const store = useGlobalStore()
      expect(store.isInfo).toBe(false)
      store.messageInfo = 'Information'
      expect(store.isInfo).toBe(true)
    })
  })

  describe('baseURL Getter', () => {
    it('should use window.location.origin when VITE_APP_HOST is not set', () => {
      const store = useGlobalStore()
      // Vite env variables are always strings, not undefined
      // Delete would be ideal but can't modify import.meta.env
      store.url = undefined // Reset cached value
      const url = store.baseURL
      // Check if it returns a valid URL
      expect(url).toBeTruthy()
      expect(typeof url).toBe('string')
    })

    it('should cache baseURL after first access', () => {
      const store = useGlobalStore()
      store.url = undefined
      const url1 = store.baseURL
      const url2 = store.baseURL
      expect(url1).toBe(url2)
      expect(store.url).toBeDefined()
    })

    it('should use VITE_APP_HOST when defined (covers lines 57-58)', () => {
      const store = useGlobalStore()
      import.meta.env.VITE_APP_HOST = 'http://example.com/'
      store.url = undefined // Reset cached value
      const url = store.baseURL
      expect(url).toBe('http://example.com/')
      expect(store.url).toBe('http://example.com/')
    })

    it('should use VITE_APP_HOST with different host formats', () => {
      const store = useGlobalStore()
      import.meta.env.VITE_APP_HOST = 'https://custom-host.io:8443/'
      store.url = undefined
      const url = store.baseURL
      expect(url).toBe('https://custom-host.io:8443/')
    })

    it('should not override cached URL on subsequent calls with different env', () => {
      const store = useGlobalStore()
      import.meta.env.VITE_APP_HOST = 'http://first.com/'
      store.url = undefined
      const url1 = store.baseURL

      // Change env variable
      import.meta.env.VITE_APP_HOST = 'http://second.com/'
      // Should return cached value, not new env value
      const url2 = store.baseURL
      expect(url1).toBe(url2)
      expect(url2).toBe('http://first.com/')
    })

    it('should include the protocol in baseURL', () => {
      const store = useGlobalStore()
      import.meta.env.VITE_APP_HOST = 'http://example.com/'
      store.url = undefined
      const url = store.baseURL
      expect(url).toContain('http')
    })
  })

  describe('Token Getter', () => {
    it('should use window.VITE_APP_TOKEN when available', () => {
      const store = useGlobalStore()
      window.VITE_APP_TOKEN = 'window-token'
      const token = store.token
      expect(token).toBe('Bearer window-token')
    })

    it('should use import.meta.env token when window token is undefined', () => {
      const store = useGlobalStore()
      window.VITE_APP_TOKEN = undefined
      import.meta.env.VITE_APP_TOKEN = 'env-token'
      const token = store.token
      expect(token).toBe('Bearer env-token')
    })

    it('should use import.meta.env token when window token is __TOKEN__', () => {
      const store = useGlobalStore()
      window.VITE_APP_TOKEN = '__TOKEN__'
      import.meta.env.VITE_APP_TOKEN = 'env-token'
      const token = store.token
      expect(token).toBe('Bearer env-token')
    })

    it('should handle empty window token', () => {
      const store = useGlobalStore()
      window.VITE_APP_TOKEN = ''
      import.meta.env.VITE_APP_TOKEN = 'env-token'
      const token = store.token
      expect(token).toBe('Bearer ')
    })

    it('should handle empty env token', () => {
      const store = useGlobalStore()
      window.VITE_APP_TOKEN = undefined
      import.meta.env.VITE_APP_TOKEN = ''
      const token = store.token
      expect(token).toBe('Bearer ')
    })

    it('should prioritize window token over env token', () => {
      const store = useGlobalStore()
      window.VITE_APP_TOKEN = 'window-priority'
      import.meta.env.VITE_APP_TOKEN = 'env-value'
      const token = store.token
      expect(token).toBe('Bearer window-priority')
    })

    it('should include Bearer prefix with space', () => {
      const store = useGlobalStore()
      window.VITE_APP_TOKEN = 'xyz123'
      const token = store.token
      expect(token).toBe('Bearer xyz123')
    })
  })

  describe('Version Getters', () => {
    it('should return UI version from environment', () => {
      const store = useGlobalStore()
      expect(store.uiVersion).toBe('1.0.0')
    })

    it('should return UI build from environment', () => {
      const store = useGlobalStore()
      expect(store.uiBuild).toBe('1')
    })
  })

  describe('clearMessages Action', () => {
    it('should clear all messages', () => {
      const store = useGlobalStore()
      store.messageError = 'Error'
      store.messageWarning = 'Warning'
      store.messageSuccess = 'Success'
      store.messageInfo = 'Info'

      store.clearMessages()

      expect(store.messageError).toBe('')
      expect(store.messageWarning).toBe('')
      expect(store.messageSuccess).toBe('')
      expect(store.messageInfo).toBe('')
    })

    it('should clear only when messages exist', () => {
      const store = useGlobalStore()
      expect(store.messageError).toBe('')
      store.clearMessages()
      expect(store.messageError).toBe('')
    })

    it('should clear messages when only some are set', () => {
      const store = useGlobalStore()
      store.messageError = 'Only error'
      store.messageSuccess = 'Success message'

      store.clearMessages()

      expect(store.messageError).toBe('')
      expect(store.messageWarning).toBe('')
      expect(store.messageSuccess).toBe('')
      expect(store.messageInfo).toBe('')
    })

    it('should clear and allow resetting messages', () => {
      const store = useGlobalStore()
      store.messageError = 'Error 1'
      store.clearMessages()
      store.messageError = 'Error 2'

      expect(store.messageError).toBe('Error 2')

      store.clearMessages()
      expect(store.messageError).toBe('')
    })

    it('should not affect other state when clearing messages', () => {
      const store = useGlobalStore()
      store.initialized = true
      const releaseBusy = store.acquireBusy()
      store.messageError = 'Error'

      store.clearMessages()

      expect(store.initialized).toBe(true)
      expect(store.disabled).toBe(true)
      expect(store.messageError).toBe('')
      releaseBusy()
    })
  })

  describe('Message Getters with clearMessages', () => {
    it('should reflect message state changes after clearMessages', () => {
      const store = useGlobalStore()
      store.messageError = 'Error'
      expect(store.isError).toBe(true)

      store.clearMessages()
      expect(store.isError).toBe(false)
    })

    it('should handle all message getters together', () => {
      const store = useGlobalStore()
      expect(store.isError).toBe(false)
      expect(store.isWarning).toBe(false)
      expect(store.isSuccess).toBe(false)
      expect(store.isInfo).toBe(false)

      store.messageError = 'Error'
      store.messageWarning = 'Warning'
      store.messageSuccess = 'Success'
      store.messageInfo = 'Info'

      expect(store.isError).toBe(true)
      expect(store.isWarning).toBe(true)
      expect(store.isSuccess).toBe(true)
      expect(store.isInfo).toBe(true)
    })
  })

  describe('Complex State Scenarios', () => {
    it('should manage multiple state changes independently', () => {
      const store = useGlobalStore()

      // Set up initial conditions
      store.initialized = true
      store.configChanged = true
      const preferences = usePreferencesStore()
      preferences.batchListFilterDevice = 'device-1'
      store.updatedDeviceData = 5
      store.messageError = 'Error occurred'

      // Verify all are set correctly
      expect(store.initialized).toBe(true)
      expect(store.configChanged).toBe(true)
      expect(preferences.batchListFilterDevice).toBe('device-1')
      expect(store.updatedDeviceData).toBe(5)
      expect(store.messageError).toBe('Error occurred')

      // Clear messages without affecting other state
      store.clearMessages()

      // Verify messages cleared but other state intact
      expect(store.messageError).toBe('')
      expect(store.initialized).toBe(true)
      expect(store.configChanged).toBe(true)
      expect(preferences.batchListFilterDevice).toBe('device-1')
      expect(store.updatedDeviceData).toBe(5)
    })

    it('should handle all change flags together', () => {
      const store = useGlobalStore()

      // All false initially
      expect(store.configChanged).toBe(false)
      expect(store.batchChanged).toBe(false)
      expect(store.deviceChanged).toBe(false)

      // Set one at a time
      store.configChanged = true
      expect(store.configChanged).toBe(true)
      expect(store.batchChanged).toBe(false)

      store.batchChanged = true
      expect(store.configChanged).toBe(true)
      expect(store.batchChanged).toBe(true)
      expect(store.deviceChanged).toBe(false)

      store.deviceChanged = true
      expect(store.configChanged).toBe(true)
      expect(store.batchChanged).toBe(true)
      expect(store.deviceChanged).toBe(true)
    })

    it('should reset all state to defaults', () => {
      const store = useGlobalStore()

      // Modify all state
      store.initialized = true
      const releaseBusy = store.acquireBusy()
      store.configChanged = true
      store.batchChanged = true
      store.deviceChanged = true
      store.messageError = 'Error'
      store.messageWarning = 'Warning'
      store.messageSuccess = 'Success'
      store.messageInfo = 'Info'
      store.updatedDeviceData = 10

      // Clear messages
      store.clearMessages()

      // Verify message getters are false
      expect(store.isError).toBe(false)
      expect(store.isWarning).toBe(false)
      expect(store.isSuccess).toBe(false)
      expect(store.isInfo).toBe(false)
      releaseBusy()
    })

    it('should maintain state consistency with both getters and setters', () => {
      const store = useGlobalStore()

      // Set message and verify getter
      store.messageError = 'Error'
      expect(store.isError).toBe(true)

      store.messageWarning = 'Warning'
      expect(store.isWarning).toBe(true)

      store.messageSuccess = 'Success'
      expect(store.isSuccess).toBe(true)

      store.messageInfo = 'Info'
      expect(store.isInfo).toBe(true)

      // All should be true
      expect(store.isError && store.isWarning && store.isSuccess && store.isInfo).toBe(true)

      // Clear all
      store.clearMessages()

      // All should be false
      expect(store.isError || store.isWarning || store.isSuccess || store.isInfo).toBe(false)
    })
  })

  describe('State Mutations', () => {
    it('should allow setting initialized state', () => {
      const store = useGlobalStore()
      store.initialized = true
      expect(store.initialized).toBe(true)
    })

    it('combines legacy busy state with overlapping idempotent busy leases', () => {
      const store = useGlobalStore()
      const releaseFirst = store.acquireBusy()
      const releaseSecond = store.acquireBusy()
      expect(store.disabled).toBe(true)

      releaseFirst()
      expect(store.disabled).toBe(true)
      releaseFirst()
      expect(store.busyOperations).toBe(1)

      releaseSecond()
      expect(store.disabled).toBe(false)
    })

    it('should allow setting change flags', () => {
      const store = useGlobalStore()
      store.configChanged = true
      store.batchChanged = true
      store.deviceChanged = true
      expect(store.configChanged).toBe(true)
      expect(store.batchChanged).toBe(true)
      expect(store.deviceChanged).toBe(true)
    })

    it('should allow setting batch list filters', () => {
      const preferences = usePreferencesStore()
      preferences.batchListFilterDevice = 'device-1'
      preferences.batchListFilterActive = true
      preferences.batchListFilterData = true
      expect(preferences.batchListFilterDevice).toBe('device-1')
      expect(preferences.batchListFilterActive).toBe(true)
      expect(preferences.batchListFilterData).toBe(true)
    })

    it('should allow incrementing notification counters', () => {
      const store = useGlobalStore()
      store.updatedDeviceData += 1
      store.updatedBatchData += 1
      store.updatedGravityData += 1
      store.updatedPourData += 1
      expect(store.updatedDeviceData).toBe(1)
      expect(store.updatedBatchData).toBe(1)
      expect(store.updatedGravityData).toBe(1)
      expect(store.updatedPourData).toBe(1)
    })

    it('should allow multiple increments of notification counters', () => {
      const store = useGlobalStore()
      store.updatedDeviceData = 5
      store.updatedDeviceData += 3
      expect(store.updatedDeviceData).toBe(8)
    })

    it('should allow resetting notification counters', () => {
      const store = useGlobalStore()
      store.updatedDeviceData = 10
      store.updatedBatchData = 20
      store.updatedGravityData = 30
      store.updatedPourData = 40

      store.updatedDeviceData = 0
      store.updatedBatchData = 0
      store.updatedGravityData = 0
      store.updatedPourData = 0

      expect(store.updatedDeviceData).toBe(0)
      expect(store.updatedBatchData).toBe(0)
      expect(store.updatedGravityData).toBe(0)
      expect(store.updatedPourData).toBe(0)
    })

    it('should maintain independent filter and notification states', () => {
      const store = useGlobalStore()
      const preferences = usePreferencesStore()
      preferences.batchListFilterDevice = 'device-1'
      store.updatedDeviceData = 5
      preferences.batchListFilterActive = true
      store.updatedBatchData = 10

      expect(preferences.batchListFilterDevice).toBe('device-1')
      expect(preferences.batchListFilterActive).toBe(true)
      expect(store.updatedDeviceData).toBe(5)
      expect(store.updatedBatchData).toBe(10)
    })

    it('should allow batch filter to reset to wildcard', () => {
      const preferences = usePreferencesStore()
      preferences.batchListFilterDevice = 'device-1'
      expect(preferences.batchListFilterDevice).toBe('device-1')
      preferences.batchListFilterDevice = '*'
      expect(preferences.batchListFilterDevice).toBe('*')
    })

    it('should allow device filter to reset to wildcard', () => {
      const preferences = usePreferencesStore()
      preferences.deviceListFilterDeviceType = 'v1.0'
      expect(preferences.deviceListFilterDeviceType).toBe('v1.0')
      preferences.deviceListFilterDeviceType = '*'
      expect(preferences.deviceListFilterDeviceType).toBe('*')
    })
  })

  describe('apiURL Getter', () => {
    it('should return apiURL with /api/ appended to baseURL', () => {
      const store = useGlobalStore()
      store.url = undefined
      import.meta.env.VITE_APP_HOST = 'http://example.com/'
      const apiUrl = store.apiURL
      expect(apiUrl).toBe('http://example.com/api/')
    })

    it('should cache apiURL based on baseURL', () => {
      const store = useGlobalStore()
      store.url = undefined
      import.meta.env.VITE_APP_HOST = 'http://test.com/'
      const apiUrl1 = store.apiURL
      const apiUrl2 = store.apiURL
      expect(apiUrl1).toBe(apiUrl2)
    })

    it('should include protocol and domain in apiURL', () => {
      const store = useGlobalStore()
      store.url = undefined
      import.meta.env.VITE_APP_HOST = 'https://api.example.com/'
      const apiUrl = store.apiURL
      expect(apiUrl).toContain('https://')
      expect(apiUrl).toContain('api.example.com')
      expect(apiUrl).toContain('/api/')
    })

    it('should handle baseURL from window.location.origin', () => {
      const store = useGlobalStore()
      store.url = undefined
      import.meta.env.VITE_APP_HOST = undefined
      // Reset environment
      const apiUrl = store.apiURL
      expect(apiUrl).toBeTruthy()
      expect(apiUrl).toContain('api')
    })
  })

  describe('hasUnsavedChanges Getter', () => {
    it('should return false when no changes', () => {
      const store = useGlobalStore()
      expect(store.hasUnsavedChanges).toBe(false)
    })

    it('should return true when configChanged is true', () => {
      const store = useGlobalStore()
      store.configChanged = true
      expect(store.hasUnsavedChanges).toBe(true)
    })

    it('should return true when batchChanged is true', () => {
      const store = useGlobalStore()
      store.batchChanged = true
      expect(store.hasUnsavedChanges).toBe(true)
    })

    it('should return true when deviceChanged is true', () => {
      const store = useGlobalStore()
      store.deviceChanged = true
      expect(store.hasUnsavedChanges).toBe(true)
    })

    it('should return true when tapChanged is true', () => {
      const store = useGlobalStore()
      store.tapChanged = true
      expect(store.hasUnsavedChanges).toBe(true)
    })

    it('should return true when vesselChanged is true', () => {
      const store = useGlobalStore()
      store.vesselChanged = true
      expect(store.hasUnsavedChanges).toBe(true)
    })

    it('should return true when multiple flags are true', () => {
      const store = useGlobalStore()
      store.configChanged = true
      store.batchChanged = true
      store.deviceChanged = true
      expect(store.hasUnsavedChanges).toBe(true)
    })

    it('should return false when all flags reset to false', () => {
      const store = useGlobalStore()
      store.configChanged = true
      store.batchChanged = true
      expect(store.hasUnsavedChanges).toBe(true)

      store.configChanged = false
      store.batchChanged = false
      expect(store.hasUnsavedChanges).toBe(false)
    })

    it('should return true when any single flag is true among multiple', () => {
      const store = useGlobalStore()
      store.configChanged = false
      store.batchChanged = false
      store.deviceChanged = false
      store.tapChanged = false
      store.vesselChanged = false
      expect(store.hasUnsavedChanges).toBe(false)

      store.tapChanged = true
      expect(store.hasUnsavedChanges).toBe(true)

      store.tapChanged = false
      store.vesselChanged = true
      expect(store.hasUnsavedChanges).toBe(true)
    })

    it('should handle combinations of true and false flags', () => {
      const store = useGlobalStore()
      store.configChanged = true
      store.batchChanged = false
      store.deviceChanged = true
      store.tapChanged = false
      store.vesselChanged = true
      expect(store.hasUnsavedChanges).toBe(true)

      store.configChanged = false
      store.deviceChanged = false
      store.vesselChanged = false
      expect(store.hasUnsavedChanges).toBe(false)
    })
  })

  describe('All Notification Counters', () => {
    it('should have all notification counters defined', () => {
      const store = useGlobalStore()
      expect(store.updatedDeviceData).toBeDefined()
      expect(store.updatedBatchData).toBeDefined()
      expect(store.updatedGravityData).toBeDefined()
      expect(store.updatedPressureData).toBeDefined()
      expect(store.updatedPourData).toBeDefined()
      expect(store.updatedTapData).toBeDefined()
      expect(store.updatedVesselData).toBeDefined()
    })

    it('should initialize all counters to 0', () => {
      const store = useGlobalStore()
      expect(store.updatedDeviceData).toBe(0)
      expect(store.updatedBatchData).toBe(0)
      expect(store.updatedGravityData).toBe(0)
      expect(store.updatedPressureData).toBe(0)
      expect(store.updatedPourData).toBe(0)
      expect(store.updatedTapData).toBe(0)
      expect(store.updatedVesselData).toBe(0)
    })

    it('should allow incrementing all counters independently', () => {
      const store = useGlobalStore()
      store.updatedDeviceData = 1
      store.updatedBatchData = 2
      store.updatedGravityData = 3
      store.updatedPressureData = 4
      store.updatedPourData = 5
      store.updatedTapData = 6
      store.updatedVesselData = 7

      expect(store.updatedDeviceData).toBe(1)
      expect(store.updatedBatchData).toBe(2)
      expect(store.updatedGravityData).toBe(3)
      expect(store.updatedPressureData).toBe(4)
      expect(store.updatedPourData).toBe(5)
      expect(store.updatedTapData).toBe(6)
      expect(store.updatedVesselData).toBe(7)
    })
  })

  describe('Additional Change Flags', () => {
    it('should have all change flags defined', () => {
      const store = useGlobalStore()
      expect(store.configChanged).toBeDefined()
      expect(store.batchChanged).toBeDefined()
      expect(store.deviceChanged).toBeDefined()
      expect(store.tapChanged).toBeDefined()
      expect(store.vesselChanged).toBeDefined()
    })

    it('should initialize all change flags to false', () => {
      const store = useGlobalStore()
      expect(store.configChanged).toBe(false)
      expect(store.batchChanged).toBe(false)
      expect(store.deviceChanged).toBe(false)
      expect(store.tapChanged).toBe(false)
      expect(store.vesselChanged).toBe(false)
    })

    it('should handle fetching timeout', () => {
      const store = useGlobalStore()
      expect(store.fetchTimout).toBe(30000)
    })

  })
})
