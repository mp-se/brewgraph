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

/**
 * Barrel export for all data model classes.
 * Allows: import { Batch, Device, ... } from '@/modules/classes'
 */

export { Batch } from './Batch'
export { BatchNote } from './BatchNote'
export {
  TEMPERATURE_FORMAT_C,
  TEMPERATURE_FORMAT_F,
  GRAVITY_FORMAT_SG,
  GRAVITY_FORMAT_PLATO,
  PRESSURE_FORMAT_PSI,
  PRESSURE_FORMAT_BAR,
  PRESSURE_FORMAT_KPA,
  VOLUME_FORMAT_METRIC,
  VOLUME_FORMAT_US,
  VOLUME_FORMAT_UK,
  VESSEL_STATUS_CLEAN,
  VESSEL_STATUS_CONDITIONING,
  VESSEL_STATUS_SERVING,
  VESSEL_TYPE_KEG,
  VESSEL_TYPE_BOTTLE,
  temperatureOptions,
  gravityOptions,
  pressureOptions,
  volumeOptions,
  vesselStatusOptions
} from './Config'
export {
  Device,
  deviceTypeOptions,
  DEVICE_TYPE_UNKNOWN,
  DEVICE_TYPE_GRAVITYMON,
  DEVICE_TYPE_GRAVITYMON_GW,
  DEVICE_TYPE_KEGMON,
  DEVICE_TYPE_CHAMBER_CONTROLLER,
  DEVICE_TYPE_PRESSUREMON,
  DEVICE_TYPE_ISPINDEL,
  chipFamilyOptions,
  CHIP_FAMILY_UNKNOWN,
  CHIP_FAMILY_ESP8266,
  CHIP_FAMILY_ESP32,
  CHIP_FAMILY_ESP32C3,
  CHIP_FAMILY_ESP32S2,
  CHIP_FAMILY_ESP32S3,
  deviceColorOptions,
  DEVICE_COLOR_BLACK,
  DEVICE_COLOR_RED,
  DEVICE_COLOR_ORANGE,
  DEVICE_COLOR_YELLOW,
  DEVICE_COLOR_GREEN,
  DEVICE_COLOR_BLUE,
  DEVICE_COLOR_PURPLE,
  DEVICE_COLOR_PINK,
  DEVICE_COLOR_WHITE
} from './Device'
export { MDNS } from './MDNS'
export { Gravity } from './Gravity'
export { Pressure } from './Pressure'
export { Pour } from './Pour'
export { PourEvent } from './PourEvent'
export { StorageVessel } from './StorageVessel'
export { Tap } from './Tap'
export { BrewfatherBatch } from './BrewfatherBatch'
export { Prediction } from './Prediction'
export {
  Integration,
  integrationTypeOptions,
  integrationTypeOptionsFor,
  measurementOptions,
  INTEGRATION_TYPE_ISPINDEL_FORWARD,
  INTEGRATION_TYPE_BREWFATHER_FORWARD,
  INTEGRATION_TYPE_CUSTOM_FORWARD,
  MEASUREMENT_GRAVITY,
  MEASUREMENT_PRESSURE,
  MEASUREMENT_POUR,
  MEASUREMENT_TEMP
} from './Integration'
