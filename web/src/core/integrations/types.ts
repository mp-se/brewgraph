export const INTEGRATION_TYPE_ISPINDEL_FORWARD = 'ispindel_forward'
export const INTEGRATION_TYPE_BREWFATHER_FORWARD = 'brewfather_forward'
export const INTEGRATION_TYPE_CUSTOM_FORWARD = 'custom_forward'

export const MEASUREMENT_GRAVITY = 'gravity'
export const MEASUREMENT_PRESSURE = 'pressure'
export const MEASUREMENT_POUR = 'pour'
export const MEASUREMENT_TEMP = 'temp'

/**
 * Integration types allowed by the shared API contract for a measurement. ispindel_forward is
 * gravity-only, brewfather_forward (Brewfather's custom stream) also takes pressure and temp,
 * and pour only offers Custom.
 */
export function integrationTypesFor(measurement: string): string[] {
  switch (measurement) {
    case MEASUREMENT_GRAVITY:
      return [
        INTEGRATION_TYPE_ISPINDEL_FORWARD,
        INTEGRATION_TYPE_BREWFATHER_FORWARD,
        INTEGRATION_TYPE_CUSTOM_FORWARD
      ]
    case MEASUREMENT_PRESSURE:
    case MEASUREMENT_TEMP:
      return [INTEGRATION_TYPE_BREWFATHER_FORWARD, INTEGRATION_TYPE_CUSTOM_FORWARD]
    default:
      return [INTEGRATION_TYPE_CUSTOM_FORWARD]
  }
}

/**
 * The type a target keeps when its measurement changes: the current one if the new measurement
 * offers it, else Custom, the one type every measurement offers.
 */
export function integrationTypeAfterMeasurementChange(type: string, measurement: string): string {
  return integrationTypesFor(measurement).includes(type) ? type : INTEGRATION_TYPE_CUSTOM_FORWARD
}
