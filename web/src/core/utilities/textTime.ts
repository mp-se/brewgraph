/** Framework-independent text and elapsed-time helpers. */
export interface LocalTimestampParts {
  date: string
  time: string
}

const pad2 = (value: number): string => String(value).padStart(2, '0')

/** Format an API timestamp in the browser's local timezone, preserving ISO-like output. */
export function localTimestampParts(timestamp: string): LocalTimestampParts {
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) {
    return { date: timestamp.substring(0, 10), time: timestamp.substring(11, 19) }
  }

  return {
    date: `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`,
    time: `${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`
  }
}

export function formatLocalTimestamp(timestamp: string): string {
  const { date, time } = localTimestampParts(timestamp)
  return time ? `${date} ${time}` : date
}

function localMidnight(date: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date)
  if (!match) return null
  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const parsed = new Date(year, month - 1, day)
  return parsed.getFullYear() === year && parsed.getMonth() === month - 1 && parsed.getDate() === day
    ? parsed
    : null
}

/** Local epoch boundary for an HTML date input value (YYYY-MM-DD). */
export function localDateStart(date: string): number {
  return localMidnight(date)?.getTime() ?? Number.NaN
}

/** Inclusive local epoch boundary for an HTML date input value (YYYY-MM-DD). */
export function localDateEnd(date: string): number {
  const start = localMidnight(date)
  if (!start) return Number.NaN
  start.setDate(start.getDate() + 1)
  return start.getTime() - 1
}

/** Shift a local calendar date by calendar days, respecting daylight-saving changes. */
export function shiftLocalDate(date: string, days: number): string {
  const shifted = localMidnight(date)
  if (!shifted || !Number.isFinite(days)) return ''
  shifted.setDate(shifted.getDate() + Math.trunc(days))
  return `${shifted.getFullYear()}-${pad2(shifted.getMonth() + 1)}-${pad2(shifted.getDate())}`
}

export function truncateString(value: string, maxLength: number): string {
  return value.length <= maxLength ? value : value.substring(0, maxLength) + '...'
}

export function relativeTime(created: string | Date, now: Date = new Date()): string {
  const diffHours = (now.getTime() - new Date(created).getTime()) / (1000 * 60 * 60)
  const diffDays = diffHours / 24

  if (diffHours < 1) return 'just now'
  if (diffHours < 24) return Math.round(diffHours) + ' h ago'
  if (diffDays < 7) return Math.round(diffDays) + ' d ago'
  return Math.round(diffDays / 7) + ' w ago'
}

/** A compact duration containing weeks, days, and hours (minutes and seconds omitted). */
export function formatDurationShort(secondsTotal: number): string {
  const hours = Math.floor((secondsTotal % (24 * 60 * 60)) / (60 * 60))
  const days = Math.floor((secondsTotal % (7 * 24 * 60 * 60)) / (24 * 60 * 60))
  const weeks = Math.floor((secondsTotal % (365 * 24 * 60 * 60)) / (7 * 24 * 60 * 60))

  let result = ''
  if (weeks > 0) result += weeks + 'w '
  if (days > 0) result += days + 'd '
  if (hours > 0) result += hours + 'h '
  return result
}
