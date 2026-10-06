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

interface PressureParams {
  id?: number
  temperature?: number | null
  pressure?: number
  battery?: number | null
  rssi?: number | null
  runTime?: number | null
  excluded?: boolean
  createdAt?: string
  batchId?: string
  deviceId?: string | null
}

export class Pressure {
  private _id: number
  private _temperature: number | null
  private _pressure: number
  private _battery: number | null
  private _rssi: number | null
  private _runTime: number | null
  private _excluded: boolean
  private _createdAt: string
  private _batchId: string
  private _deviceId: string | null

  constructor({
    id = 0,
    temperature = null,
    pressure = 0.0,
    battery = null,
    rssi = null,
    runTime = null,
    excluded = false,
    createdAt = '',
    batchId = '',
    deviceId = null
  }: PressureParams = {}) {
    this._id = id
    this._temperature = temperature ?? null
    this._pressure = pressure ?? 0.0
    this._battery = battery ?? null
    this._rssi = rssi ?? null
    this._runTime = runTime ?? null
    this._excluded = excluded ?? false
    this._createdAt = createdAt ?? ''
    this._batchId = batchId ?? ''
    this._deviceId = deviceId ?? null
  }

  static fromJson(p: Record<string, unknown>): Pressure {
    return new Pressure({
      id: p.id as number,
      temperature: (p.temperature as number | null) ?? null,
      pressure: p.pressure as number,
      battery: (p.battery as number | null) ?? null,
      rssi: (p.rssi as number | null) ?? null,
      runTime: (p.runTime as number | null) ?? null,
      excluded: (p.excluded as boolean) ?? false,
      createdAt: (p.createdAt as string) ?? '',
      batchId: (p.batchId as string) ?? '',
      deviceId: (p.deviceId as string | null) ?? null
    })
  }

  toJson(): Record<string, unknown> {
    return {
      temperature: this.temperature,
      pressure: this.pressure,
      battery: this.battery,
      rssi: this.rssi,
      runTime: this.runTime,
      excluded: this.excluded
    }
  }

  get id() {
    return this._id
  }
  get temperature() {
    return this._temperature
  }
  get pressure() {
    return this._pressure
  }
  get battery() {
    return this._battery
  }
  get rssi() {
    return this._rssi
  }
  get runTime() {
    return this._runTime
  }
  get excluded() {
    return this._excluded
  }
  get createdAt() {
    return this._createdAt
  }
  get batchId() {
    return this._batchId
  }
  get deviceId() {
    return this._deviceId
  }

  set id(v: number) {
    this._id = v
  }
  set temperature(v: number | null) {
    this._temperature = v
  }
  set pressure(v: number) {
    this._pressure = v
  }
  set battery(v: number | null) {
    this._battery = v
  }
  set rssi(v: number | null) {
    this._rssi = v
  }
  set runTime(v: number | null) {
    this._runTime = v
  }
  set excluded(v: boolean) {
    this._excluded = v
  }
  set createdAt(v: string) {
    this._createdAt = v
  }
  set batchId(v: string) {
    this._batchId = v
  }
  set deviceId(v: string | null) {
    this._deviceId = v
  }
}
