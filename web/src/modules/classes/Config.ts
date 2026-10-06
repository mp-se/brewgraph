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
  GRAVITY_FORMAT_PLATO,
  GRAVITY_FORMAT_SG,
  PRESSURE_FORMAT_BAR,
  PRESSURE_FORMAT_KPA,
  PRESSURE_FORMAT_PSI,
  TEMPERATURE_FORMAT_C,
  TEMPERATURE_FORMAT_F,
  VESSEL_STATUS_CLEAN,
  VESSEL_STATUS_CONDITIONING,
  VESSEL_STATUS_FILLED,
  VESSEL_STATUS_SERVING,
  VESSEL_TYPE_BOTTLE,
  VESSEL_TYPE_KEG,
  VOLUME_FORMAT_METRIC,
  VOLUME_FORMAT_UK,
  VOLUME_FORMAT_US
} from '@brewgraph/core'

export {
  GRAVITY_FORMAT_PLATO,
  GRAVITY_FORMAT_SG,
  PRESSURE_FORMAT_BAR,
  PRESSURE_FORMAT_KPA,
  PRESSURE_FORMAT_PSI,
  TEMPERATURE_FORMAT_C,
  TEMPERATURE_FORMAT_F,
  VESSEL_STATUS_CLEAN,
  VESSEL_STATUS_CONDITIONING,
  VESSEL_STATUS_FILLED,
  VESSEL_STATUS_SERVING,
  VESSEL_TYPE_BOTTLE,
  VESSEL_TYPE_KEG,
  VOLUME_FORMAT_METRIC,
  VOLUME_FORMAT_UK,
  VOLUME_FORMAT_US
}

export const temperatureOptions = [
  { label: 'Celsius °C', value: TEMPERATURE_FORMAT_C },
  { label: 'Fahrenheit °F', value: TEMPERATURE_FORMAT_F }
]

export const gravityOptions = [
  { label: 'Specific Gravity', value: GRAVITY_FORMAT_SG },
  { label: 'Plato', value: GRAVITY_FORMAT_PLATO }
]

export const pressureOptions = [
  { label: 'PSI', value: PRESSURE_FORMAT_PSI },
  { label: 'Bar', value: PRESSURE_FORMAT_BAR },
  { label: 'kPa', value: PRESSURE_FORMAT_KPA }
]

export const volumeOptions = [
  { label: 'Metric', value: VOLUME_FORMAT_METRIC },
  { label: 'US', value: VOLUME_FORMAT_US },
  { label: 'UK', value: VOLUME_FORMAT_UK }
]

export const vesselStatusOptions = [
  { label: 'Clean', value: VESSEL_STATUS_CLEAN },
  { label: 'Conditioning', value: VESSEL_STATUS_CONDITIONING },
  { label: 'Serving', value: VESSEL_STATUS_SERVING }
]
