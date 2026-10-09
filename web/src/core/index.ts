/**
 * Framework-neutral BrewGraph domain logic.
 *
 * This package deliberately has no Vue, Pinia, UI-library, HTTP-client, auth,
 * or product-specific API dependencies. Applications provide those at their
 * boundaries and consume the types and transformations exported here.
 */

export * from './integrations/integrationPreview'
export * from './import-export/beerXml'
export * from './utilities/pagination'
export * from './calculations/units'
export * from './calculations/movingAverage'
export * from './fermentation/dryHops'
export * from './fermentation/steps'
export * from './utilities/textTime'
export * from './analytics/readingStats'
export * from './analytics/gravitySeries'
export * from './devices/detect'
export * from './devices/assignment'
export * from './utilities/sorting'
export * from './utilities/precision'
export * from './validation/errorSummary'
export * from './integrations/types'
export * from './settings/formats'
export * from './gravityFormula'
