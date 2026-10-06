import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { usePreferencesStore } from '@/modules/preferencesStore'

describe('usePreferencesStore', () => {
  const storage = new Map()
  let failReads = false
  let failWrites = false

  beforeEach(() => {
    storage.clear()
    failReads = false
    failWrites = false
    vi.stubGlobal('localStorage', {
      getItem: key => {
        if (failReads) throw new Error('storage unavailable')
        return storage.has(key) ? storage.get(key) : null
      },
      setItem: (key, value) => {
        if (failWrites) throw new Error('storage unavailable')
        storage.set(key, String(value))
      },
      clear: () => storage.clear()
    })
    setActivePinia(createPinia())
  })

  it('loads persisted values and applies defaults for missing keys', () => {
    localStorage.setItem('batchListFilterDevice', 'device-1')
    localStorage.setItem('batchListFilterData', 'true')
    localStorage.setItem('dark_mode', 'true')

    const preferences = usePreferencesStore()

    expect(preferences.batchListFilterDevice).toBe('device-1')
    expect(preferences.batchListFilterData).toBe(true)
    expect(preferences.dark_mode).toBe(true)
    expect(preferences.batchListFilterActive).toBe(false)
    expect(preferences.deviceListFilterDeviceType).toBe('*')
    expect(preferences.showChamberTemps).toBe(false)
    expect(preferences.showKegmonTaps).toBe(false)
  })

  it('preserves an intentionally blank device filter', () => {
    localStorage.setItem('batchListFilterDevice', '')

    expect(usePreferencesStore().batchListFilterDevice).toBe('')
  })

  it('persists updates without App-level watchers', async () => {
    const preferences = usePreferencesStore()
    preferences.batchListFilterDevice = 'device-2'
    preferences.batchListFilterActive = true
    preferences.dark_mode = true

    await nextTick()

    expect(localStorage.getItem('batchListFilterDevice')).toBe('device-2')
    expect(localStorage.getItem('batchListFilterActive')).toBe('true')
    expect(localStorage.getItem('dark_mode')).toBe('true')
  })

  it('keeps session defaults when reading browser storage throws', () => {
    failReads = true
    const preferences = usePreferencesStore()

    expect(preferences.batchListFilterDevice).toBe('*')
    expect(preferences.batchListFilterData).toBe(false)
    expect(preferences.dark_mode).toBe(false)
  })

  it('keeps in-session preferences when browser storage writes throw', async () => {
    const preferences = usePreferencesStore()
    failWrites = true
    preferences.batchListFilterDevice = 'device-2'
    preferences.batchListFilterActive = true
    preferences.batchListFilterData = true
    preferences.deviceListFilterDeviceType = 'gravitymon'
    preferences.showChamberTemps = true
    preferences.showKegmonTaps = true
    preferences.dark_mode = true

    await nextTick()

    expect(preferences.showKegmonTaps).toBe(true)
    expect(preferences.dark_mode).toBe(true)
  })

  it('uses defaults and skips persistence when localStorage is absent', async () => {
    vi.stubGlobal('localStorage', undefined)
    const preferences = usePreferencesStore()

    expect(preferences.batchListFilterDevice).toBe('*')
    preferences.batchListFilterDevice = 'session-only'
    await nextTick()
    expect(preferences.batchListFilterDevice).toBe('session-only')
  })
})
