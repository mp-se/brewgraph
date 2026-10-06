import { abv, gravityToPlato, tempToF } from '../calculations/units'
import { MovingAverageFilter, type NumericPoint } from '../calculations/movingAverage'

export interface GravitySeriesReading {
  created: string | Date
  gravity: number
  battery?: number
  temperature?: number | null
  chamberTemperature?: number | null
  velocity?: number | null
}

export function gravityPoints(
  readings: GravitySeriesReading[],
  useSpecificGravity: boolean,
  toPlato: (specificGravity: number) => number = gravityToPlato
): NumericPoint<string | Date>[] {
  return readings.map((reading) => ({
    x: reading.created,
    y: Number((useSpecificGravity ? reading.gravity : toPlato(reading.gravity)).toFixed(4))
  }))
}

export function temperaturePoints(
  readings: GravitySeriesReading[],
  useCelsius: boolean,
  toFahrenheit: (celsius: number) => number = tempToF
): NumericPoint<string | Date>[] {
  return readings
    .filter((reading) => reading.temperature !== null && reading.temperature !== undefined)
    .map((reading) => ({
      x: reading.created,
      y: Number((useCelsius ? reading.temperature! : toFahrenheit(reading.temperature!)).toFixed(2))
    }))
}

export function alcoholPoints(
  readings: GravitySeriesReading[],
  calculateAbv: (originalGravity: number, finalGravity: number) => number = abv
): NumericPoint<string | Date>[] {
  const originalGravity = Math.max(...readings.map((reading) => reading.gravity))
  return readings.map((reading) => ({
    x: reading.created,
    y: Number(calculateAbv(originalGravity, reading.gravity).toFixed(2))
  }))
}

export function gravityVelocityPoints(readings: GravitySeriesReading[]): {
  velocity: NumericPoint<string | Date>[]
  development: NumericPoint<string | Date>[]
} {
  const development: NumericPoint<string | Date>[] = []
  const filter = new MovingAverageFilter(10)
  const slots: { time: number | null; totalGravity: number; count: number }[] = []
  let currentSlot = { time: null as number | null, totalGravity: 0, count: 0 }

  for (const reading of readings) {
    const createdTime = new Date(reading.created).getTime()
    const gravity = filter.process(reading.gravity)
    if (!currentSlot.time) currentSlot.time = createdTime
    if (createdTime - currentSlot.time < 3600 * 1000) {
      currentSlot.totalGravity += gravity
      currentSlot.count++
    } else {
      slots.push(currentSlot)
      currentSlot = { time: null, totalGravity: 0, count: 0 }
    }
    if (reading.velocity !== null && reading.velocity !== undefined) {
      development.push({ x: new Date(reading.created), y: reading.velocity })
    }
  }
  if (currentSlot.count > 0) slots.push(currentSlot)

  const velocity: NumericPoint<string | Date>[] = []
  for (let index = 1; index < slots.length; index++) {
    const previous = slots[index - 1]
    const current = slots[index]
    velocity.push({
      x: new Date(current.time as number),
      y: (current.totalGravity / current.count - previous.totalGravity / previous.count) * 24 * 1000
    })
  }
  return { velocity, development }
}
