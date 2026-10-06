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

import { logDebug } from '@/ui'
import {
  detectDeviceType as detectCoreDeviceType,
  detectId as detectCoreId,
  detectMdns as detectCoreMdns,
  detectPlatform as detectCorePlatform
} from '@brewgraph/core'

export function detectId(status: Record<string, unknown>): string {
  const id = detectCoreId(status)
  if (id) logDebug('DeviceListView.detectId()', 'ID found', id)
  return id
}

export function detectMdns(status: Record<string, unknown>): string {
  const mdns = detectCoreMdns(status)
  if (mdns) logDebug('DeviceListView.detectMdns()', 'mDNS found', mdns)
  return mdns
}

export function detectPlatform(status: Record<string, unknown>): string {
  const platform = detectCorePlatform(status)
  if (platform) logDebug('DeviceListView.detectPlatform()', 'Platform found', platform)
  return platform
}

export function detectDeviceType(status: Record<string, unknown>): string {
  logDebug('DeviceListView.detectDeviceType()')

  const deviceType = detectCoreDeviceType(status)
  logDebug('DeviceListView.detectDeviceType()', deviceType || "Unknown device type, can't detect")
  return deviceType
}
