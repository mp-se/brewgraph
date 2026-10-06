/** Incremental simple moving-average filter for numeric telemetry. */
export class MovingAverageFilter {
  /** Current samples; public for compatibility with existing diagnostic consumers. */
  readonly data: number[] = []

  constructor(readonly windowSize: number) {}

  process(value: number): number {
    this.data.push(value)
    if (this.data.length > this.windowSize) this.data.shift()
    return this.data.reduce((sum, current) => sum + current, 0) / this.data.length
  }
}

export interface NumericPoint<TX = unknown> {
  x: TX
  y: number
}

export function applyMovingAverage<TX>(
  points: readonly NumericPoint<TX>[],
  windowSize: number
): NumericPoint<TX>[] {
  const filter = new MovingAverageFilter(windowSize)
  return points.map((point) => ({ x: point.x, y: filter.process(point.y) }))
}
