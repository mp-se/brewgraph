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

interface GravityParams {
  id?: number
  temperature?: number | null
  gravity?: number
  velocity?: number | null
  angle?: number | null
  battery?: number | null
  rssi?: number | null
  runTime?: number | null
  excluded?: boolean
  createdAt?: string
  batchId?: string
  deviceId?: string | null
}

export class Gravity {
  private _id: number
  private _temperature: number | null
  private _gravity: number
  private _velocity: number | null
  private _angle: number | null
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
    gravity = 0.0,
    velocity = null,
    angle = null,
    battery = null,
    rssi = null,
    runTime = null,
    excluded = false,
    createdAt = '',
    batchId = '',
    deviceId = null
  }: GravityParams = {}) {
    this._id = id
    this._temperature = temperature ?? null
    this._gravity = gravity ?? 0.0
    this._velocity = velocity ?? null
    this._angle = angle ?? null
    this._battery = battery ?? null
    this._rssi = rssi ?? null
    this._runTime = runTime ?? null
    this._excluded = excluded ?? false
    this._createdAt = createdAt ?? ''
    this._batchId = batchId ?? ''
    this._deviceId = deviceId ?? null
  }

  static fromJson(g: Record<string, unknown>): Gravity {
    return new Gravity({
      id: g.id as number,
      temperature: (g.temperature as number | null) ?? null,
      gravity: g.gravity as number,
      velocity: (g.velocity as number | null) ?? null,
      angle: (g.angle as number | null) ?? null,
      battery: (g.battery as number | null) ?? null,
      rssi: (g.rssi as number | null) ?? null,
      runTime: (g.runTime as number | null) ?? null,
      excluded: (g.excluded as boolean) ?? false,
      createdAt: (g.createdAt as string) ?? '',
      batchId: (g.batchId as string) ?? '',
      deviceId: (g.deviceId as string | null) ?? null
    })
  }

  toJson(): Record<string, unknown> {
    return {
      temperature: this.temperature,
      gravity: this.gravity,
      velocity: this.velocity,
      angle: this.angle,
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
  get gravity() {
    return this._gravity
  }
  get velocity() {
    return this._velocity
  }
  get angle() {
    return this._angle
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
  get created() {
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
  set gravity(v: number) {
    this._gravity = v
  }
  set velocity(v: number | null) {
    this._velocity = v
  }
  set angle(v: number | null) {
    this._angle = v
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
