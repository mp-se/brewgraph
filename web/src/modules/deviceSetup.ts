/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import {
  DEVICE_TYPE_CHAMBER_CONTROLLER,
  DEVICE_TYPE_GRAVITYMON,
  DEVICE_TYPE_GRAVITYMON_GW,
  DEVICE_TYPE_ISPINDEL,
  DEVICE_TYPE_KEGMON,
  DEVICE_TYPE_PRESSUREMON
} from '@/modules/classes'

/** How to point a device at the server: the sentence above the table and the ingest path it posts to. */
export interface DeviceSetup {
  intro: string
  /** Short public ingest path, as served by `GET /api/ingest/endpoints`; empty for Kegmon, whose firmware adds its own paths. */
  path: string
  /** iSpindel's config UI asks for host, path, port and SSL as separate fields. */
  separateFields?: boolean
  /** The ingest endpoint also accepts the token as `?token=` and as a trailing path segment. */
  tokenInUrl?: boolean
}

const SETUP: Record<string, DeviceSetup> = {
  [DEVICE_TYPE_ISPINDEL]: {
    intro: 'In the iSpindel config UI (Service tab):',
    path: '/ingest/ispindel',
    separateFields: true,
    tokenInUrl: true
  },
  [DEVICE_TYPE_GRAVITYMON]: {
    intro: "Navigate to the device's local IP in a browser and enter:",
    path: '/ingest/gravitymon',
    tokenInUrl: true
  },
  // The gateway relays GravityMon readings, so it posts to the same endpoint.
  [DEVICE_TYPE_GRAVITYMON_GW]: {
    intro: 'Configure the gateway to forward readings to:',
    path: '/ingest/gravitymon',
    tokenInUrl: true
  },
  [DEVICE_TYPE_PRESSUREMON]: {
    intro: 'Configure the device to post to:',
    path: '/ingest/pressuremon',
    tokenInUrl: true
  },
  [DEVICE_TYPE_KEGMON]: {
    intro: "Server only — the firmware adds /ingest/kegmon and /ingest/kegmon/beer. Configure Kegmon with this server and the tap's token:",
    path: ''
  },
  [DEVICE_TYPE_CHAMBER_CONTROLLER]: {
    intro: 'Configure your chamber controller to post temperature data and fetch target temperature for active control:',
    path: '/ingest/chamber'
  }
}

/** Setup instructions for a device type, or null when the type posts nothing (unknown). */
export function deviceSetupFor(deviceType: string | null | undefined): DeviceSetup | null {
  return (deviceType && SETUP[deviceType]) || null
}
