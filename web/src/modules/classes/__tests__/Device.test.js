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

import { describe, it, expect } from 'vitest'
import { Device } from '@/modules/classes'

describe('Device - Data Class', () => {
  describe('Constructor', () => {
    it('should create a Device with default values', () => {
      const d = new Device()
      expect(d.id).toBe('')
      expect(d.name).toBe('')
      expect(d.chipId).toBe('')
      expect(d.chipFamily).toBe('')
      expect(d.deviceType).toBe('')
      expect(d.mdns).toBe('')
      expect(d.config).toBe('')
      expect(d.deviceColor).toBe('white')
      expect(d.url).toBe('')
      expect(d.description).toBe('')
      expect(d.collectLogs).toBe(false)
      expect(d.token).toBe('')
    })

    it('should use provided values', () => {
      const d = new Device({
        id: 'abc',
        chipId: 'esp32',
        name: 'iSpindel',
        deviceType: 'ispindel',
        collectLogs: true
      })
      expect(d.id).toBe('abc')
      expect(d.chipId).toBe('esp32')
      expect(d.name).toBe('iSpindel')
      expect(d.deviceType).toBe('ispindel')
      expect(d.collectLogs).toBe(true)
    })

    it('should normalize bare http:// url to empty string', () => {
      const d = new Device({ url: 'http://' })
      expect(d.url).toBe('')
    })

    it('should normalize bare https:// url to empty string', () => {
      const d = new Device({ url: 'https://' })
      expect(d.url).toBe('')
    })

    it('should keep a valid url as-is', () => {
      const d = new Device({ url: 'http://192.168.1.1' })
      expect(d.url).toBe('http://192.168.1.1')
    })
  })

  describe('fromJson', () => {
    it('should create a Device from JSON', () => {
      const json = {
        id: 'd1',
        name: 'GravityMon',
        chipId: 'abc123',
        chipFamily: 'esp8266',
        deviceType: 'gravitymon 1.0.0',
        mdns: 'gmon',
        config: '{}',
        deviceColor: 'red',
        url: 'http://gmon.local',
        description: 'gravity sensor',
        collectLogs: true,
        token: 'tok1'
      }
      const d = Device.fromJson(json)
      expect(d.id).toBe('d1')
      expect(d.name).toBe('GravityMon')
      expect(d.chipId).toBe('abc123')
      expect(d.deviceType).toBe('gravitymon 1.0.0')
      expect(d.url).toBe('http://gmon.local')
      expect(d.collectLogs).toBe(true)
      expect(d.token).toBe('tok1')
    })

    it('should default missing fields to empty strings', () => {
      const d = Device.fromJson({ id: 'd2' })
      expect(d.name).toBe('')
      expect(d.chipId).toBe('')
      expect(d.collectLogs).toBe(false)
    })
  })

  describe('toJson', () => {
    it('should serialize mutable fields without id or token', () => {
      const d = new Device({
        id: 'skip',
        name: 'Dev',
        deviceType: 'ispindel',
        chipId: 'c1',
        token: 'secret'
      })
      const json = d.toJson()
      expect(json.name).toBe('Dev')
      expect(json.deviceType).toBe('ispindel')
      expect(json.chipId).toBe('c1')
      expect(json.id).toBeUndefined()
      expect(json.token).toBeUndefined()
    })
  })

  describe('compare', () => {
    it('should return true for equal devices', () => {
      const d1 = new Device({ name: 'X', deviceType: 'ispindel', chipId: 'c1' })
      const d2 = new Device({ name: 'X', deviceType: 'ispindel', chipId: 'c1' })
      expect(Device.compare(d1, d2)).toBe(true)
    })

    it('compares JSON config by value across separate API response objects', () => {
      const d1 = new Device({ config: { sleep: 300, wifi: { enabled: true } } })
      const d2 = new Device({ config: { sleep: 300, wifi: { enabled: true } } })
      const changed = new Device({ config: { sleep: 600, wifi: { enabled: true } } })

      expect(Device.compare(d1, d2)).toBe(true)
      expect(Device.compare(d1, changed)).toBe(false)
    })

    it('should return false for different devices', () => {
      const d1 = new Device({ name: 'X' })
      const d2 = new Device({ name: 'Y' })
      expect(Device.compare(d1, d2)).toBe(false)
    })

    it.each([
      ['deviceColor', { deviceColor: 'blue' }],
      ['batchId', { batchId: 'batch-1' }],
      ['batchRole', { batchRole: 'pressure' }],
      ['vesselId', { vesselId: 'vessel-1' }]
    ])('detects a changed %s field sent to the API', (_field, changed) => {
      expect(Device.compare(new Device(), new Device(changed))).toBe(false)
    })
  })

  describe('setters', () => {
    it('should update all fields via setters', () => {
      const d = new Device()
      d.id = 'new'
      d.name = 'Updated'
      d.chipId = 'new-chip'
      d.chipFamily = 'esp32'
      d.deviceType = '2.0.0'
      d.mdns = 'pm'
      d.config = '{}'
      d.deviceColor = 'blue'
      d.url = 'http://pm.local'
      d.description = 'updated'
      d.collectLogs = true
      d.token = 'tok2'
      expect(d.name).toBe('Updated')
      expect(d.collectLogs).toBe(true)
      expect(d.token).toBe('tok2')
    })
  })
})
