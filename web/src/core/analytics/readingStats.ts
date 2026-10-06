export interface ReadingWithTemperature {
  excluded?: boolean
  temperature: number | null
}

export interface ReadingStats {
  value: { min: number; max: number }
  temperature: { min: number; max: number }
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

export interface ReadingStatsOptions<T extends ReadingWithTemperature> {
  getValue: (reading: T) => number
  getCreated: (reading: T) => string
  isValidTemperature?: (temperature: number) => boolean
  initialValueMin?: number
  initialValueMax?: number
}

/** Aggregate active device readings without mutating the caller's collection. */
export function readingStats<T extends ReadingWithTemperature>(
  readings: T[],
  options: ReadingStatsOptions<T>
): ReadingStats {
  const active = readings
    .filter((reading) => !reading.excluded)
    .slice()
    .sort((a, b) => Date.parse(options.getCreated(a)) - Date.parse(options.getCreated(b)))
  const stats: ReadingStats = {
    value: { min: options.initialValueMin ?? 2, max: options.initialValueMax ?? 0 },
    temperature: { min: 100, max: -100 },
    date: { first: '', last: '', firstDate: '', lastDate: '', firstTime: '', lastTime: '' },
    readings: active.length,
    averageInterval: 0,
    averageIntervalString: ''
  }

  for (const reading of active) {
    const value = options.getValue(reading)
    if (value > stats.value.max) stats.value.max = value
    if (value < stats.value.min) stats.value.min = value
    if (
      reading.temperature !== null &&
      (options.isValidTemperature?.(reading.temperature) ?? true)
    ) {
      if (reading.temperature > stats.temperature.max) stats.temperature.max = reading.temperature
      if (reading.temperature < stats.temperature.min) stats.temperature.min = reading.temperature
    }
  }

  if (!active.length) return stats

  stats.date.first = options.getCreated(active[0])
  stats.date.last = options.getCreated(active[active.length - 1])
  stats.date.firstDate = localTimestampParts(stats.date.first).date
  stats.date.lastDate = localTimestampParts(stats.date.last).date
  stats.date.firstTime = localTimestampParts(stats.date.first).time
  stats.date.lastTime = localTimestampParts(stats.date.last).time
  stats.averageInterval = new Number(
    (Date.parse(stats.date.last) - Date.parse(stats.date.first)) / active.length / 1000
  ).toFixed(0)
  stats.averageIntervalString =
    Number(stats.averageInterval) < 60
      ? stats.averageInterval + ' s'
      : new Number(Number(stats.averageInterval) / 60).toFixed(0) +
        ' m ' +
        new Number(Number(stats.averageInterval) % 60).toFixed(0) +
        ' s'
  return stats
}
import { localTimestampParts } from '../utilities/textTime'
