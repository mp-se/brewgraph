import { describe, expect, it } from 'vitest'
import {
  DUMMY_READINGS,
  integrationTypeAfterMeasurementChange,
  integrationTypesFor,
  previewIntegration,
  renderTemplate,
  TEMPLATE_EXAMPLES,
  TEMPLATE_TOKENS_BY_MEASUREMENT
} from '@brewgraph/core'

describe('shared integration preview', () => {
  it('starts every measurement from a complete JSON template that renders to a JSON object', () => {
    for (const measurement of Object.keys(TEMPLATE_EXAMPLES) as Array<
      keyof typeof TEMPLATE_EXAMPLES
    >) {
      const example = TEMPLATE_EXAMPLES[measurement]
      // Complete: every token the measurement offers appears in the example.
      for (const token of TEMPLATE_TOKENS_BY_MEASUREMENT[measurement]) {
        expect(example.includes('${' + token + '}'), `${measurement} example has ${token}`).toBe(
          true
        )
      }
      const preview = previewIntegration(
        'custom_forward',
        { url: 'https://example.invalid', template: example },
        measurement
      )
      expect(preview.bodyIsJson, `${measurement} renders to JSON`).toBe(true)
      expect(typeof preview.body, `${measurement} renders to an object`).toBe('object')
    }
  })

  it('renders only tokens supported by the requested measurement', () => {
    expect(renderTemplate('${pressure}|${temperature}|${gravity}', 'pressure')).toBe(
      '12.5|4|${gravity}'
    )
    expect(TEMPLATE_TOKENS_BY_MEASUREMENT.pour).toContain('pourAmount')
  })

  it('creates a JSON custom-forward preview when its rendered payload is JSON', () => {
    expect(
      previewIntegration('custom_forward', {
        url: 'https://example.invalid/webhook',
        template: '{"gravity":"${gravity}"}'
      })
    ).toEqual({
      method: 'POST',
      headers: {},
      body: { gravity: '1.042' },
      bodyIsJson: true
    })
  })

  it('keeps custom GET payloads as raw text', () => {
    expect(
      previewIntegration(
        'custom_forward',
        { url: 'https://example.invalid/webhook', method: 'GET', template: 'pour=${pourAmount}' },
        'pour'
      )
    ).toEqual({
      method: 'GET',
      headers: {},
      body: 'pour=0.33',
      bodyIsJson: false
    })
  })

  it('previews the original iSpindel format with the chip id, battery and a fixed interval', () => {
    const preview = previewIntegration('ispindel_forward', { url: 'https://example.invalid' })
    expect(preview.method).toBe('POST')
    expect(preview.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(preview.body).toEqual({
      name: 'Fermenter 1',
      ID: 'a1b2c3',
      angle: 45.2,
      temperature: 20.5,
      temp_units: 'C',
      battery: 3.98,
      gravity: 1.042,
      interval: 900,
      RSSI: -62
    })
    expect(preview.body).not.toHaveProperty('token')
  })

  it("previews Brewfather's custom stream format with the [SG] suffix on the name", () => {
    const preview = previewIntegration('brewfather_forward', { url: 'https://example.invalid' })
    expect(preview.body).toEqual({
      name: 'Fermenter 1[SG]',
      temp: 20.5,
      temp_unit: 'C',
      gravity: 1.042,
      gravity_unit: 'G',
      battery: 3.98,
      angle: 45.2,
      rssi: -62
    })
  })

  it("previews Brewfather's custom stream for pressure: kPa, own temperature, no [SG]", () => {
    const preview = previewIntegration(
      'brewfather_forward',
      { url: 'https://example.invalid' },
      'pressure'
    )
    expect(preview.method).toBe('POST')
    expect(preview.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(preview.body).toEqual({
      name: 'Fermenter 1',
      pressure: 12.5,
      pressure_unit: 'KPA',
      temp: 4.0,
      temp_unit: 'C',
      battery: 3.98,
      rssi: -62
    })
  })

  it("previews Brewfather's custom stream for temperature with no [SG] suffix", () => {
    const preview = previewIntegration(
      'brewfather_forward',
      { url: 'https://example.invalid' },
      'temp'
    )
    expect(preview.body).toEqual({
      name: 'Fermenter 1',
      temp: 18.5,
      temp_unit: 'C',
      battery: 3.98,
      rssi: -62
    })
  })

  it('offers each measurement only the types the server accepts', () => {
    expect(integrationTypesFor('gravity')).toEqual([
      'ispindel_forward',
      'brewfather_forward',
      'custom_forward'
    ])
    expect(integrationTypesFor('pressure')).toEqual(['brewfather_forward', 'custom_forward'])
    expect(integrationTypesFor('temp')).toEqual(['brewfather_forward', 'custom_forward'])
    expect(integrationTypesFor('pour')).toEqual(['custom_forward'])
  })

  it('keeps a type that the new measurement offers and falls back to Custom otherwise', () => {
    const after = integrationTypeAfterMeasurementChange
    expect(after('brewfather_forward', 'pressure')).toBe('brewfather_forward')
    expect(after('brewfather_forward', 'temp')).toBe('brewfather_forward')
    expect(after('brewfather_forward', 'pour')).toBe('custom_forward')
    expect(after('ispindel_forward', 'pressure')).toBe('custom_forward')
    expect(after('ispindel_forward', 'temp')).toBe('custom_forward')
    expect(after('ispindel_forward', 'gravity')).toBe('ispindel_forward')
    expect(after('custom_forward', 'pour')).toBe('custom_forward')
  })

  // Pinned to the same literals as _DUMMY_READINGS in api/oss/services/integration.py and the
  // server test tests/test_integration_test_delivery.py: test delivery sends this very reading.
  it('keeps the dummy readings identical to the ones test delivery sends', () => {
    const common = {
      deviceName: 'Fermenter 1',
      deviceId: '00000000-0000-0000-0000-000000000001',
      chipId: 'a1b2c3',
      batchId: '00000000-0000-0000-0000-000000000002',
      timestamp: '2026-01-01T12:00:00+00:00'
    }
    expect(DUMMY_READINGS.gravity).toEqual({
      ...common,
      gravity: 1.042,
      temperature: 20.5,
      angle: 45.2,
      velocity: 0.15,
      battery: 3.98,
      rssi: -62
    })
    expect(DUMMY_READINGS.pressure).toEqual({
      ...common,
      pressure: 12.5,
      temperature: 4.0,
      battery: 3.98,
      rssi: -62
    })
    expect(DUMMY_READINGS.temp).toEqual({
      ...common,
      temperature: 18.5,
      tempType: 'beer',
      battery: 3.98,
      rssi: -62
    })
    expect(DUMMY_READINGS.pour).toEqual({
      pourAmount: 0.33,
      volumeRemaining: 12.4,
      tapId: '00000000-0000-0000-0000-000000000003',
      tapName: 'Tap 1',
      vesselId: '00000000-0000-0000-0000-000000000004',
      batchId: common.batchId,
      timestamp: common.timestamp
    })
  })

  it('uses the target name as the device name, and falls back when it is blank', () => {
    const body = (type: string, measurement: 'gravity' | 'pressure' | 'temp', name?: string) =>
      previewIntegration(type, { url: 'https://example.invalid' }, measurement, name).body as {
        name: string
      }
    expect(body('ispindel_forward', 'gravity', 'My iSpindel').name).toBe('My iSpindel')
    expect(body('brewfather_forward', 'gravity', 'My iSpindel').name).toBe('My iSpindel[SG]')
    expect(body('brewfather_forward', 'pressure', 'Keg 2').name).toBe('Keg 2')
    expect(body('brewfather_forward', 'temp', 'Chamber').name).toBe('Chamber')
    expect(body('brewfather_forward', 'temp', '  ').name).toBe('Fermenter 1')
    expect(body('brewfather_forward', 'temp').name).toBe('Fermenter 1')
    expect(renderTemplate('${deviceName}', 'gravity', 'My iSpindel')).toBe('My iSpindel')
  })
})
