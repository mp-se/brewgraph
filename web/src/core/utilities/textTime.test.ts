import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  formatLocalTimestamp,
  localDateEnd,
  localDateStart,
  localTimestampParts,
  shiftLocalDate
} from './textTime'

afterEach(() => vi.unstubAllEnvs())

describe('local timestamp helpers', () => {
  it('formats ISO timestamps in the viewer timezone', () => {
    vi.stubEnv('TZ', 'Europe/Stockholm')

    expect(localTimestampParts('2026-01-02T03:04:05Z')).toEqual({
      date: '2026-01-02',
      time: '04:04:05'
    })
    expect(formatLocalTimestamp('2026-01-02T03:04:05Z')).toBe('2026-01-02 04:04:05')
  })

  it('uses local calendar boundaries and shifts across DST by calendar day', () => {
    vi.stubEnv('TZ', 'Europe/Stockholm')
    const start = localDateStart('2026-03-29')
    const end = localDateEnd('2026-03-29')

    expect(new Date(start).getHours()).toBe(0)
    expect(new Date(end).getHours()).toBe(23)
    expect(end - start).toBe(23 * 60 * 60 * 1000 - 1)
    expect(shiftLocalDate('2026-03-30', -1)).toBe('2026-03-29')
  })

  it('rejects invalid calendar dates and preserves malformed timestamp text', () => {
    expect(Number.isNaN(localDateStart('2026-02-30'))).toBe(true)
    expect(Number.isNaN(localDateEnd('not-a-date'))).toBe(true)
    expect(shiftLocalDate('not-a-date', -1)).toBe('')
    expect(formatLocalTimestamp('bad')).toBe('bad')
  })
})
