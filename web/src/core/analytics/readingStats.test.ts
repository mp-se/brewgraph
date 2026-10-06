import { afterEach, describe, expect, it, vi } from 'vitest'
import { readingStats } from './readingStats'

afterEach(() => vi.unstubAllEnvs())

describe('readingStats local display fields', () => {
  it('derives first and last date/time in the local timezone', () => {
    vi.stubEnv('TZ', 'Europe/Stockholm')
    const readings = [
      { value: 1.05, temperature: 20, created: '2026-01-01T23:30:00Z' },
      { value: 1.02, temperature: 19, created: '2026-01-02T00:30:00Z' }
    ]

    const stats = readingStats(readings, {
      getValue: (reading) => reading.value,
      getCreated: (reading) => reading.created
    })

    expect(stats.date.first).toBe('2026-01-01T23:30:00Z')
    expect(stats.date.firstDate).toBe('2026-01-02')
    expect(stats.date.firstTime).toBe('00:30:00')
    expect(stats.date.lastDate).toBe('2026-01-02')
    expect(stats.date.lastTime).toBe('01:30:00')
  })
})
