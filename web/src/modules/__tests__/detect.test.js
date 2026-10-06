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

import { describe, it, expect, vi } from 'vitest'
import { detectId, detectMdns, detectPlatform, detectDeviceType } from '../detect'

// Mock the logger
vi.mock('../logger', () => ({
  logDebug: vi.fn()
}))

describe('detect.js - Device Detection', () => {
  describe('detectId', () => {
    it('should detect id from status object', () => {
      const status = { id: 'device-123' }
      const result = detectId(status)
      expect(result).toBe('device-123')
    })

    it('should return empty string when id is missing', () => {
      const status = { name: 'test' }
      const result = detectId(status)
      expect(result).toBe('')
    })

    it('should handle empty status object', () => {
      const status = {}
      const result = detectId(status)
      expect(result).toBe('')
    })

    it('should detect id even with other properties', () => {
      const status = { id: 'abc123', name: 'device', value: 42 }
      const result = detectId(status)
      expect(result).toBe('abc123')
    })
  })

  describe('detectMdns', () => {
    it('should detect mDNS from status object', () => {
      const status = { mdns: 'brewgraph.local' }
      const result = detectMdns(status)
      expect(result).toBe('brewgraph.local')
    })

    it('should return empty string when mDNS is missing', () => {
      const status = { name: 'test' }
      const result = detectMdns(status)
      expect(result).toBe('')
    })

    it('should handle empty status object', () => {
      const status = {}
      const result = detectMdns(status)
      expect(result).toBe('')
    })
  })

  describe('detectPlatform', () => {
    it('should detect and lowercase platform', () => {
      const status = { platform: 'ESP32 v1.0' }
      const result = detectPlatform(status)
      expect(result).toBe('esp32')
    })

    it('should return empty string when platform is missing', () => {
      const status = { name: 'test' }
      const result = detectPlatform(status)
      expect(result).toBe('')
    })

    it('should extract first word only', () => {
      const status = { platform: 'ESP32C3 WROOM Module' }
      const result = detectPlatform(status)
      expect(result).toBe('esp32c3')
    })

    it('should handle uppercase platform', () => {
      const status = { platform: 'ESP8266' }
      const result = detectPlatform(status)
      expect(result).toBe('esp8266')
    })
  })

  describe('detectDeviceType', () => {
    it('should detect Kegmon device type', () => {
      const status = { scale_raw1: 1000 }
      const result = detectDeviceType(status)
      expect(result).toBe('kegmon')
    })

    it('should detect Chamber Controller device type', () => {
      const status = { pid_mode: 'auto' }
      const result = detectDeviceType(status)
      expect(result).toBe('chamber_controller')
    })

    it('should detect Gravitymon Gateway device type', () => {
      const status = { gravity_device: 'device-1' }
      const result = detectDeviceType(status)
      expect(result).toBe('gravitymon_gateway')
    })

    it('should detect Gravitymon device type', () => {
      const status = { gravity: 1.05 }
      const result = detectDeviceType(status)
      expect(result).toBe('gravitymon')
    })

    it('should detect Pressuremon device type', () => {
      const status = { pressure: 20 }
      const result = detectDeviceType(status)
      expect(result).toBe('pressuremon')
    })

    it('should return empty string for unknown device type', () => {
      const status = { unknown_property: 'value' }
      const result = detectDeviceType(status)
      expect(result).toBe('')
    })

    it('should return empty string for empty status', () => {
      const status = {}
      const result = detectDeviceType(status)
      expect(result).toBe('')
    })

    it('should prioritize in order: Kegmon > Chamber > Gateway > Gravitymon > Pressuremon', () => {
      // Multiple properties present - should match Kegmon first
      const status = {
        scale_raw1: 1000,
        pid_mode: 'auto',
        gravity: 1.05
      }
      const result = detectDeviceType(status)
      expect(result).toBe('kegmon')
    })

    it('should match Chamber over lower priority', () => {
      const status = {
        pid_mode: 'auto',
        gravity: 1.05,
        pressure: 20
      }
      const result = detectDeviceType(status)
      expect(result).toBe('chamber_controller')
    })
  })
})
