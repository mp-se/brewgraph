/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 *
 * This file is part of BrewGraph. For open source use it is licensed under
 * the GNU General Public License v3.0. For commercial use without source
 * disclosure, a separate Commercial License is required.
 * See LICENSE for details.
 */

import {
  INTEGRATION_TYPE_BREWFATHER_FORWARD,
  INTEGRATION_TYPE_CUSTOM_FORWARD,
  INTEGRATION_TYPE_ISPINDEL_FORWARD,
  integrationTypesFor,
  MEASUREMENT_GRAVITY,
  MEASUREMENT_POUR,
  MEASUREMENT_PRESSURE,
  MEASUREMENT_TEMP
} from '@brewgraph/core'

export {
  INTEGRATION_TYPE_BREWFATHER_FORWARD,
  INTEGRATION_TYPE_CUSTOM_FORWARD,
  INTEGRATION_TYPE_ISPINDEL_FORWARD,
  MEASUREMENT_GRAVITY,
  MEASUREMENT_POUR,
  MEASUREMENT_PRESSURE,
  MEASUREMENT_TEMP
}

export const measurementOptions = [
  { label: 'Gravity', value: MEASUREMENT_GRAVITY },
  { label: 'Pressure', value: MEASUREMENT_PRESSURE },
  { label: 'Pour', value: MEASUREMENT_POUR },
  { label: 'Temperature', value: MEASUREMENT_TEMP }
]

export const integrationTypeOptions = [
  { label: 'iSpindel forward', value: INTEGRATION_TYPE_ISPINDEL_FORWARD },
  { label: 'Brewfather custom stream', value: INTEGRATION_TYPE_BREWFATHER_FORWARD },
  { label: 'Custom', value: INTEGRATION_TYPE_CUSTOM_FORWARD }
]

/** Gravity offers all three types; pressure and temperature offer Brewfather custom stream and
 * Custom; pour offers only Custom (iSpindel forward is gravity-only). */
export function integrationTypeOptionsFor(measurement: string) {
  const allowed = integrationTypesFor(measurement)
  return integrationTypeOptions.filter((option) => allowed.includes(option.value))
}

export interface IntegrationConfigData {
  url: string
  method: string
  headers: Record<string, string>
  template: string | null
}

interface IntegrationParams {
  id?: string
  name?: string
  measurement?: string
  type?: string
  enabled?: boolean
  config?: Partial<IntegrationConfigData>
  createdAt?: string
  updatedAt?: string
  consecutiveFailures?: number
  lastSuccessAt?: string | null
  lastFailureAt?: string | null
  lastFailureCode?: string | null
  disabledReason?: string | null
  version?: number
}

export class Integration {
  private _id: string
  private _name: string
  private _measurement: string
  private _type: string
  private _enabled: boolean
  private _config: IntegrationConfigData
  private _createdAt: string
  private _updatedAt: string
  private _consecutiveFailures: number
  private _lastSuccessAt: string | null
  private _lastFailureAt: string | null
  private _lastFailureCode: string | null
  private _disabledReason: string | null
  private _version: number

  constructor({
    id = '',
    name = '',
    measurement = MEASUREMENT_GRAVITY,
    type = INTEGRATION_TYPE_ISPINDEL_FORWARD,
    enabled = true,
    config = {},
    createdAt = '',
    updatedAt = '', consecutiveFailures = 0, lastSuccessAt = null, lastFailureAt = null,
    lastFailureCode = null, disabledReason = null, version = 1
  }: IntegrationParams = {}) {
    this._id = id
    this._name = name
    this._measurement = measurement
    this._type = type
    this._enabled = enabled
    this._config = {
      url: config.url ?? '',
      method: config.method ?? 'POST',
      headers: config.headers ?? {},
      template: config.template ?? null
    }
    this._createdAt = createdAt
    this._updatedAt = updatedAt
    this._consecutiveFailures = consecutiveFailures
    this._lastSuccessAt = lastSuccessAt
    this._lastFailureAt = lastFailureAt
    this._lastFailureCode = lastFailureCode
    this._disabledReason = disabledReason
    this._version = version
  }

  static fromJson(d: Record<string, unknown>): Integration {
    const config = (d.config as Record<string, unknown>) ?? {}
    return new Integration({
      id: d.id as string,
      name: (d.name as string) ?? '',
      measurement: (d.measurement as string) ?? MEASUREMENT_GRAVITY,
      type: (d.type as string) ?? INTEGRATION_TYPE_ISPINDEL_FORWARD,
      enabled: (d.enabled as boolean) ?? true,
      config: {
        url: (config.url as string) ?? '',
        method: (config.method as string) ?? 'POST',
        headers: (config.headers as Record<string, string>) ?? {},
        template: (config.template as string | null) ?? null
      },
      createdAt: (d.createdAt as string) ?? '',
      updatedAt: (d.updatedAt as string) ?? ''
      , consecutiveFailures: (d.consecutiveFailures as number) ?? 0
      , lastSuccessAt: (d.lastSuccessAt as string | null) ?? null
      , lastFailureAt: (d.lastFailureAt as string | null) ?? null
      , lastFailureCode: (d.lastFailureCode as string | null) ?? null
      , disabledReason: (d.disabledReason as string | null) ?? null
      , version: (d.version as number) ?? 1
    })
  }

  /** Only `method`/`headers`/`template` are meaningful for `custom_forward` — the two
   * built-in types define their own payload shape server-side and reject a template.
   * `measurement` is only sent on create — PATCH never includes it, since it is
   * immutable server-side (see `updateIntegration` in `integrationStore.ts`). */
  toJson(): Record<string, unknown> {
    const config: Record<string, unknown> = { url: this.config.url }
    if (this.type === INTEGRATION_TYPE_CUSTOM_FORWARD) {
      config.method = this.config.method
      config.headers = this.config.headers
      config.template = this.config.template
    }
    return {
      name: this.name,
      measurement: this.measurement,
      type: this.type,
      enabled: this.enabled,
      config
    }
  }

  get id() {
    return this._id
  }
  get name() {
    return this._name
  }
  set name(v: string) {
    this._name = v
  }
  get measurement() {
    return this._measurement
  }
  set measurement(v: string) {
    this._measurement = v
  }
  get type() {
    return this._type
  }
  set type(v: string) {
    this._type = v
  }
  get enabled() {
    return this._enabled
  }
  set enabled(v: boolean) {
    this._enabled = v
  }
  get config() {
    return this._config
  }
  set config(v: IntegrationConfigData) {
    this._config = v
  }
  get createdAt() {
    return this._createdAt
  }
  get updatedAt() {
    return this._updatedAt
  }
  get consecutiveFailures() { return this._consecutiveFailures }
  get lastSuccessAt() { return this._lastSuccessAt }
  get lastFailureAt() { return this._lastFailureAt }
  get lastFailureCode() { return this._lastFailureCode }
  get disabledReason() { return this._disabledReason }
  get version() { return this._version }
}
