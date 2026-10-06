import { describe, expect, it } from 'vitest'
import {
  fermentationStepsPayload,
  hasActiveFermentationStepAt,
  parseFermentationStepsForEditor,
  serializeFermentationSteps
} from '@brewgraph/core'

describe('shared fermentation steps', () => {
  it('converts canonical Celsius storage values for a Fahrenheit editor', () => {
    expect(parseFermentationStepsForEditor('[{"temp":20}]', { usesFahrenheit: true })[0].temp).toBe(68)
  })

  it('serializes and builds API-ready normalized steps in Celsius', () => {
    const steps = [{ order: 4, name: 'Warm', type: 'Hold', temp: 68, days: 2, date: '', control: undefined }]
    expect(serializeFermentationSteps(steps, { usesFahrenheit: true })).toContain('"temp":20')
    expect(fermentationStepsPayload('batch-1', steps, { usesFahrenheit: true })[0]).toMatchObject({
      batchId: 'batch-1', order: 0, temp: 20, date: null, control: 'fridge'
    })
  })

  it('evaluates date windows deterministically', () => {
    expect(hasActiveFermentationStepAt([{ date: '2026-01-10', days: 3 }], new Date('2026-01-12T12:00:00'))).toBe(true)
    expect(hasActiveFermentationStepAt([{ date: '2026-01-10', days: 3 }], new Date('2026-01-13T12:00:00'))).toBe(false)
  })
})
